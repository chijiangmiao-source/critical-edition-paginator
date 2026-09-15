import type { FootnoteDraft, ParagraphDraft } from '../lib/model'

interface Props {
  footnotes: FootnoteDraft[]
  paragraphs: ParagraphDraft[]
  onChange(footnotes: FootnoteDraft[]): void
}

export function FootnoteEditor({ footnotes, paragraphs, onChange }: Props) {
  const update = (key: string, patch: Partial<FootnoteDraft>) => {
    onChange(footnotes.map((f) => (f.key === key ? { ...f, ...patch } : f)))
  }
  const remove = (key: string) => {
    onChange(footnotes.filter((f) => f.key !== key))
  }
  const add = () => {
    const used = new Set(footnotes.map((f) => f.id))
    let n = footnotes.length + 1
    while (used.has(`n${n}`)) n += 1
    const firstParagraph = paragraphs[0]?.id ?? ''
    onChange([
      ...footnotes,
      {
        key: `k${Date.now()}-${n}`,
        id: `n${n}`,
        paragraphId: firstParagraph,
        lineInParagraph: 1,
        height: 1,
      },
    ])
  }
  return (
    <section className="panel" aria-label="注记">
      <header className="panel-header">
        <h2>注记</h2>
        <button
          type="button"
          data-testid="add-footnote"
          onClick={add}
          disabled={paragraphs.length === 0}
        >
          添加注记
        </button>
      </header>
      <table className="grid">
        <thead>
          <tr>
            <th>id</th>
            <th>标记段落</th>
            <th>段内行</th>
            <th>高度</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {footnotes.map((f) => (
            <tr key={f.key} data-testid={`footnote-row-${f.id}`}>
              <td>
                <input
                  data-testid={`footnote-id-${f.key}`}
                  value={f.id}
                  onChange={(e) => update(f.key, { id: e.target.value })}
                />
              </td>
              <td>
                <select
                  data-testid={`footnote-paragraph-${f.id}`}
                  value={f.paragraphId}
                  onChange={(e) => update(f.key, { paragraphId: e.target.value })}
                >
                  {paragraphs.map((p) => (
                    <option key={p.key} value={p.id}>
                      {p.id}
                    </option>
                  ))}
                </select>
              </td>
              <td>
                <input
                  type="number"
                  min={1}
                  data-testid={`footnote-line-${f.id}`}
                  value={f.lineInParagraph}
                  onChange={(e) => update(f.key, { lineInParagraph: Number(e.target.value) })}
                />
              </td>
              <td>
                <input
                  type="number"
                  min={1}
                  data-testid={`footnote-height-${f.id}`}
                  value={f.height}
                  onChange={(e) => update(f.key, { height: Number(e.target.value) })}
                />
              </td>
              <td>
                <button
                  type="button"
                  data-testid={`remove-footnote-${f.id}`}
                  onClick={() => remove(f.key)}
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
