import type { FailureOut, InvalidDirectiveOut, InvalidDirectiveReason } from '../lib/types'

interface Props {
  failure: FailureOut
  invalidDirectives?: InvalidDirectiveOut[]
}

const REASON_TEXT: Record<InvalidDirectiveReason, string> = {
  paragraph_not_found: '段落 id 失配（目标段落不存在）',
  line_out_of_range: '段内行号越界',
  illegal_position: '该位置不允许此操作',
}

const KIND_TEXT = {
  lock_break: '必须保留',
  no_split: '禁止断开',
} as const

export function FailurePanel({ failure, invalidDirectives = [] }: Props) {
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
      <p className="failure-note" data-testid="failure-directive-note">
        该无解源于篇章本身（容量 / 片段 / 保持约束），与版式指令无关，不作指令归因。
      </p>
      {invalidDirectives.length > 0 && (
        <div className="failure-invalid-directives" data-testid="failure-invalid-directives">
          <h4>失效指令（未参与求解）</h4>
          <ul>
            {invalidDirectives.map((d) => (
              <li key={d.order} data-testid={`failure-invalid-directive-${d.order}`}>
                #{d.order + 1} {KIND_TEXT[d.kind]} · 段落 {d.paragraph_id} 第{' '}
                {d.line_in_paragraph} 行后：{REASON_TEXT[d.reason]}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
