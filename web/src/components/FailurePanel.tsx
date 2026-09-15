import type { FailureOut } from '../lib/types'

interface Props {
  failure: FailureOut
}

export function FailurePanel({ failure }: Props) {
  return (
    <div className="failure-panel" data-testid="failure-panel" role="alert">
      <h3>无法完成分页</h3>
      <p data-testid="failure-paragraph">
        最短不可行前缀截至第 {failure.paragraph_index} 段「{failure.paragraph_id}」
        （覆盖第 1–{failure.prefix_end_line} 行，共 {failure.prefix_paragraph_count} 段）。
      </p>
      <p>
        该前缀内不存在任何合法分页。以下注记位于前缀范围内，按标记行与录入顺序列出，
        供排查参考，不单独归责于某一注记：
      </p>
      {failure.footnote_ids.length === 0 ? (
        <p className="muted" data-testid="failure-footnotes">
          前缀范围内无注记
        </p>
      ) : (
        <ul data-testid="failure-footnotes">
          {failure.footnotes.map((f) => (
            <li key={f.id}>
              {f.id}（标记第 {f.marker_line} 行，高 {f.height}）
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
