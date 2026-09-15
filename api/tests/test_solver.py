"""求解器单元测试：所有期望值均手工推算。"""
from __future__ import annotations

from app.solver import Document, Failure, Footnote, Paragraph, Solution, solve


def doc(capacity, paragraphs, footnotes=()):
    return Document(
        capacity,
        tuple(Paragraph(*p) for p in paragraphs),
        tuple(Footnote(fid, m, h, i) for i, (fid, m, h) in enumerate(footnotes)),
    )


def as_failure(result):
    assert isinstance(result, Failure), f"期望不可行，实际得到 {result!r}"
    return result


def as_solution(result):
    assert isinstance(result, Solution), f"期望可行解，实际得到 {result!r}"
    return result


def test_footnotes_push_page_breaks():
    # H=10，两段各 4 行；n1 标记第 2 行高 3，n2 标记第 6 行高 2。
    # 候选断点：段内仅第 2、6 行后（两侧 ≥2 行），段界第 4 行后。
    # 断 2：占用 5 / 8，平方和 29；断 4：7 / 6，平方和 25；断 6：9 / 2，平方和 65。
    sol = as_solution(solve(doc(10, [("p1", 4, False), ("p2", 4, False)],
                               [("n1", 2, 3), ("n2", 6, 2)])))
    assert sol.ending_lines == (4, 8)
    assert sol.squared_slack == 25
    assert [f.id for f in sol.pages[0].footnotes] == ["n1"]
    assert [f.id for f in sol.pages[1].footnotes] == ["n2"]
    assert sol.pages[0].used == 7 and sol.pages[0].slack == 3
    assert sol.pages[1].used == 6 and sol.pages[1].slack == 4


def test_lexicographic_tie_break_on_ending_lines():
    # H=4，五个单行段。两页方案中平方和最小为 5，断点序列 (2,5) 与 (3,5) 并列，
    # 取字典序最小 ⇒ (2, 5)。
    sol = as_solution(solve(doc(4, [(f"p{i}", 1, False) for i in range(1, 6)])))
    assert sol.ending_lines == (2, 5)
    assert sol.squared_slack == 5


def test_keep_with_next_makes_document_infeasible():
    # H=3，p1 两行且保持，p2 两行：p1 末行须与 p2 前两行同页，
    # 即第 2、3、4 行同页 ⇒ 至少 3 行加第 1 行无处可放，无解。
    # 最短不可行前缀为前两段（p1 自身可行）。
    failure = as_failure(solve(doc(3, [("p1", 2, True), ("p2", 2, False)])))
    assert failure.paragraph_index == 2
    assert failure.paragraph_id == "p2"
    assert failure.prefix_end_line == 4
    assert failure.footnotes == ()


def test_oversized_footnote_fails_at_first_prefix():
    failure = as_failure(solve(doc(3, [("p1", 2, False)], [("n1", 1, 4)])))
    assert failure.paragraph_index == 1
    assert failure.paragraph_id == "p1"
    assert [f.id for f in failure.footnotes] == ["n1"]


def test_keep_with_single_line_next_paragraph():
    # H=2，p1 两行保持，p2 仅一行：p1 末行（第 2 行）须与 p2 唯一行同页，
    # 但第 1 行无法单独成页（段内断点两侧须 ≥2 行）⇒ 无解，前缀末段为 p2。
    failure = as_failure(solve(doc(2, [("p1", 2, True), ("p2", 1, False)])))
    assert failure.paragraph_id == "p2"
    assert failure.prefix_end_line == 3


def test_paragraph_split_balances_pages():
    # H=4，单段 6 行。可行断点：第 2、3、4 行后。
    # 平方和：断 2 ⇒ 4+0=4；断 3 ⇒ 1+1=2；断 4 ⇒ 0+4=4。取断 3。
    sol = as_solution(solve(doc(4, [("p1", 6, False)])))
    assert sol.ending_lines == (3, 6)
    assert sol.squared_slack == 2


def test_failure_lists_prefix_footnotes_in_marker_then_input_order():
    # H=3，三段各两行；n2、n3 标记第 3 行（高 3、1），n1 标记第 5 行。
    # 含第 3 行的页至少占 1+3+1=5 > 3 ⇒ 前两段即不可行；n1 不在前缀内。
    failure = as_failure(solve(doc(
        3,
        [("p1", 2, False), ("p2", 2, False), ("p3", 2, False)],
        [("n1", 5, 1), ("n2", 3, 3), ("n3", 3, 1)],
    )))
    assert failure.paragraph_id == "p2"
    assert failure.prefix_end_line == 4
    assert [f.id for f in failure.footnotes] == ["n2", "n3"]


def test_keep_satisfied_on_single_page():
    sol = as_solution(solve(doc(5, [("p1", 2, True), ("p2", 2, False)])))
    assert sol.ending_lines == (4,)
    assert sol.squared_slack == 1


def test_last_paragraph_keep_flag_is_ignored():
    # 末段无下段，其保持标记不参与约束。
    sol = as_solution(solve(doc(2, [("p1", 2, False), ("p2", 2, True)])))
    assert sol.ending_lines == (2, 4)


def test_keep_chain_forces_joint_pages():
    # H=5，p1、p2 均保持：第 2、4 行后均不可断 ⇒ 三段同页，共 6 行 > 5 ⇒ 无解。
    failure = as_failure(solve(doc(
        5, [("p1", 2, True), ("p2", 2, True), ("p3", 2, False)]
    )))
    # 前缀 1：[2] 可行；前缀 2：第 2 行后不可断，[1..4] 可行；
    # 前缀 3：第 2、4 行后均不可断，[1..6]=6>5 不可行。
    assert failure.paragraph_id == "p3"
    assert failure.prefix_end_line == 6


def test_footnote_ordering_on_same_marker_line():
    # 同一标记行的多条注记按录入序号排列。
    sol = as_solution(solve(doc(
        10, [("p1", 3, False)], [("nb", 2, 1), ("na", 2, 2), ("nc", 1, 1)]
    )))
    assert [f.id for f in sol.pages[0].footnotes] == ["nc", "nb", "na"]


def test_minimal_page_count_wins_over_balance():
    # H=6，两段各 3 行：一页放下（剩余 0，平方和 0）优于两页。
    sol = as_solution(solve(doc(6, [("p1", 3, False), ("p2", 3, False)])))
    assert sol.ending_lines == (6,)
