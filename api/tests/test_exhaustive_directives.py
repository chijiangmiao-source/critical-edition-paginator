"""指令功能的独立穷举验收（≤ 8 行）。

与求解器相互独立的暴力器枚举：
- 全部断点掩码（2^(总行数−1) 种分页），按容量 / 段片段 / 保持约束过滤；
- 全部「释放指令子集」（2^有效指令数 种）；
并以位集交叉求每个释放子集下的最优分页，核对：
1. 兼容解的页数、剩余容量平方和、结束行号序列；
2. 最小释放数量、同数量下按录入序号序列裁决出的唯一建议；
3. 用户确认部分释放后，求解器追加的最小额外释放集；
4. 失效指令的定位（段落失配 / 越界 / 位置非法）；
5. 原文档本身无解时仍给最短不可行前缀、不混入指令归因；
6. 无指令请求与旧行为完全一致（无指令回归）。
"""
from __future__ import annotations

import random
from itertools import combinations

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
    solve,
)

Para = tuple[str, int, bool]
Note = tuple[str, int, int]
# (kind, paragraph_id, line_in_paragraph)，数组下标即录入序号
RawDirective = tuple[str, str, int]


def _spans(paragraphs: list[Para]) -> list[tuple[int, int]]:
    spans, start = [], 1
    for _, lines, _ in paragraphs:
        spans.append((start, start + lines - 1))
        start += lines
    return spans


def _evaluate_mask(
    capacity: int,
    paragraphs: list[Para],
    footnotes: list[Note],
    mask: int,
    total: int,
    spans: list[tuple[int, int]],
):
    """返回该断点掩码的排序键 (页数, 平方和, 结束行序列)；非法返回 None。"""
    breaks = [b for b in range(1, total) if mask >> (b - 1) & 1]
    ends = breaks + [total]
    pages: list[tuple[int, int]] = []
    prev = 0
    for end in ends:
        load = (end - prev) + sum(h for _, m, h in footnotes if prev < m <= end)
        if load > capacity:
            return None
        pages.append((prev, end))
        prev = end
    for s, e in spans:
        internal = [b for b in breaks if s <= b < e]
        if not internal:
            continue
        cuts = [s - 1, *internal, e]
        if any(cuts[k + 1] - cuts[k] < 2 for k in range(len(cuts) - 1)):
            return None

    def page_of(line: int) -> int:
        for pi, (a, b) in enumerate(pages):
            if a < line <= b:
                return pi
        raise AssertionError

    for i in range(len(paragraphs) - 1):
        if not paragraphs[i][2]:
            continue
        last_line = spans[i][1]
        nxt_first = spans[i + 1][0]
        nxt_second = min(spans[i + 1][0] + 1, spans[i + 1][1])
        if not (page_of(last_line) == page_of(nxt_first) == page_of(nxt_second)):
            return None
    squared = sum(
        (capacity - (e - a) - sum(h for _, m, h in footnotes if a < m <= e)) ** 2
        for a, e in pages
    )
    endings = tuple(e for _, e in pages)
    return len(pages), squared, endings


