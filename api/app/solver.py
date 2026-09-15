"""分页求解器。

在全部合法分页方案中，依次最小化：
1. 页数；
2. 各页剩余容量平方和；
3. 全局结束行号序列（字典序最小）。

约束模型：
- 正文每行占 1 单位容量；注记不可拆分，按其标记行计入所在页，占 height 单位。
- 段落跨页时，断点两侧均须至少 2 行。
- 「与下段保持」：本段末行与下段前两行须同页。
  由于段内两行规则已禁止在下段第 1 行之后断页（否则下段一侧仅 1 行），
  保持约束等价于禁止在本段末行（段界）断页；下段仅 1 行时该等价依然成立。
- 末段的保持标记无下段可引，按规则忽略（前缀求解时同理：
  仅当被引用的下一段已在求解范围内时才检查保持约束）。
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Paragraph:
    id: str
    lines: int
    keep_with_next: bool = False


@dataclass(frozen=True)
class Footnote:
    id: str
    marker_line: int  # 全局 1 基行号
    height: int
    order: int  # 录入序号（0 起），用于同标记行时的稳定排序


@dataclass(frozen=True)
class Document:
    capacity: int
    paragraphs: tuple[Paragraph, ...]
    footnotes: tuple[Footnote, ...]


@dataclass(frozen=True)
class Page:
    index: int  # 1 起
    start_line: int
    end_line: int
    footnotes: tuple[Footnote, ...]  # 本页注记，按 (标记行, 录入序号) 排序
    text_units: int
    footnote_units: int
    used: int
    slack: int


@dataclass(frozen=True)
class Solution:
    pages: tuple[Page, ...]
    ending_lines: tuple[int, ...]
    squared_slack: int


@dataclass(frozen=True)
class Failure:
    paragraph_index: int  # 1 起，最短不可行前缀的末段
    paragraph_id: str
    prefix_end_line: int
    footnotes: tuple[Footnote, ...]  # 前缀内全部注记，按 (标记行, 录入序号) 排序


def paragraph_spans(paragraphs: tuple[Paragraph, ...]) -> tuple[tuple[int, int], ...]:
    """每段的 [首行, 末行]（全局 1 基，闭区间）。"""
    spans: list[tuple[int, int]] = []
    start = 1
    for p in paragraphs:
        spans.append((start, start + p.lines - 1))
        start += p.lines
    return tuple(spans)


def _forbidden_breaks(
    paragraphs: tuple[Paragraph, ...], spans: tuple[tuple[int, int], ...]
) -> frozenset[int]:
    """禁止在该全局行号之后断页的位置集合（行号 < 总行数）。"""
    forbidden: set[int] = set()
    last = len(paragraphs) - 1
    for i, (p, (s, e)) in enumerate(zip(paragraphs, spans)):
        # 段内断点：两侧均须 ≥ 2 行
        for b in range(s, e):
            if b - s + 1 < 2 or e - b < 2:
                forbidden.add(b)
        # 保持约束：禁止在本段末行断页（末段无下段，不检查）
        if i < last and p.keep_with_next:
            forbidden.add(e)
    return frozenset(forbidden)


def _solve_whole(doc: Document) -> Solution | None:
    """对整篇（或某个前缀子篇）求最优分页；无解返回 None。"""
    spans = paragraph_spans(doc.paragraphs)
    total = spans[-1][1]
    forbidden = _forbidden_breaks(doc.paragraphs, spans)

    # note_prefix[x] = 标记行 ≤ x 的注记高度和
    note_prefix = [0] * (total + 1)
    for f in doc.footnotes:
        note_prefix[f.marker_line] += f.height
    for x in range(1, total + 1):
        note_prefix[x] += note_prefix[x - 1]

    def load(a: int, b: int) -> int:
        """页 (a, b] 的占用：正文行数 + 页内注记高度和。"""
        return (b - a) + note_prefix[b] - note_prefix[a]

    # best[b] = 放置第 b+1..total 行的最优 (页数, 剩余容量平方和)
    best: list[tuple[int, int] | None] = [None] * (total + 1)
    best[total] = (0, 0)
    nxt: list[int | None] = [None] * (total + 1)
    for b in range(total - 1, -1, -1):
        winner: tuple[int, int] | None = None
        winner_bp: int | None = None
        for bp in range(b + 1, total + 1):
            if bp < total and bp in forbidden:
                continue
            used = load(b, bp)
            if used > doc.capacity:
                break  # 占用随 bp 单调不减，可提前终止
            tail = best[bp]
            if tail is None:
                continue
            cand = (tail[0] + 1, tail[1] + (doc.capacity - used) ** 2)
            # bp 递增枚举，严格小于才替换 ⇒ 同值时保留最小断点，
            # 重建时即得字典序最小的结束行号序列
            if winner is None or cand < winner:
                winner, winner_bp = cand, bp
        best[b] = winner
        nxt[b] = winner_bp

    if best[0] is None:
        return None

    endings: list[int] = []
    b = 0
    while b < total:
        bp = nxt[b]
        assert bp is not None
        endings.append(bp)
        b = bp

    pages: list[Page] = []
    prev = 0
    squared = 0
    for i, end in enumerate(endings, start=1):
        page_notes = tuple(sorted(
            (f for f in doc.footnotes if prev < f.marker_line <= end),
            key=lambda f: (f.marker_line, f.order),
        ))
        text_units = end - prev
        note_units = sum(f.height for f in page_notes)
        used = text_units + note_units
        slack = doc.capacity - used
        squared += slack * slack
        pages.append(Page(i, prev + 1, end, page_notes, text_units, note_units, used, slack))
        prev = end
    return Solution(tuple(pages), tuple(endings), squared)


def solve(doc: Document) -> Solution | Failure:
    """求解整篇；若无解，定位最短不可行前缀并返回其末段与前缀内注记。

    不可行性随前缀长度单调（前缀无解则更长前缀亦无解：更长前缀的任一合法
    分页截断到该前缀即得该前缀的合法分页），故整篇无解时必存在唯一最短
    不可行前缀，顺序扫描即可。
    """
    whole = _solve_whole(doc)
    if whole is not None:
        return whole

    spans = paragraph_spans(doc.paragraphs)
    for k in range(1, len(doc.paragraphs) + 1):
        end_line = spans[k - 1][1]
        prefix_notes = tuple(f for f in doc.footnotes if f.marker_line <= end_line)
        sub = Document(doc.capacity, doc.paragraphs[:k], prefix_notes)
        if _solve_whole(sub) is None:
            ordered = tuple(sorted(prefix_notes, key=lambda f: (f.marker_line, f.order)))
            return Failure(k, doc.paragraphs[k - 1].id, end_line, ordered)
    raise AssertionError("整篇无解时必存在不可行前缀")
