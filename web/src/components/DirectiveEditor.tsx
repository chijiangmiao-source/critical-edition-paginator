import type { InvalidDirectiveReason } from '../lib/types'
import type { DirectiveDraft, ParagraphDraft } from '../lib/model'

interface Props {
  directives: DirectiveDraft[]
  paragraphs: ParagraphDraft[]
  /** 最近一次响应中失效指令的录入序号（= 当前草稿数组下标）及原因 */
  invalidByOrder: Map<number, InvalidDirectiveReason>
  onChange(directives: DirectiveDraft[]): void
}

const REASON_TEXT: Record<InvalidDirectiveReason, string> = {
  paragraph_not_found: '段落 ID 已失配（段落已改名或删除）',
  line_out_of_range: '段内行号越界',
  illegal_position: '该位置不允许此操作',
}

const KIND_TEXT = {
  lock_break: '必须保留',
  no_split: '禁止断开',
} as const

export function DirectiveEditor({ directives, paragraphs, invalidByOrder, onChange }: Props) {
  const update = (key: string, patch: Partial<DirectiveDraft>) => {
    onChange(directives.map((d) => (d.key === key ? { ...d, ...patch } : d)))
  }
  const remove = (key: string) => {
    onChange(directives.filter((d) => d.key !== key))
  }
  const add = () => {
    const first = paragraphs[0]
    // 默认「必须保留」：非末段取段界（末行）；末段无段界可取，回退到首个合法段内位置
    const isLast =
      paragraphs.length > 0 && paragraphs[paragraphs.length - 1].key === first?.key
    const line = first ? (isLast ? (first.lines >= 4 ? 2 : 1) : first.lines) : 1
    onChange([
      ...directives,
      {
        key: `k-dir-${Date.now()}-${directives.length + 1}`,
        kind: 'lock_break',
        paragraphId: first?.id ?? '',
        lineInParagraph: line,
      },
    ])
  }

  const currentIds = new Set(paragraphs.map((p) => p.id))

  return (
    <section className="panel" aria-label="版式指令">
      <header className="panel-header">
        <h2>版式指令</h2>
        <button
          type="button"
          data-testid="add-directive"
          onClick={add}
          disabled={paragraphs.length === 0}
        >
          添加指令
        </button>
      </header>
      <p className="muted hint">
        「必须保留」「禁止断开」均可施于段界（非末段末行后）或合法段内行
        （锁定须两侧片段均 ≥ 2 行）。指令按段落 ID 与段内行号保存；
        段落改名、删除、目标行越界或位置非法时就地标失效，不影响其余编辑。
      </p>
      <table className="grid">
        <thead>
          <tr>
            <th>操作</th>
            <th>段落</th>
            <th>段内行</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {directives.map((d, order) => {
            const reason = invalidByOrder.get(order)
            const matched = currentIds.has(d.paragraphId)
            return (
              <tr
                key={d.key}
                data-testid={`directive-row-${order}`}
                className={reason ? 'row-directive-invalid' : undefined}
              >
                <td>
                  <select
                    data-testid={`directive-kind-${order}`}
                    value={d.kind}
                    onChange={(e) =>
                      update(d.key, { kind: e.target.value as DirectiveDraft['kind'] })
                    }
                  >
                    <option value="lock_break">{KIND_TEXT.lock_break}</option>
                    <option value="no_split">{KIND_TEXT.no_split}</option>
                  </select>
                </td>
                <td>
                  <select
                    data-testid={`directive-paragraph-${order}`}
                    value={matched ? d.paragraphId : `__missing__${order}`}
                    onChange={(e) => update(d.key, { paragraphId: e.target.value })}
                  >
                    {paragraphs.map((p) => (
                      <option key={p.key} value={p.id}>
                        {p.id}
                      </option>
                    ))}
                    {!matched && (
                      <option value={`__missing__${order}`}>
                        {d.paragraphId || '(空)'}（已失配）
                      </option>
                    )}
                  </select>
                </td>
                <td>
                  <input
                    type="number"
                    min={1}
                    data-testid={`directive-line-${order}`}
                    value={d.lineInParagraph}
                    onChange={(e) => update(d.key, { lineInParagraph: Number(e.target.value) })}
                  />
                </td>
                <td>
                  <button
                    type="button"
                    data-testid={`remove-directive-${order}`}
                    onClick={() => remove(d.key)}
                  >
                    删除
                  </button>
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
      {directives.map((d, order) => {
        const reason = invalidByOrder.get(order)
        if (!reason) return null
        return (
          <p
            key={`invalid-${d.key}`}
            className="directive-invalid-note"
            data-testid={`directive-invalid-${order}`}
          >
            指令 #{order + 1}（{KIND_TEXT[d.kind]} · {d.paragraphId || '?'} 第{' '}
            {d.lineInParagraph} 行后）已失效：{REASON_TEXT[reason]}
          </p>
        )
      })}
    </section>
  )
}
