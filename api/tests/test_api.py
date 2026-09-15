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


# ---------- 人工版式指令 ----------

def test_request_without_directives_keeps_exact_old_shape():
    """无指令旧请求：响应逐字段保持原样（不出现任何指令字段）。"""
    resp = client.post("/api/paginate", json=base_request())
    body = resp.json()
    assert "directives_satisfied" not in body
    assert "active_directive_count" not in body
    assert "invalid_directives" not in body
    assert "released_directives" not in body
    assert "release_confirmed" not in body
    # 失败响应同样不带新字段
    resp2 = client.post("/api/paginate", json=base_request(
        capacity=3,
        paragraphs=[
            {"id": "p1", "lines": 2, "keep_with_next": True},
            {"id": "p2", "lines": 2, "keep_with_next": False},
        ],
        footnotes=[],
    ))
    failure = resp2.json()["failure"]
    assert "invalid_directives" not in failure


def test_lock_break_directive_ok_contract():
    resp = client.post("/api/paginate", json=base_request(
        directives=[
            {"kind": "lock_break", "paragraph_id": "p1", "line_in_paragraph": 4},
        ],
    ))
    body = resp.json()
    assert body["status"] == "ok"
    assert body["directives_satisfied"] is True
    assert body["active_directive_count"] == 1
    assert body["invalid_directives"] == []
    assert body["released_directives"] == []
    assert body["release_confirmed"] is True
    # 锁定段界（p1 末行=第 4 行）：无指令时本就断在 4，结果不变
    assert body["summary"]["ending_lines"] == [4, 8]


def test_no_split_directive_changes_solution():
    # H=4，单段 6 行，禁止第 3 行后断开 ⇒ 最优从 (3,6) 变为 (2,6)
    resp = client.post("/api/paginate", json={
        "capacity": 4,
        "paragraphs": [{"id": "p1", "lines": 6, "keep_with_next": False}],
        "footnotes": [],
        "directives": [{"kind": "no_split", "paragraph_id": "p1", "line_in_paragraph": 3}],
    })
    body = resp.json()
    assert body["summary"]["ending_lines"] == [2, 6]
    assert body["directives_satisfied"] is True
    assert body["invalid_directives"] == []


def test_invalid_directives_are_localized_and_others_apply():
    resp = client.post("/api/paginate", json={
        "capacity": 10,
        "paragraphs": [
            {"id": "p1", "lines": 5, "keep_with_next": False},
            {"id": "p2", "lines": 5, "keep_with_next": False},
        ],
        "footnotes": [],
        "directives": [
            {"kind": "lock_break", "paragraph_id": "ghost", "line_in_paragraph": 1},
            {"kind": "lock_break", "paragraph_id": "p1", "line_in_paragraph": 9},
            {"kind": "lock_break", "paragraph_id": "p1", "line_in_paragraph": 1},
            {"kind": "no_split", "paragraph_id": "p1", "line_in_paragraph": 5},
            {"kind": "lock_break", "paragraph_id": "p1", "line_in_paragraph": 5},
        ],
    })
    body = resp.json()
    invalid = body["invalid_directives"]
    assert {(i["order"], i["reason"]) for i in invalid} == {
        (0, "paragraph_not_found"),
        (1, "line_out_of_range"),
        (2, "illegal_position"),
        (3, "illegal_position"),
    }
    assert body["active_directive_count"] == 1
    assert body["directives_satisfied"] is True
    assert body["summary"]["ending_lines"] == [5, 10]


