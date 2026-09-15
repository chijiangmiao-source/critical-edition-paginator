"""穷举核对：对不超过 12 行的文档，枚举全部合法分页并与求解器比对。

暴力器直接按题面语义实现（不做保持约束的等价归约），与求解器相互独立：
- 逐一枚举断点子集；
- 逐页检查容量（正文行数 + 页内注记高度和 ≤ H）；
- 段被拆分后，其在每一页上的片段均须 ≥ 2 行；
- 保持约束直接检查「本段末行与下段前两行同页」；
- 目标依次为 (页数, 剩余容量平方和, 结束行号序列字典序)。
"""
from __future__ import annotations

import random

from app.solver import Document, Failure, Footnote, Paragraph, solve

Para = tuple[str, int, bool]  # (id, lines, keep_with_next)
Note = tuple[str, int, int]  # (id, marker_line, height)


def _spans(paragraphs: list[Para]) -> list[tuple[int, int]]:
    spans, start = [], 1
    for _, lines, _ in paragraphs:
        spans.append((start, start + lines - 1))
        start += lines
    return spans


def brute_optimal(capacity: int, paragraphs: list[Para], footnotes: list[Note]):
    """返回 (结束行号序列, 剩余容量平方和)；无解返回 None。"""
    total = sum(lines for _, lines, _ in paragraphs)
    spans = _spans(paragraphs)

    best: tuple[tuple[int, int, tuple[int, ...]], tuple[int, ...], int] | None = None
    for mask in range(1 << max(total - 1, 0)):
        breaks = [b for b in range(1, total) if mask >> (b - 1) & 1]
        ends = breaks + [total]
        pages: list[tuple[int, int]] = []
        prev = 0
        ok = True
        for end in ends:
            load = (end - prev) + sum(h for _, m, h in footnotes if prev < m <= end)
            if load > capacity:
                ok = False
                break
            pages.append((prev, end))
            prev = end
        if not ok:
            continue
        # 段被拆分后，其在每一页上的片段均须 ≥ 2 行（未拆分的段不受限）
        for s, e in spans:
            internal = [b for b in breaks if s <= b < e]
            if not internal:
                continue
            cuts = [s - 1, *internal, e]
            if any(cuts[k + 1] - cuts[k] < 2 for k in range(len(cuts) - 1)):
                ok = False
                break
        if not ok:
            continue
        # 保持约束：本段末行与下段前两行同页（末段无下段，不检查）
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
                ok = False
                break
        if not ok:
            continue
        squared = sum((capacity - (e - a) - sum(h for _, m, h in footnotes if a < m <= e)) ** 2
                      for a, e in pages)
        endings = tuple(e for _, e in pages)
        key = (len(pages), squared, endings)
        if best is None or key < best[0]:
            best = (key, endings, squared)
    if best is None:
        return None
    return best[1], best[2]


def to_document(capacity: int, paragraphs: list[Para], footnotes: list[Note]) -> Document:
    return Document(
        capacity,
        tuple(Paragraph(pid, lines, keep) for pid, lines, keep in paragraphs),
        tuple(Footnote(fid, marker, height, i) for i, (fid, marker, height) in enumerate(footnotes)),
    )


def check_case(capacity: int, paragraphs: list[Para], footnotes: list[Note]) -> None:
    doc = to_document(capacity, paragraphs, footnotes)
    result = solve(doc)
    expected = brute_optimal(capacity, paragraphs, footnotes)
    label = f"H={capacity} paragraphs={paragraphs} footnotes={footnotes}"
    if expected is None:
        assert isinstance(result, Failure), f"期望无解：{label}"
        _check_failure_prefix(capacity, paragraphs, footnotes, result, label)
        return
    endings, squared = expected
    assert not isinstance(result, Failure), f"期望可行：{label}"
    assert result.ending_lines == endings, f"结束行号序列不一致：{label}"
    assert result.squared_slack == squared, f"剩余容量平方和不一致：{label}"
    # 页结构与结束行号一致
    assert tuple(p.end_line for p in result.pages) == endings
    assert sum(p.slack * p.slack for p in result.pages) == squared
    # 注记按标记行落在对应页，页内按 (标记行, 录入序号) 排序
    for page in result.pages:
        expected_notes = sorted(
            (f for f in footnotes if page.start_line <= f[1] <= page.end_line),
            key=lambda f: (f[1], footnotes.index(f)),
        )
        assert tuple(f.id for f in page.footnotes) == tuple(f[0] for f in expected_notes)


