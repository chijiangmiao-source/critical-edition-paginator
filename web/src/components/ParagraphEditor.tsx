import type { ParagraphDraft } from '../lib/model'

interface Props {
  paragraphs: ParagraphDraft[]
  failureParagraphId: string | null
  onChange(paragraphs: ParagraphDraft[]): void
}

export function ParagraphEditor({ paragraphs, failureParagraphId, onChange }: Props) {
  const update = (key: string, patch: Partial<ParagraphDraft>) => {
    onChange(paragraphs.map((p) => (p.key === key ? { ...p, ...patch } : p)))
  }
  const remove = (key: string) => {
    onChange(paragraphs.filter((p) => p.key !== key))
  }
  const add = () => {
    const used = new Set(paragraphs.map((p) => p.id))
    let n = paragraphs.length + 1
    while (used.has(`p${n}`)) n += 1
    onChange([
      ...paragraphs,
      { key: `k${Date.now()}-${n}`, id: `p${n}`, lines: 2, keepWithNext: false },
    ])
  }
  return (
    <section className="panel" aria-label="段落">
      <header className="panel-header">
        <h2>段落</h2>
        <button type="button" data-testid="add-paragraph" onClick={add}>
          添加段落
        </button>
      </header>
      <table className="grid">
        <thead>
          <tr>
            <th>id</th>
            <th>行数</th>
            <th title="末段无下段，保持标记不参与约束">与下段保持</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {paragraphs.map((p, index) => (
            <tr
              key={p.key}
              data-testid={`paragraph-row-${p.id}`}
              className={p.id === failureParagraphId ? 'row-failure' : undefined}
            >
              <td>
                <input
                  data-testid={`paragraph-id-${p.key}`}
                  value={p.id}
                  onChange={(e) => update(p.key, { id: e.target.value })}
                />
              </td>
              <td>
                <input
                  type="number"
                  min={1}
                  data-testid={`lines-input-${p.id}`}
                  value={p.lines}
                  onChange={(e) => update(p.key, { lines: Number(e.target.value) })}
                />
              </td>
              <td>
                <input
                  type="checkbox"
                  data-testid={`keep-input-${p.id}`}
                  checked={p.keepWithNext}
                  disabled={index === paragraphs.length - 1}
                  title={index === paragraphs.length - 1 ? '末段无下段，保持标记被忽略' : undefined}
                  onChange={(e) => update(p.key, { keepWithNext: e.target.checked })}
                />
              </td>
              <td>
                <button
                  type="button"
                  data-testid={`remove-paragraph-${p.id}`}
                  onClick={() => remove(p.key)}
                >
                  删除
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  )
}