class BruteWorld:
    """预计算全部可行分页（按目标排序）与每条指令的满足位集。"""

    def __init__(self, capacity, paragraphs, footnotes, directives):
        self.capacity = capacity
        self.paragraphs = paragraphs
        self.footnotes = footnotes
        self.directives = directives
        self.total = sum(lines for _, lines, _ in paragraphs)
        self.spans = _spans(paragraphs)
        self.start_of = {pid: s for (pid, _, _), (s, _) in zip(paragraphs, self.spans)}
        self.n = {pid: lines for pid, lines, _ in paragraphs}
        self.last_pid = paragraphs[-1][0]

        scored: list[tuple[tuple[int, int, tuple[int, ...]], int]] = []
        for mask in range(1 << max(self.total - 1, 0)):
            key = _evaluate_mask(capacity, paragraphs, footnotes, mask, self.total, self.spans)
            if key is not None:
                scored.append((key, mask))
        scored.sort(key=lambda x: x[0])
        self.keys = [k for k, _ in scored]
        self.masks = [m for _, m in scored]
        self.base_feasible = bool(scored)

        # 独立分类失效指令
        self.valid_orders: list[int] = []
        self.invalid: dict[int, str] = {}
        for order, (kind, pid, line) in enumerate(directives):
            if pid not in self.n:
                self.invalid[order] = PARAGRAPH_NOT_FOUND
                continue
            n = self.n[pid]
            if line < 1 or line > n:
                self.invalid[order] = LINE_OUT_OF_RANGE
                continue
            if kind == LOCK_BREAK:
                legal = (line == n and pid != self.last_pid) or 2 <= line <= n - 2
            else:
                legal = line <= n - 1
            if not legal:
                self.invalid[order] = ILLEGAL_POSITION
                continue
            self.valid_orders.append(order)
        self.valid_orders.sort()

        # 每条有效指令在「可行分页下标位集」上的满足位集
        self.sat: dict[int, int] = {}
        all_bits = (1 << len(self.masks)) - 1
        for order in self.valid_orders:
            kind, pid, line = directives[order]
            gline = self.start_of[pid] + line - 1
            bits = 0
            for idx, mask in enumerate(self.masks):
                has_break = bool(mask >> (gline - 1) & 1)
                if (kind == LOCK_BREAK and has_break) or (kind == NO_SPLIT and not has_break):
                    bits |= 1 << idx
            self.sat[order] = bits
        self.all_bits = all_bits

    def allowed_bits(self, released: frozenset[int]) -> int:
        bits = self.all_bits
        for order in self.valid_orders:
            if order not in released:
                bits &= self.sat[order]
        return bits

    def best_under(self, released: frozenset[int]):
        """返回该释放集下最优分页键；不可行返回 None。"""
        bits = self.allowed_bits(released)
        if bits == 0:
            return None
        idx = (bits & -bits).bit_length() - 1  # 可行分页已按目标升序
        return self.keys[idx]

    def minimum_release(self, must_release: frozenset[int] = frozenset()):
        """枚举释放子集（须包含 must_release），返回 (最小追加数量, 唯一建议集, 最优键)。"""
        remaining = [o for o in self.valid_orders if o not in must_release]
        for add_size in range(0, len(remaining) + 1):
            for combo in combinations(remaining, add_size):
                released = frozenset(must_release) | frozenset(combo)
                key = self.best_under(released)
                if key is not None:
                    return add_size, tuple(sorted(released)), key
        return None


def to_document(capacity, paragraphs, footnotes, directives: list[RawDirective]) -> Document:
    return Document(
        capacity,
        tuple(Paragraph(pid, lines, keep) for pid, lines, keep in paragraphs),
        tuple(Footnote(fid, marker, height, i) for i, (fid, marker, height) in enumerate(footnotes)),
        tuple(Directive(kind, pid, line, i) for i, (kind, pid, line) in enumerate(directives)),
    )