def test_conflicting_directives_return_release_suggestion():
    # H=4，单段 6 行，锁定第 2、3 行后：至少释放 1 条，序号字典序取 0。
    resp = client.post("/api/paginate", json={
        "capacity": 4,
        "paragraphs": [{"id": "p1", "lines": 6, "keep_with_next": False}],
        "footnotes": [],
        "directives": [
            {"kind": "lock_break", "paragraph_id": "p1", "line_in_paragraph": 2},
            {"kind": "lock_break", "paragraph_id": "p1", "line_in_paragraph": 3},
        ],
    })
    body = resp.json()
    assert body["status"] == "ok"
    assert body["directives_satisfied"] is False
    assert body["release_confirmed"] is False
    assert [d["order"] for d in body["released_directives"]] == [0]
    assert body["released_directives"][0] == {
        "order": 0, "kind": "lock_break",
        "paragraph_id": "p1", "line_in_paragraph": 2,
    }
    # 建议解仍按既有目标给出可复算预览（保留锁 3 ⇒ 首页结束于 3）
    assert body["summary"]["ending_lines"] == [3, 6]


def test_confirm_release_and_recompute():
    payload = {
        "capacity": 4,
        "paragraphs": [{"id": "p1", "lines": 6, "keep_with_next": False}],
        "footnotes": [],
        "directives": [
            {"kind": "lock_break", "paragraph_id": "p1", "line_in_paragraph": 2},
            {"kind": "lock_break", "paragraph_id": "p1", "line_in_paragraph": 3},
        ],
    }
    # 一次确认释放序号 0 后重算
    payload["release_directives"] = [0]
    resp = client.post("/api/paginate", json=payload)
    body = resp.json()
    # 已确认释放：仍记录被释放指令（故 directives_satisfied=False），但无待确认建议
    assert body["directives_satisfied"] is False
    assert body["release_confirmed"] is True
    assert [d["order"] for d in body["released_directives"]] == [0]
    assert body["summary"]["ending_lines"] == [3, 6]


def test_confirm_insufficient_release_appends_minimum_extra():
    # 三锁 2、3、4：只确认释放 0（锁2）后锁3、锁4 仍冲突，须再释放 1。
    resp = client.post("/api/paginate", json={
        "capacity": 4,
        "paragraphs": [{"id": "p1", "lines": 8, "keep_with_next": False}],
        "footnotes": [],
        "directives": [
            {"kind": "lock_break", "paragraph_id": "p1", "line_in_paragraph": 2},
            {"kind": "lock_break", "paragraph_id": "p1", "line_in_paragraph": 3},
            {"kind": "lock_break", "paragraph_id": "p1", "line_in_paragraph": 4},
        ],
        "release_directives": [0],
    })
    body = resp.json()
    # 追加的 1 未经确认 ⇒ 仍为建议态
    assert body["release_confirmed"] is False
    assert [d["order"] for d in body["released_directives"]] == [0, 1]


def test_base_infeasible_returns_prefix_even_with_directives():
    resp = client.post("/api/paginate", json={
        "capacity": 3,
        "paragraphs": [
            {"id": "p1", "lines": 2, "keep_with_next": True},
            {"id": "p2", "lines": 2, "keep_with_next": False},
        ],
        "footnotes": [],
        "directives": [
            {"kind": "lock_break", "paragraph_id": "p1", "line_in_paragraph": 2},
            {"kind": "lock_break", "paragraph_id": "ghost", "line_in_paragraph": 1},
        ],
    })
    body = resp.json()
    assert body["status"] == "infeasible"
    assert body["failure"]["paragraph_id"] == "p2"
    # 失效指令仍就地标出，但不混入前缀归因（无 released_directives 字段）
    assert [i["order"] for i in body["failure"]["invalid_directives"]] == [1]
    assert "released_directives" not in body


def test_validation_rejects_unknown_kind_and_bad_release_index():
    resp = client.post("/api/paginate", json={
        "capacity": 4,
        "paragraphs": [{"id": "p1", "lines": 6}],
        "footnotes": [],
        "directives": [{"kind": "frozen", "paragraph_id": "p1", "line_in_paragraph": 2}],
    })
    assert resp.status_code == 422
    resp = client.post("/api/paginate", json={
        "capacity": 4,
        "paragraphs": [{"id": "p1", "lines": 6}],
        "footnotes": [],
        "directives": [{"kind": "lock_break", "paragraph_id": "p1", "line_in_paragraph": 2}],
        "release_directives": [5],
    })
    assert resp.status_code == 422
