"""对运行中的 API 做真实 HTTP 冒烟检查。

本地运行 pytest 时未设置 API_BASE_URL，本用例跳过；
compose 的 verify 服务会注入 API_BASE_URL=http://api:8000 并真正执行。
"""
from __future__ import annotations

import os
import time

import httpx
import pytest

BASE_URL = os.environ.get("API_BASE_URL", "").rstrip("/")

pytestmark = pytest.mark.skipif(not BASE_URL, reason="未设置 API_BASE_URL，跳过联调冒烟")


def _wait_ready(deadline: float = 60.0) -> None:
    start = time.monotonic()
    while True:
        try:
            resp = httpx.get(f"{BASE_URL}/api/health", timeout=2.0)
            if resp.status_code == 200:
                return
        except httpx.HTTPError:
            pass
        if time.monotonic() - start > deadline:
            raise TimeoutError(f"等待 {BASE_URL} 就绪超时")
        time.sleep(1.0)


def test_live_api_roundtrip():
    _wait_ready()
    resp = httpx.post(
        f"{BASE_URL}/api/paginate",
        json={
            "capacity": 10,
            "paragraphs": [
                {"id": "p1", "lines": 4, "keep_with_next": False},
                {"id": "p2", "lines": 4, "keep_with_next": False},
            ],
            "footnotes": [
                {"id": "n1", "marker_line": 2, "height": 3},
                {"id": "n2", "marker_line": 6, "height": 2},
            ],
        },
        timeout=5.0,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["summary"]["ending_lines"] == [4, 8]
    assert body["pages"][0]["used"] == 7


def test_live_api_infeasible():
    _wait_ready()
    resp = httpx.post(
        f"{BASE_URL}/api/paginate",
        json={
            "capacity": 3,
            "paragraphs": [{"id": "p1", "lines": 2, "keep_with_next": False}],
            "footnotes": [{"id": "n1", "marker_line": 1, "height": 4}],
        },
        timeout=5.0,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "infeasible"
    assert body["failure"]["paragraph_id"] == "p1"
    assert body["failure"]["footnote_ids"] == ["n1"]


def test_live_api_directive_conflict_release_flow():
    """真实 HTTP：指令冲突 ⇒ 唯一最小释放建议；确认后 release_confirmed=true。"""
    _wait_ready()
    payload = {
        "capacity": 4,
        "paragraphs": [{"id": "p1", "lines": 6, "keep_with_next": False}],
        "footnotes": [],
        "directives": [
            {"kind": "lock_break", "paragraph_id": "p1", "line_in_paragraph": 2},
            {"kind": "lock_break", "paragraph_id": "p1", "line_in_paragraph": 3},
        ],
    }
    resp = httpx.post(f"{BASE_URL}/api/paginate", json=payload, timeout=5.0)
    body = resp.json()
    assert body["status"] == "ok"
    assert body["directives_satisfied"] is False
    assert body["release_confirmed"] is False
    assert [d["order"] for d in body["released_directives"]] == [0]
    # 失效指令就地标出为空列表（字段存在）
    assert body["invalid_directives"] == []

    # 一次确认释放并重算
    payload["release_directives"] = [0]
    resp = httpx.post(f"{BASE_URL}/api/paginate", json=payload, timeout=5.0)
    body = resp.json()
    assert body["release_confirmed"] is True
    assert body["summary"]["ending_lines"] == [3, 6]


def test_live_api_old_request_shape_unchanged():
    """无指令旧请求的响应不含任何新增字段。"""
    _wait_ready()
    resp = httpx.post(
        f"{BASE_URL}/api/paginate",
        json={
            "capacity": 10,
            "paragraphs": [
                {"id": "p1", "lines": 4, "keep_with_next": False},
                {"id": "p2", "lines": 4, "keep_with_next": False},
            ],
            "footnotes": [],
        },
        timeout=5.0,
    )
    body = resp.json()
    for key in (
        "directives_satisfied",
        "active_directive_count",
        "invalid_directives",
        "released_directives",
        "release_confirmed",
    ):
        assert key not in body
