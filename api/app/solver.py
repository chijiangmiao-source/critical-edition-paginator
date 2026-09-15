"""分页求解器。

在全部合法分页方案中，依次最小化：
1. 页数；
2. 各页剩余容量平方和；
3. 全局结束行号序列（字典序最小）。

约束模型：
- 正文每行占 1 单位容量；注记不可拆分，按其标记行计入所在页，占 height 单位。
- 段落被拆分后，其在每一页上的片段（段首至首个断点、相邻断点之间、
  末个断点至段尾）均须 ≥ 2 行；未被拆分的段不受此限。
- 「与下段保持」：本段末行与下段前两行须同页。
  由于片段规则已禁止在下段第 1 行之后断页（否则下段首片段仅 1 行），
  保持约束等价于禁止在本段末行（段界）断页；下段仅 1 行时该等价依然成立。
- 末段的保持标记无下段可引，按规则忽略（前缀求解时同理：
  仅当被引用的下一段已在求解范围内时才检查保持约束）。

人工版式指令（软约束，违反即「释放」）：
- ``lock_break``（必须保留）：施于段界（非末段的末行之后）或合法段内行位
  （段内第 i 行后，2 ≤ i ≤ 行数−2，保证两侧片段均 ≥ 2 行），要求该位置必须断页；
  某页跨过该行即违反该指令。
- ``no_split``（禁止断开）：施于段内行位（1 ≤ i ≤ 行数−1），页末断点落在该行即违反。
- 指令以 (段落 id, 段内行号) 定位；段落 id 失配、行号越界、位置不允许该类操作时，
  该指令判为失效（不参与约束）并就地标出，其余指令照常生效。

释放裁决（原文档可分页但全部指令不能同时满足时）：
- 每条指令在任一具体分页下是否被违反是确定的，且违反责任可按页**加法**分摊
  （锁定行只可能落在唯一一个页的开区间内；禁断只可能在唯一一个页末被违反），
  故最小释放问题并入同一次动态规划，目标五元组依次为：
  ① 被释放（违反）指令数；
  ② 同数下被释放指令录入序号序列的字典序（以位权 Σ2^(m−1−rank) 最大实现）；
  ③ 页数；④ 剩余容量平方和；⑤ 结束行号序列（DP 重建保字典序最小）。
  一次 O(总行数²) DP 即得唯一建议，无需指数枚举。
- 用户已确认释放的指令不再计入目标（沉没成本），求解器只在其外最小化追加释放。
"""
from __future__ import annotations

from bisect import bisect_left, bisect_right
from dataclasses import dataclass, replace

LOCK_BREAK = "lock_break"
NO_SPLIT = "no_split"

# 失效原因（稳定机器码，界面据此文案化）
PARAGRAPH_NOT_FOUND = "paragraph_not_found"
LINE_OUT_OF_RANGE = "line_out_of_range"
ILLEGAL_POSITION = "illegal_position"


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
class Directive:
    kind: str  # LOCK_BREAK / NO_SPLIT
    paragraph_id: str
    line_in_paragraph: int  # 段内 1 基行号；lock 段界时取段落末行
    order: int  # 录入序号（0 起，请求数组下标）


@dataclass(frozen=True)
class InvalidDirective:
    order: int
    kind: str
    paragraph_id: str
    line_in_paragraph: int
    reason: str  # PARAGRAPH_NOT_FOUND / LINE_OUT_OF_RANGE / ILLEGAL_POSITION


@dataclass(frozen=True)
class Document:
    capacity: int
    paragraphs: tuple[Paragraph, ...]
    footnotes: tuple[Footnote, ...]
    directives: tuple[Directive, ...] = ()


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
    # 本次求解中被违反（释放）的有效指令录入序号，不含用户已预先确认释放者；
    # 空 = 全部未预先释放的有效指令均满足。
    violated_directives: tuple[int, ...] = ()
    # 失效指令（段落失配 / 行越界 / 位置非法），不参与求解
    invalid_directives: tuple[InvalidDirective, ...] = ()


@dataclass(frozen=True)
class Failure:
    paragraph_index: int  # 1 起，最短不可行前缀的末段
    paragraph_id: str
    prefix_end_line: int
    footnotes: tuple[Footnote, ...]  # 前缀内全部注记，按 (标记行, 录入序号) 排序
    invalid_directives: tuple[InvalidDirective, ...] = ()


def paragraph_spans(paragraphs: tuple[Paragraph, ...]) -> tuple[tuple[int, int], ...]:
    """每段的 [首行, 末行]（全局 1 基，闭区间）。"""
    spans: list[tuple[int, int]] = []
    start = 1
    for p in paragraphs:
        spans.append((start, start + p.lines - 1))
        start += p.lines
    return tuple(spans)


def _keep_forbidden_breaks(
    paragraphs: tuple[Paragraph, ...], spans: tuple[tuple[int, int], ...]
) -> frozenset[int]:
    """保持约束禁止的断点：段末行之后（末段无下段，不检查）。"""
    last = len(paragraphs) - 1
    return frozenset(
        spans[i][1] for i in range(last) if paragraphs[i].keep_with_next
    )