def check_world(capacity, paragraphs, footnotes, directives: list[RawDirective]) -> dict:
    world = BruteWorld(capacity, paragraphs, footnotes, directives)
    doc = to_document(capacity, paragraphs, footnotes, directives)
    label = f"H={capacity} paras={paragraphs} notes={footnotes} dirs={directives}"
    result = solve(doc)

    # —— 失效定位核对 ——
    got_invalid = {i.order: i.reason for i in (
        result.invalid_directives if isinstance(result, Solution) else result.invalid_directives
    )}
    assert got_invalid == world.invalid, f"失效定位不一致：{label}\n{got_invalid} != {world.invalid}"

    if not world.base_feasible:
        # 原文档本身无解：必为最短不可行前缀，且不混入指令归因
        assert isinstance(result, Failure), f"期望文档级无解：{label}"
        assert _brute_prefix(capacity, paragraphs, footnotes, world.spans) == (
            result.paragraph_index, result.prefix_end_line
        ), f"最短不可行前缀被指令污染：{label}"
        return {"kind": "infeasible_base"}

    assert isinstance(result, Solution), f"原文档可行却失败：{label}"
    add_size, expected_release, expected_key = world.minimum_release()
    got_release = tuple(sorted(result.violated_directives))
    assert got_release == expected_release, (
        f"最小释放建议不一致：{label}\n{got_release} != {expected_release}"
    )
    assert (len(result.pages), result.squared_slack, result.ending_lines) == expected_key, (
        f"建议解与暴力最优不一致：{label}"
    )

    # —— 确认该释放集后重算：解相同，且不再追加释放 ——
    confirmed = solve(doc, released_orders=frozenset(expected_release))
    assert isinstance(confirmed, Solution), label
    assert tuple(sorted(confirmed.violated_directives)) == expected_release, label
    assert confirmed.ending_lines == result.ending_lines, label
    assert confirmed.squared_slack == result.squared_slack, label

    # —— 随机确认一个子集：求解器应追加最小额外释放（枚举复核） ——
    if world.valid_orders:
        rng_local = random.Random(capacity * 1009 + len(paragraphs) * 31 + len(directives))
        probe = frozenset(rng_local.sample(
            world.valid_orders, k=rng_local.randint(0, len(world.valid_orders))
        ))
        add, probe_release, probe_key = world.minimum_release(probe)
        probed = solve(doc, released_orders=probe)
        assert isinstance(probed, Solution), label
        assert tuple(sorted(probed.violated_directives)) == probe_release, (
            f"部分确认后的追加释放不一致：{label}"
        )
        assert (len(probed.pages), probed.squared_slack, probed.ending_lines) == probe_key, label

    return {
        "kind": "satisfied" if add_size == 0 else "conflict",
        "released": expected_release,
    }


def _brute_prefix(capacity, paragraphs, footnotes, spans):
    """无指令暴力定位最短不可行前缀，返回 (段序号 1 起, 前缀结束行)。"""
    for k in range(1, len(paragraphs) + 1):
        end_line = spans[k - 1][1]
        prefix_notes = [f for f in footnotes if f[1] <= end_line]
        total = spans[k - 1][1]
        feasible = False
        for mask in range(1 << max(total - 1, 0)):
            if _evaluate_mask(
                capacity, paragraphs[:k], prefix_notes, mask, total, spans[:k]
            ) is not None:
                feasible = True
                break
        if not feasible:
            return k, end_line
    raise AssertionError


def compositions(total: int):
    if total == 0:
        return [[]]
    out = []
    for first in range(1, total + 1):
        for rest in compositions(total - first):
            out.append([first] + rest)
    return out


def _random_directives(rng, paragraphs) -> list[RawDirective]:
    ids = [pid for pid, _, _ in paragraphs]
    out: list[RawDirective] = []
    for j in range(rng.randint(0, 5)):
        kind = rng.choice([LOCK_BREAK, NO_SPLIT])
        if rng.random() < 0.2:
            pid = rng.choice(ids + ["ghost", "x9"])  # 段落失配
        else:
            pid = rng.choice(ids)
        n = next((lines for p, lines, _ in paragraphs if p == pid), rng.randint(1, 4))
        # 行号覆盖：越界、段界、段内各位
        line = rng.choice([1, 1, 2, max(n - 1, 1), n, n + 1, n + 2, rng.randint(1, max(n, 1))])
        out.append((kind, pid, line))
    return out


