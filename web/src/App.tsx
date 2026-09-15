import { useState } from 'react'
import { paginate } from './lib/api'
import { buildRequest, type Draft } from './lib/model'
import type { PaginateResponse } from './lib/types'
import { ParagraphEditor } from './components/ParagraphEditor'
import { FootnoteEditor } from './components/FootnoteEditor'
import { Preview } from './components/Preview'
import { FailurePanel } from './components/FailurePanel'

const initialDraft: Draft = {
  capacity: 10,
  paragraphs: [
    { key: 'k-p1', id: 'p1', lines: 5, keepWithNext: true },
    { key: 'k-p2', id: 'p2', lines: 6, keepWithNext: false },
  ],
  footnotes: [
    { key: 'k-n1', id: 'n1', paragraphId: 'p1', lineInParagraph: 2, height: 2 },
    { key: 'k-n2', id: 'n2', paragraphId: 'p2', lineInParagraph: 4, height: 3 },
  ],
}

export default function App() {
  const [draft, setDraft] = useState<Draft>(initialDraft)
  const [result, setResult] = useState<PaginateResponse | null>(null)
  const [errors, setErrors] = useState<string[]>([])
  const [busy, setBusy] = useState(false)

  const failureParagraphId =
    result !== null && result.status === 'infeasible' ? result.failure.paragraph_id : null

  async function compute() {
    const built = buildRequest(draft)
    if (!built.ok) {
      setErrors(built.errors)
      setResult(null)
      return
    }
    setErrors([])
    setBusy(true)
    try {
      setResult(await paginate(built.request))
    } catch (err) {
      setResult(null)
      setErrors([err instanceof Error ? err.message : String(err)])
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="app">
      <header className="app-header">
        <h1>古籍校勘版分页</h1>
        <p className="muted">
          页下注反向挤占正文；在全部合法方案中依次最小化页数、剩余容量平方和，并取结束行号字典序最小者。
        </p>
      </header>
      <main className="layout">
        <div className="editor">
          <section className="panel">
            <header className="panel-header">
              <h2>版面</h2>
            </header>
            <label className="field">
              页容量 H（行）
              <input
                type="number"
                min={1}
                data-testid="capacity-input"
                value={draft.capacity}
                onChange={(e) => setDraft({ ...draft, capacity: Number(e.target.value) })}
              />
            </label>
          </section>
          <ParagraphEditor
            paragraphs={draft.paragraphs}
            failureParagraphId={failureParagraphId}
            onChange={(paragraphs) => setDraft({ ...draft, paragraphs })}
          />
          <FootnoteEditor
            footnotes={draft.footnotes}
            paragraphs={draft.paragraphs}
            onChange={(footnotes) => setDraft({ ...draft, footnotes })}
          />
          <button
            type="button"
            className="compute"
            data-testid="compute-button"
            disabled={busy}
            onClick={compute}
          >
            {busy ? '计算中…' : '计算分页'}
          </button>
          {errors.length > 0 && (
            <ul className="errors" data-testid="error-list">
              {errors.map((e) => (
                <li key={e}>{e}</li>
              ))}
            </ul>
          )}
        </div>
        <div className="result">
          {result === null && <p className="muted">编辑左侧篇章结构后点击「计算分页」。</p>}
          {result !== null && result.status === 'ok' && (
            <>
              <p className="summary" data-testid="summary">
                共 {result.summary.page_count} 页 · 剩余容量平方和 {result.summary.squared_slack} ·
                结束行号 [{result.summary.ending_lines.join(', ')}]
              </p>
              <Preview pages={result.pages} capacity={result.summary.capacity} />
            </>
          )}
          {result !== null && result.status === 'infeasible' && (
            <FailurePanel failure={result.failure} />
          )}
        </div>
      </main>
    </div>
  )
}