def classify_directives(
    doc: Document,
) -> tuple[tuple[Directive, ...], tuple[InvalidDirective, ...]]:
    """把指令分为有效 / 失效两类。

    有效位置：
    - lock_break：段界（非末段末行之后），或段内第 i 行后且 2 ≤ i ≤ 行数−2；
    - no_split：段内第 i 行后且 1 ≤ i ≤ 行数−1。
    其余（段落 id 失配、行号越界、位置不允许该类操作）判失效，原样保留供界面标出。
    """
    index_by_id = {p.id: i for i, p in enumerate(doc.paragraphs)}
    valid: list[Directive] = []
    invalid: list[InvalidDirective] = []
    last_index = len(doc.paragraphs) - 1
    for d in doc.directives:
        idx = index_by_id.get(d.paragraph_id)
        if idx is None:
            invalid.append(InvalidDirective(
                d.order, d.kind, d.paragraph_id, d.line_in_paragraph, PARAGRAPH_NOT_FOUND
            ))
            continue
        n = doc.paragraphs[idx].lines
        line = d.line_in_paragraph
        if line < 1 or line > n:
            invalid.append(InvalidDirective(
                d.order, d.kind, d.paragraph_id, line, LINE_OUT_OF_RANGE
            ))
            continue
        if d.kind == LOCK_BREAK:
            is_boundary = line == n and idx < last_index
            is_internal = 2 <= line <= n - 2
            if not (is_boundary or is_internal):
                invalid.append(InvalidDirective(
                    d.order, d.kind, d.paragraph_id, line, ILLEGAL_POSITION
                ))
                continue
        elif d.kind == NO_SPLIT:
            if line > n - 1:
                invalid.append(InvalidDirective(
                    d.order, d.kind, d.paragraph_id, line, ILLEGAL_POSITION
                ))
                continue
        else:  # 理论不可达：请求层已校验 kind 取值
            invalid.append(InvalidDirective(
                d.order, d.kind, d.paragraph_id, line, ILLEGAL_POSITION
            ))
            continue
        valid.append(d)
    return tuple(valid), tuple(invalid)


