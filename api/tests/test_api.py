"""API 契约测试（FastAPI TestClient，真实路由与序列化）。"""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def base_request(**overrides):
    req = {
        "capacity": 10,
        "paragraphs": [
            {"id": "p1", "lines": 4, "keep_with_next": False},
            {"id": "p2", "lines": 4, "keep_with_next": False},
        ],
        "footnotes": [
            {"id": "n1", "marker_line": 2, "height": 3},
            {"id": "n2", "marker_line": 6, "height": 2},
        ],
    }
    req.update(overrides)
    return req


def test_health():
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_paginate_ok_contract():
    resp = client.post("/api/paginate", json=base_request())
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["summary"] == {
        "capacity": 10,
        "total_lines": 8,
        "page_count": 2,
        "squared_slack": 25,
        "ending_lines": [4, 8],
    }
    assert len(body["pages"]) == 2
    first, second = body["pages"]
    assert first["start_line"] == 1 and first["end_line"] == 4
    assert first["line_count"] == 4
    assert [l["line"] for l in first["lines"]] == [1, 2, 3, 4]
    assert first["lines"][1] == {"line": 2, "paragraph_id": "p1", "line_in_paragraph": 2}
    assert [f["id"] for f in first["footnotes"]] == ["n1"]
    assert first["text_units"] == 4 and first["footnote_units"] == 3
    assert first["used"] == 7 and first["slack"] == 3
    assert first["break_after"] == {
        "kind": "paragraph_boundary", "after_line": 4, "paragraph_id": "p1",
        "lines_before_in_paragraph": None,
    }
    assert second["break_after"]["kind"] == "end"
    assert [f["id"] for f in second["footnotes"]] == ["n2"]


def test_paginate_split_break_kind():
    # 单段 6 行、H=4：最优在第 3 行后段内断开。
    resp = client.post("/api/paginate", json=base_request(
        capacity=4,
        paragraphs=[{"id": "p1", "lines": 6, "keep_with_next": False}],
        footnotes=[],
    ))
    body = resp.json()
    assert body["status"] == "ok"
    assert body["summary"]["ending_lines"] == [3, 6]
    assert body["pages"][0]["break_after"] == {
        "kind": "paragraph_split", "after_line": 3, "paragraph_id": "p1",
        "lines_before_in_paragraph": 3,
    }


def test_paginate_infeasible_contract():
    resp = client.post("/api/paginate", json=base_request(
        capacity=3,
        paragraphs=[
            {"id": "p1", "lines": 2, "keep_with_next": True},
            {"id": "p2", "lines": 2, "keep_with_next": False},
            {"id": "p3", "lines": 2, "keep_with_next": False},
        ],
        footnotes=[
            {"id": "n1", "marker_line": 5, "height": 1},
            {"id": "n2", "marker_line": 3, "height": 3},
            {"id": "n3", "marker_line": 3, "height": 1},
        ],
    ))
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "infeasible"
    assert body["summary"] == {"capacity": 3, "total_lines": 6}
    failure = body["failure"]
    # 前缀 [p1] 可行；[p1,p2] 中第 3 行所在页至少 1+3+1=5 > 3 ⇒ 最短不可行前缀末段 p2
    assert failure["paragraph_id"] == "p2"
    assert failure["paragraph_index"] == 2
    assert failure["prefix_paragraph_count"] == 2
    assert failure["prefix_end_line"] == 4
    # 前缀内注记按 (标记行, 录入序号)：n2、n3；n1 在第 5 行，不在前缀内
    assert failure["footnote_ids"] == ["n2", "n3"]
    assert [f["id"] for f in failure["footnotes"]] == ["n2", "n3"]


def test_paginate_infeasible_without_footnotes_returns_empty_list():
    resp = client.post("/api/paginate", json=base_request(
        capacity=3,
        paragraphs=[
            {"id": "p1", "lines": 2, "keep_with_next": True},
            {"id": "p2", "lines": 2, "keep_with_next": False},
        ],
        footnotes=[],
    ))
    body = resp.json()
    assert body["status"] == "infeasible"
    assert body["failure"]["paragraph_id"] == "p2"
    assert body["failure"]["footnote_ids"] == []
    assert body["failure"]["footnotes"] == []


def test_validation_rejects_bad_input():
    cases = [
        ("capacity 为 0", base_request(capacity=0)),
        ("段落行数为 0", base_request(paragraphs=[{"id": "p1", "lines": 0}])),
        ("段落为空", base_request(paragraphs=[])),
        ("段落 id 重复", base_request(paragraphs=[
            {"id": "p1", "lines": 2}, {"id": "p1", "lines": 2}])),
        ("注记高度为 0", base_request(footnotes=[{"id": "n1", "marker_line": 1, "height": 0}])),
        ("标记行超出总行数", base_request(footnotes=[{"id": "n1", "marker_line": 99, "height": 1}])),
        ("注记 id 重复", base_request(footnotes=[
            {"id": "n1", "marker_line": 1, "height": 1},
            {"id": "n1", "marker_line": 2, "height": 1},
        ])),
    ]
    for label, payload in cases:
        resp = client.post("/api/paginate", json=payload)
        assert resp.status_code == 422, f"{label} 应返回 422，实际 {resp.status_code}"
