"""人工版式指令的求解器单元测试：所有期望值均手工推算。"""
from __future__ import annotations

from app.solver import (
    Directive,
    Document,
    Failure,
    Footnote,
    ILLEGAL_POSITION,
    LINE_OUT_OF_RANGE,
    LOCK_BREAK,
    NO_SPLIT,
    PARAGRAPH_NOT_FOUND,
    Paragraph,
    Solution,
    classify_directives,
    solve,
)


def doc(capacity, paragraphs, footnotes=(), directives=()):
    return Document(
        capacity,
        tuple(Paragraph(*p) for p in paragraphs),
        tuple(Footnote(fid, m, h, i) for i, (fid, m, h) in enumerate(footnotes)),
        tuple(Directive(kind, pid, line, i) for i, (kind, pid, line) in enumerate(directives)),
    )


def as_failure(result):
    assert isinstance(result, Failure), f"期望不可行，实际得到 {result!r}"
    return result


def as_solution(result):
    assert isinstance(result, Solution), f"期望可行解，实际得到 {result!r}"
    return result


# ---------- 指令生效：嵌入现有目标求解 ----------

def test_lock_break_at_paragraph_boundary_forces_page_end():
    # H=10，p1、p2 各 5 行无注记，无指令时一页装下（结束行 (10,)）。
    # 在段界（p1 第 5 行后）锁定断点 ⇒ 必须断在 5。
    sol = as_solution(solve(doc(
        10, [("p1", 5, False), ("p2", 5, False)],
        directives=[(LOCK_BREAK, "p1", 5)],
    )))
    assert sol.ending_lines == (5, 10)
    assert sol.violated_directives == ()
    assert sol.invalid_directives == ()


def test_lock_break_internal_changes_optimal_ending():
    # H=10，p1=4、p2=4，n1@2 高3，n2@6 高2：无指令最优断段界 4（平方和 25）。
    # 锁定段内断点 p2 第 2 行（全局第 6 行）⇒ 第 6 行必须是页末。
    # 两页方案 (6,8) 首页占用 6+3+2=11 > 10 不可行；三页中
    # (2,6,8) 平方和 25+16+64=105，优于 (4,6,8) 的 9+36+64=109。
    sol = as_solution(solve(doc(
        10, [("p1", 4, False), ("p2", 4, False)],
        [("n1", 2, 3), ("n2", 6, 2)],
        directives=[(LOCK_BREAK, "p2", 2)],
    )))
    assert sol.ending_lines == (2, 6, 8)
    assert sol.violated_directives == ()


def test_no_split_forbids_internal_break():
    # H=4，单段 6 行，无指令最优断第 3 行后（(3,6)，平方和 2）。
    # 禁止在第 3 行后断开 ⇒ 合法断点剩第 2、4 行后；
    # 断 2 ⇒ (2,6) 次页 4 行平方和 4；断 4 ⇒ (4,6) 平方和 4，字典序取 (2,6)。
    sol = as_solution(solve(doc(
        4, [("p1", 6, False)], directives=[(NO_SPLIT, "p1", 3)]
    )))
    assert sol.ending_lines == (2, 6)
    assert sol.violated_directives == ()


def test_lock_break_internal_requires_two_line_fragments():
    # 段内锁定 p1 第 2 行（全局第 2 行）⇒ 强制该处为断点，首片段 2 行合法。
    sol = as_solution(solve(doc(
        4, [("p1", 6, False)], directives=[(LOCK_BREAK, "p1", 2)]
    )))
    assert sol.ending_lines[0] == 2  # 首页必结束于 2


# ---------- 失效指令定位：保留其余编辑内容 ----------

def test_invalid_paragraph_id_marked_others_still_apply():
    sol = as_solution(solve(doc(
        10, [("p1", 5, False), ("p2", 5, False)],
        directives=[
            (LOCK_BREAK, "ghost", 5),       # 段落失配
            (LOCK_BREAK, "p1", 5),          # 有效：强制段界断点
        ],
    )))
    assert sol.ending_lines == (5, 10)
    assert len(sol.invalid_directives) == 1
    bad = sol.invalid_directives[0]
    assert bad.order == 0 and bad.paragraph_id == "ghost"
    assert bad.reason == PARAGRAPH_NOT_FOUND


def test_invalid_line_out_of_range_marked():
    sol = as_solution(solve(doc(
        10, [("p1", 3, False)],
        directives=[(LOCK_BREAK, "p1", 9)],
    )))
    # 唯一指令失效，等同无指令：一页
    assert sol.ending_lines == (3,)
    bad = sol.invalid_directives[0]
    assert bad.order == 0 and bad.line_in_paragraph == 9
    assert bad.reason == LINE_OUT_OF_RANGE


