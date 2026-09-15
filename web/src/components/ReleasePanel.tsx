import type { DirectiveRefOut } from '../lib/types'

interface Props {
  released: DirectiveRefOut[]
  /** 段落 id → 行数，用于把段内行号解释为段界 / 段内位置 */
  paragraphLines: Map<string, number>
  onConfirm(): void
  busy: boolean
}

const KIND_TEXT = {
  lock_break: '必须保留',
  no_split: '禁止断开',
} as const

export function describeDirective(
  d: DirectiveRefOut,
  paragraphLines: Map<string, number>,
  paragraphIndexById: Map<string, number>,
): string {
  const n = paragraphLines.get(d.paragraph_id)
  const isBoundary = d.kind === 'lock_break' && n !== undefined && d.line_in_paragraph === n
  const paraNo = paragraphIndexById.get(d.paragraph_id)
  const where = isBoundary
    ? `段界（第 ${paraNo ?? '?'} 段「${d.paragraph_id}」结束处）`
    : `第 ${paraNo ?? '?'} 段「${d.paragraph_id}」第 ${d.line_in_paragraph} 行后`
  const tail = paragraphIndexById.has(d.paragraph_id) ? '' : '（段落已失配）'
  return `#${d.order + 1} ${KIND_TEXT[d.kind]} · ${where}${tail}`
}

export function ReleasePanel({ released, paragraphLines, onConfirm, busy }: Props) {
  const paragraphIndexById = new Map(
    [...paragraphLines.keys()].map((id, i) => [id, i + 1]),
  )
  return (
    <div className="release-panel" data-testid="release-panel" role="alert">
      <h3>指令无法同时满足</h3>
      <p>
        原文档可以分页，但全部有效指令不能同时成立。求解器已在所有可行分页中找出
        <strong> 释放数量最少 </strong>
        的一组指令；同数量时按被释放指令的录入序号序列裁决，建议唯一：
      </p>
      <ul data-testid="release-list">
        {released.map((d) => (
          <li key={d.order} data-testid={`release-item-${d.order}`}>
            {describeDirective(d, paragraphLines, paragraphIndexById)}
          </li>
        ))}
      </ul>
      <p className="muted">
        下方预览即按该建议给出的可复算结果（页数 → 剩余容量平方和 → 结束行号序列）。
        可一次确认释放并重算，或返回左侧调整指令。
      </p>
      <button
        type="button"
        className="release-confirm"
        data-testid="release-confirm"
        disabled={busy}
        onClick={onConfirm}
      >
        {busy ? '重算中…' : '确认释放并重算'}
      </button>
    </div>
  )
}