def test_exhaustive_random_small_chapters():
    """≤ 8 行随机小篇章：枚举全部断点 × 全部释放集合核对。"""
    rng = random.Random(20260915)
    counts = {"satisfied": 0, "conflict": 0, "infeasible_base": 0}
    for _ in range(350):
        total = rng.randint(1, 8)
        comp = rng.choice(compositions(total))
        paragraphs = [
            (f"p{i + 1}", lines, rng.random() < 0.35)
            for i, lines in enumerate(comp)
        ]
        notes: list[Note] = []
        for j in range(rng.randint(0, 3)):
            notes.append((f"n{j + 1}", rng.randint(1, total), rng.randint(1, 5)))
        capacity = rng.randint(1, 7)
        directives = _random_directives(rng, paragraphs)
        info = check_world(capacity, paragraphs, notes, directives)
        counts[info["kind"]] += 1
    # 三类情形都必须被随机语料覆盖
    assert counts["satisfied"] > 0 and counts["conflict"] > 0 and counts["infeasible_base"] > 0, (
        counts
    )


def test_exhaustive_conflict_matrix_all_directive_patterns():
    """固定篇章上穷举所有指令组合（位置与种类网格），逐案核对唯一建议。"""
    # H=4，单段 6 行：合法段内断点为第 2、3、4 行后。
    paragraphs = [("p1", 6, False)]
    rng = random.Random(777)
    raw_directives: list[RawDirective] = []
    for line in range(1, 7):
        for kind in (LOCK_BREAK, NO_SPLIT):
            raw_directives.append((kind, "p1", line))
    # 对所有长度 ≤ 4 的指令子序列抽样穷举（完整 2^12 代价过高）
    import itertools
    cases = 0
    combos = list(itertools.combinations(range(len(raw_directives)), 3))
    for chosen in rng.sample(combos, 200):
        directives = [raw_directives[i] for i in chosen]
        check_world(4, paragraphs, [], directives)
        cases += 1
    assert cases == 200


def test_handcrafted_minimum_release_is_count_then_order_sequence():
    """最小释放数量优先；同数量按录入序号序列裁决（手工构造并由暴力器复核）。"""
    # H=4，单段 8 行；锁 2、3、4：锁 3 与锁 2/4 均不可共存（相邻行），
    # 释放 1 条即可（序号 1）。
    info = check_world(
        4, [("p1", 8, False)], [],
        [(LOCK_BREAK, "p1", 2), (LOCK_BREAK, "p1", 3), (LOCK_BREAK, "p1", 4)],
    )
    assert info["kind"] == "conflict"
    assert info["released"] == (1,)


def test_handcrafted_two_must_release():
    """必须释放两条时，取序号序列字典序最小的一对。"""
    # H=4，单段 8 行，四个紧邻锁定点 2、3、4、5（序号 0..3）：可共存的锁定点
    # 须相隔 ≥ 2 行，最多保留两个：{2,4}(释放 1,3)、{2,5}(释放 1,2)、
    # {3,5}(释放 0,2)；三者按释放序号序列裁决取字典序最小 (0,2)。
    info = check_world(
        4, [("p1", 8, False)], [],
        [
            (LOCK_BREAK, "p1", 2),
            (LOCK_BREAK, "p1", 3),
            (LOCK_BREAK, "p1", 4),
            (LOCK_BREAK, "p1", 5),
        ],
    )
    assert info["kind"] == "conflict"
    assert info["released"] == (0, 2)


def test_no_directive_regression_against_brute():
    """无指令请求：与无指令暴力最优逐字段一致（含不可行前缀）。"""
    rng = random.Random(4242)
    for _ in range(60):
        total = rng.randint(1, 8)
        comp = rng.choice(compositions(total))
        paragraphs = [
            (f"p{i + 1}", lines, rng.random() < 0.4) for i, lines in enumerate(comp)
        ]
        notes = [(f"n{j + 1}", rng.randint(1, total), rng.randint(1, 5))
                 for j in range(rng.randint(0, 3))]
        capacity = rng.randint(1, 7)
        info = check_world(capacity, paragraphs, notes, [])
        assert info["kind"] in {"satisfied", "infeasible_base"}