def test_illegal_positions_classified():
    # p1=5 行（非末段），p2=6 行（末段）
    d = doc(
        10, [("p1", 5, False), ("p2", 6, False)],
        directives=[
            (LOCK_BREAK, "p1", 1),   # 段内第 1 行后：首片段仅 1 行，非法
            (LOCK_BREAK, "p1", 4),   # 段内第 4 行后：末片段仅 1 行，非法
            (LOCK_BREAK, "p2", 6),   # 末段段界：无断页可言，非法
            (NO_SPLIT, "p2", 6),     # 末段段界：无断页可禁，非法
            (NO_SPLIT, "p1", 5),     # 非末段段界禁断：合法
            (LOCK_BREAK, "p1", 5),   # 非末段段界锁定：合法
            (LOCK_BREAK, "p1", 2),   # 段内第 2 行后（两侧 ≥2）：合法
            (NO_SPLIT, "p1", 1),     # 段内第 1 行后：合法位置（虽本就非法断）
            (NO_SPLIT, "p1", 4),     # 段内第 4 行后：合法
        ],
    )
    valid, invalid = classify_directives(d)
    assert {v.order for v in valid} == {4, 5, 6, 7, 8}
    assert {i.order for i in invalid} == {0, 1, 2, 3}
    assert all(i.reason == ILLEGAL_POSITION for i in invalid)


def test_no_split_at_boundary_forces_paragraphs_together():
    # H=10，p1=p2=4 行，n1@2 高3、n2@6 高2：无指令最优断段界 4（(4,8)）。
    # 在段界（p1 第 4 行后）禁止断开 ⇒ 不得在 4 断页，最优改断第 2 行后。
    sol = as_solution(solve(doc(
        10, [("p1", 4, False), ("p2", 4, False)],
        [("n1", 2, 3), ("n2", 6, 2)],
        directives=[(NO_SPLIT, "p1", 4)],
    )))
    assert sol.ending_lines == (2, 8)
    assert sol.violated_directives == ()
    assert sol.invalid_directives == ()


def test_lock_internal_on_short_paragraph_illegal():
    # 3 行段：段内任何锁定都会使某侧片段 < 2 行，全部非法。
    d = doc(10, [("p1", 3, False), ("p2", 2, False)],
            directives=[(LOCK_BREAK, "p1", 2)])
    valid, invalid = classify_directives(d)
    assert valid == ()
    assert invalid[0].reason == ILLEGAL_POSITION


def test_no_split_then_boundary_lock_still_works():
    # no_split 只管段内；段界锁定不受影响。
    sol = as_solution(solve(doc(
        10, [("p1", 5, False), ("p2", 5, False)],
        directives=[
            (NO_SPLIT, "p1", 3),
            (LOCK_BREAK, "p1", 5),
        ],
    )))
    assert sol.ending_lines[0] == 5


# ---------- 最小释放建议 ----------

def test_conflicting_locks_suggest_minimum_release():
    # H=4，单段 6 行。合法段内断点只有第 2、3、4 行后。
    # 同时锁定第 2 和第 4 行：需要三页 (2,4,6)，容量本身允许但
    # 中间片段第 3–4 行=2 行合法——构造真正冲突：锁定 2 与 3（同一页不能
    # 同时在 2、3 结束）⇒ 至少释放 1 条。
    sol = as_solution(solve(doc(
        4, [("p1", 6, False)],
        directives=[
            (LOCK_BREAK, "p1", 2),
            (LOCK_BREAK, "p1", 3),
        ],
    )))
    # 释放数量最少 = 1；释放序号 0 或 1，取录入序号序列字典序最小 ⇒ 释放 0
    assert sol.violated_directives == (0,)
    # 保留锁定 3 ⇒ 首页结束于 3
    assert sol.ending_lines[0] == 3


def test_release_tie_break_by_order_sequence():
    # 两种单条释放都可行时，选录入序号较小者。
    sol = as_solution(solve(doc(
        4, [("p1", 6, False)],
        directives=[
            (LOCK_BREAK, "p1", 3),
            (LOCK_BREAK, "p1", 2),
        ],
    )))
    # 序号 0=锁3、序号 1=锁2；释放 0（保留锁2）字典序更小
    assert sol.violated_directives == (0,)
    assert sol.ending_lines[0] == 2