def _check_failure_prefix(capacity, paragraphs, footnotes, failure: Failure, label: str) -> None:
    """无解时：暴力确认该前缀为最短不可行前缀，且注记列表正确。"""
    spans = _spans(paragraphs)
    first_bad = None
    for k in range(1, len(paragraphs) + 1):
        end_line = spans[k - 1][1]
        prefix_notes = [f for f in footnotes if f[1] <= end_line]
        if brute_optimal(capacity, paragraphs[:k], prefix_notes) is None:
            first_bad = k
            break
    assert first_bad is not None, f"整篇无解但所有前缀均可行：{label}"
    assert failure.paragraph_index == first_bad, f"最短不可行前缀不一致：{label}"
    assert failure.paragraph_id == paragraphs[first_bad - 1][0]
    assert failure.prefix_end_line == spans[first_bad - 1][1]
    prefix_notes = [f for f in footnotes if f[1] <= failure.prefix_end_line]
    ordered = sorted(prefix_notes, key=lambda f: (f[1], footnotes.index(f)))
    assert tuple(f.id for f in failure.footnotes) == tuple(f[0] for f in ordered)


def compositions(total: int) -> list[list[int]]:
    if total == 0:
        return [[]]
    out = []
    for first in range(1, total + 1):
        for rest in compositions(total - first):
            out.append([first] + rest)
    return out


def test_exhaustive_without_footnotes():
    """≤ 7 行、无注记：全部分段 × 全部/抽样保持标记 × H ∈ 1..5。"""
    rng = random.Random(20260915)
    for total in range(1, 8):
        for comp in compositions(total):
            k = len(comp)
            masks = range(1 << (k - 1)) if k <= 4 else rng.sample(range(1 << (k - 1)), 8)
            for mask in masks:
                paragraphs = [
                    (f"p{i + 1}", lines, bool(mask >> i & 1))
                    for i, lines in enumerate(comp)
                ]
                for capacity in range(1, 6):
                    check_case(capacity, paragraphs, [])


def test_exhaustive_with_footnotes():
    """≤ 12 行、含注记：固定种子的随机文档，覆盖可行与不可行。"""
    rng = random.Random(20260915)
    feasible = infeasible = 0
    for _ in range(400):
        total = rng.randint(1, 12)
        comp = rng.choice(compositions(total))
        paragraphs = [
            (f"p{i + 1}", lines, rng.random() < 0.4)
            for i, lines in enumerate(comp)
        ]
        notes: list[Note] = []
        for j in range(rng.randint(0, 4)):
            notes.append((f"n{j + 1}", rng.randint(1, total), rng.randint(1, 6)))
        capacity = rng.randint(1, 8)
        check_case(capacity, paragraphs, notes)
        if brute_optimal(capacity, paragraphs, notes) is None:
            infeasible += 1
        else:
            feasible += 1
    # 确保两类结果都被覆盖
    assert feasible > 0 and infeasible > 0


def test_exhaustive_keep_only_checked_within_prefix():
    """保持约束仅在下一段已进入前缀时检查：构造末段保持标记「救回」前缀的用例。

    p1 保持、p2 一行、H=2：前两段不可行（p1 末行须与 p2 同页，3 行 > 2）。
    若错误地在求解前缀时检查 p2 的保持标记，会把更长的可行前缀误判为不可行。
    """
    paragraphs = [("p1", 2, True), ("p2", 1, True), ("p3", 2, False)]
    # 整篇：p1 保持（断 2 禁）、p2 保持（断 3 禁）⇒ [1..5] 需 5 > 2，不可行；
    # 但前缀 [p1] 可行、[p1,p2] 不可行 ⇒ 最短不可行前缀末段为 p2。
    result = solve(to_document(2, paragraphs, []))
    assert isinstance(result, Failure)
    assert result.paragraph_id == "p2"
    assert result.prefix_end_line == 3
    assert result.footnotes == ()