def _solve_whole(
    doc: Document,
    valid: tuple[Directive, ...] = (),
    prereleased: frozenset[int] = frozenset(),
) -> Solution | None:
    """对整篇（或某个前缀子篇）在硬约束与有效指令下求最优分页；无解返回 None。

    硬约束：容量、段片段 ≥ 2 行、与下段保持。指令为软约束：违反即计入释放，
    目标五元组 (释放数, −释放位权, 页数, 剩余平方和) 依次最小化；
    结束行号序列由「同值取最小断点」的重建保证字典序最小。

    prereleased 为用户已确认释放的序号：不参与约束、也不计入本次目标。
    """
    spans = paragraph_spans(doc.paragraphs)
    total = spans[-1][1]
    keep_forbidden = _keep_forbidden_breaks(doc.paragraphs, spans)
    para_of = [0] * (total + 1)
    for idx, (s, e) in enumerate(spans):
        for line in range(s, e + 1):
            para_of[line] = idx

    # note_prefix[x] = 标记行 ≤ x 的注记高度和
    note_prefix = [0] * (total + 1)
    for f in doc.footnotes:
        note_prefix[f.marker_line] += f.height
    for x in range(1, total + 1):
        note_prefix[x] += note_prefix[x - 1]

    def load(a: int, b: int) -> int:
        """页 (a, b] 的占用：正文行数 + 页内注记高度和。"""
        return (b - a) + note_prefix[b] - note_prefix[a]

    # 参与本次裁决的有效指令（按录入序号升序），rank 用于位权：
    # 同释放数下，录入序号序列字典序最小 ⇔ 位权 Σ2^(m−1−rank) 最大。
    active = sorted((d for d in valid if d.order not in prereleased), key=lambda d: d.order)
    rank_of = {d.order: j for j, d in enumerate(active)}
    m = len(active)
    start_by_id = {p.id: spans[i][0] for i, p in enumerate(doc.paragraphs)}

    # 锁定指令：(全局行号, 位权)；页 (a,b] 跨过 a < r < b 的锁定行即违反。
    # 禁断指令：页末 b（b < 总行）落在其行上即违反；同一行可挂多条。
    lock_pairs: list[tuple[int, int]] = []
    split_weight_at: dict[int, int] = {}
    for d in active:
        gline = start_by_id[d.paragraph_id] + d.line_in_paragraph - 1
        weight = 1 << (m - 1 - rank_of[d.order])
        if d.kind == LOCK_BREAK:
            lock_pairs.append((gline, weight))
        else:
            split_weight_at[gline] = split_weight_at.get(gline, 0) + weight
    # 二分查找要求按全局行号有序（同一行可挂多条锁定，权重相邻累加）
    lock_pairs.sort(key=lambda x: x[0])
    lock_lines = [g for g, _ in lock_pairs]
    lock_weights = [w for _, w in lock_pairs]

    def lock_penalty(a: int, b: int) -> int:
        """本页开区间 (a, b) 内被跨过的锁定行：对应指令位权之和。"""
        lo = bisect_right(lock_lines, a)
        hi = bisect_left(lock_lines, b)
        if hi <= lo:
            return 0
        return sum(lock_weights[lo:hi])

    # best[b] = 放置第 b+1..total 行的最优代价五元组（后四项），计数由位权位推出，
    # 显式保留 (违反数, −位权, 页数, 平方和)。
    best: list[tuple[int, int, int, int] | None] = [None] * (total + 1)
    best[total] = (0, 0, 0, 0)
    nxt: list[int | None] = [None] * (total + 1)
    for b in range(total - 1, -1, -1):
        # 若断点 b 落在段内（切开该段），则本页合上该段时末片段须 ≥ 2 行
        open_para_end = -1
        if b >= 1:
            si, ei = spans[para_of[b]]
            if si <= b < ei:
                open_para_end = ei
        winner: tuple[int, int, int, int] | None = None
        winner_bp: int | None = None
        for bp in range(b + 1, total + 1):
            used = load(b, bp)
            if used > doc.capacity:
                break  # 占用随 bp 单调不减，可提前终止
            tail = best[bp]
            if tail is None:
                continue
            if bp < total:
                if bp in keep_forbidden:
                    continue
                sj, ej = spans[para_of[bp]]
                if sj <= bp < ej:
                    # 段内断点：本页收尾的片段（首片段或中间片段）须 ≥ 2 行
                    if bp - max(b, sj - 1) < 2:
                        continue
            if open_para_end >= 0 and bp >= open_para_end:
                # 断点 b 所在段在本页结束：末片段须 ≥ 2 行
                if open_para_end - b < 2:
                    continue
            # 本页造成的指令违反：跨过的锁定行 + 落在页末的禁断行。
            # 每条指令占独立的 rank 位，位权和即按位或，置位位数即违反条数。
            v_weight = lock_penalty(b, bp)
            if bp < total:
                v_weight += split_weight_at.get(bp, 0)
            page_violations = v_weight.bit_count()
            cand = (
                tail[0] + page_violations,
                tail[1] - v_weight,
                tail[2] + 1,
                tail[3] + (doc.capacity - used) ** 2,
            )
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

    # 依据最终分页收集被违反的指令录入序号
    order_at_lock: dict[int, list[int]] = {}
    for d in active:
        if d.kind != LOCK_BREAK:
            continue
        gline = start_by_id[d.paragraph_id] + d.line_in_paragraph - 1
        order_at_lock.setdefault(gline, []).append(d.order)
    order_at_split: dict[int, list[int]] = {}
    for d in active:
        if d.kind != NO_SPLIT:
            continue
        gline = start_by_id[d.paragraph_id] + d.line_in_paragraph - 1
        order_at_split.setdefault(gline, []).append(d.order)

    violated: set[int] = set()
    prev = 0
    for end in endings:
        for r in range(prev + 1, end):  # 开区间 (prev, end) 内的锁定行被跨过
            violated.update(order_at_lock.get(r, ()))
        if end < total:
            violated.update(order_at_split.get(end, ()))
        prev = end

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
    return Solution(
        tuple(pages), tuple(endings), squared, tuple(sorted(violated))
    )


def _prefix_failure(doc: Document, invalid: tuple[InvalidDirective, ...]) -> Failure:
    """原文档本身无解时的最短不可行前缀定位（不混入指令归因）。"""
    spans = paragraph_spans(doc.paragraphs)
    for k in range(1, len(doc.paragraphs) + 1):
        end_line = spans[k - 1][1]
        prefix_notes = tuple(f for f in doc.footnotes if f.marker_line <= end_line)
        sub = Document(doc.capacity, doc.paragraphs[:k], prefix_notes)
        if _solve_whole(sub) is None:
            ordered = tuple(sorted(prefix_notes, key=lambda f: (f.marker_line, f.order)))
            return Failure(k, doc.paragraphs[k - 1].id, end_line, ordered, invalid)
    raise AssertionError("整篇无解时必存在不可行前缀")


def solve(
    doc: Document,
    released_orders: frozenset[int] = frozenset(),
) -> Solution | Failure:
    """按人工版式指令求解整篇。

    1. 分类有效 / 失效指令；失效指令不参与约束，随结果就地标出。
    2. 有效指令（剔除调用方已确认释放的序号）以软约束形式嵌入
       容量、片段、保持约束的同一次动态规划。
    3. 原文档本身无解 ⇒ 最短不可行前缀（既有行为，不归因指令）。
       注：指令是软约束，永远不会「导致」无解；这里的无解仅由硬约束决定。
    """
    valid, invalid = classify_directives(doc)
    valid_orders = {d.order for d in valid}
    prereleased = frozenset(o for o in released_orders if o in valid_orders)

    sol = _solve_whole(doc, valid, prereleased)
    if sol is None:
        return _prefix_failure(doc, invalid)

    relaxed = tuple(sorted(set(sol.violated_directives) | set(prereleased)))
    return replace(
        sol,
        violated_directives=relaxed,
        invalid_directives=invalid,
    )