def test_minimum_release_count_not_first_feasible_single():
    # 需要释放 2 条的情形：三个两两冲突的锁定。
    # H=4，单段 8 行，合法段内断点 2..6。锁定 2、3、4 三个紧邻点，
    # 一页至多含一个锁定点 ⇒ 任意两页无法容纳三个点且片段约束下，
    # 至少释放到只剩可共存的集合。
    sol = as_solution(solve(doc(
        4, [("p1", 8, False)],
        directives=[
            (LOCK_BREAK, "p1", 2),
            (LOCK_BREAK, "p1", 3),
            (LOCK_BREAK, "p1", 4),
        ],
    )))
    # 锁 2 与 4 可共存（(2,4,...) 片段均≥2）；锁 3 与二者距离仅 1 行不可共存。
    # 最小释放 1 条（释放锁 3，序号 1）。
    assert sol.violated_directives == (1,)
    assert sol.ending_lines[:2] == (2, 4)


def test_no_split_vs_lock_conflict_resolved_by_release():
    # 锁定第 3 行后，又禁止第 3 行后断开：直接矛盾，须释放其一。
    sol = as_solution(solve(doc(
        4, [("p1", 6, False)],
        directives=[
            (LOCK_BREAK, "p1", 3),
            (NO_SPLIT, "p1", 3),
        ],
    )))
    # 释放序号 0（字典序最小）⇒ 保留 no_split，回到无锁定最优 (3,6)？
    # 保留 no_split@3 ⇒ 不能断 3，最优为 (2,6)。
    assert sol.violated_directives == (0,)
    assert sol.ending_lines == (2, 6)


def test_confirmed_release_recompute_no_further_release():
    # 用户已确认释放序号 0，重算应把它标记为已确认而非再次建议。
    d = doc(
        4, [("p1", 6, False)],
        directives=[
            (LOCK_BREAK, "p1", 2),
            (LOCK_BREAK, "p1", 3),
        ],
    )
    sol = as_solution(solve(d, released_orders=frozenset({0})))
    # 锁 2 已释放、锁 3 保留：可行，且不再追加释放
    assert sol.violated_directives == (0,)
    assert sol.ending_lines[0] == 3


def test_confirmed_release_still_infeasible_appends_minimum_extra():
    # 只确认释放不足够时，求解器在其外再找最小追加释放集。
    d = doc(
        4, [("p1", 8, False)],
        directives=[
            (LOCK_BREAK, "p1", 2),
            (LOCK_BREAK, "p1", 3),
            (LOCK_BREAK, "p1", 4),
        ],
    )
    # 错误地只确认释放序号 0（锁2）：剩锁3、锁4 仍冲突（相距仅 1 行），
    # 须再释放 1 条；追加序号 1（字典序）⇒ 最终释放 (0,1)，保留锁4。
    sol = as_solution(solve(d, released_orders=frozenset({0})))
    assert sol.violated_directives == (0, 1)
    assert sol.ending_lines[0] == 4


# ---------- 原文档本身无解：不混入指令归因 ----------

def test_base_infeasible_returns_prefix_failure_without_attributing_directives():
    # H=3，p1=2 保持、p2=2：原文档本身无解（与指令无关）。
    # 即便再加一条锁定指令，仍返回最短不可行前缀，且不给出释放建议。
    failure = as_failure(solve(doc(
        3, [("p1", 2, True), ("p2", 2, False)],
        directives=[(LOCK_BREAK, "p1", 2)],  # 合法段界锁
    )))
    assert failure.paragraph_id == "p2"
    assert failure.prefix_end_line == 4


def test_base_infeasible_still_reports_invalid_directives():
    # 原文档无解时失效指令仍就地标出（它们不参与约束，也不归因）。
    failure = as_failure(solve(doc(
        3, [("p1", 2, True), ("p2", 2, False)],
        directives=[(LOCK_BREAK, "ghost", 1)],
    )))
    assert failure.paragraph_id == "p2"
    assert len(failure.invalid_directives) == 1
    assert failure.invalid_directives[0].reason == PARAGRAPH_NOT_FOUND


def test_base_infeasible_without_directives_has_empty_invalid():
    failure = as_failure(solve(doc(3, [("p1", 2, True), ("p2", 2, False)])))
    assert failure.invalid_directives == ()


# ---------- 指令不改变无指令最优解的回归 ----------

def test_redundant_lock_along_optimal_solution():
    # 锁定恰好落在无指令最优断点上：结果与无指令一致，且无需释放。
    sol = as_solution(solve(doc(
        4, [("p1", 6, False)], directives=[(LOCK_BREAK, "p1", 3)]
    )))
    assert sol.ending_lines == (3, 6)
    assert sol.squared_slack == 2
    assert sol.violated_directives == ()


def test_all_invalid_directives_equals_no_directive_solution():
    sol = as_solution(solve(doc(
        4, [("p1", 6, False)], directives=[(NO_SPLIT, "ghost", 1)]
    )))
    assert sol.ending_lines == (3, 6)
    assert len(sol.invalid_directives) == 1
    assert sol.violated_directives == ()
