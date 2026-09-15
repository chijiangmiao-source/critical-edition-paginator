import { useMemo, useState } from 'react'
import { paginate } from './lib/api'
import { buildRequest, paragraphStartLines, type Draft } from './lib/model'
import type {
  DirectiveRefOut,
  InvalidDirectiveReason,
  PaginateResponse,
} from './lib/types'
import { ParagraphEditor } from './components/ParagraphEditor'
import { FootnoteEditor } from './components/FootnoteEditor'
import { DirectiveEditor } from './components/DirectiveEditor'
import { Preview } from './components/Preview'
import { FailurePanel } from './components/FailurePanel'
import { ReleasePanel } from './components/ReleasePanel'

const initialDraft: Draft = {
  capacity: 10,
  paragraphs: [
    { key: 'k-p1', id: 'p1', lines: 5, keepWithNext: true },
    { key: 'k-p2', id: 'p2', lines: 6, keepWithNext: false },
  ],
  footnotes: [
    { key: 'k-n1', id: 'n1', paragraphKey: 'k-p1', lineInParagraph: 2, height: 2 },
    { key: 'k-n2', id: 'n2', paragraphKey: 'k-p2', lineInParagraph: 4, height: 3 },
  ],
  directives: [],
}

export default function App() {
  const [draft, setDraft] = useState<Draft>(initialDraft)
  const [result, setResult] = useState<PaginateResponse | null>(null)
  const [errors, setErrors] = useState<string[]>([])
  const [busy, setBusy] = useState(false)
  // 草稿在最近一次计算后被改动 ⇒ 释放建议与失效标记不再可确信，隐藏建议面板
  const [dirty, setDirty] = useState(false)
  // 失效指令按草稿 key 标出（序号 → 计算时的草稿 key），编辑后仍能稳定定位
  const [invalidKeys, setInvalidKeys] = useState<Map<string, InvalidDirectiveReason>>(new Map())

  const failureParagraphId =
    result !== null && result.status === 'infeasible' ? result.failure.paragraph_id : null

  function patchDraft(patch: Partial<Draft>) {
    setDraft({ ...draft, ...patch })
    setDirty(true)
  }

  async function compute(releaseOrders: number[] = []) {
    const built = buildRequest(draft)
    if (!built.ok) {
      setErrors(built.errors)
      setResult(null)
      return
    }
    setErrors([])
    setBusy(true)
    try {
      const request =
        releaseOrders.length > 0
          ? { ...built.request, release_directives: releaseOrders }
          : built.request
      const resp = await paginate(request)
      setResult(resp)
      setDirty(false)
      if (resp.status === 'ok') {
        const map = new Map<string, InvalidDirectiveReason>()
        for (const item of resp.invalid_directives ?? []) {
          const key = draft.directives[item.order]?.key
          if (key) map.set(key, item.reason)
        }
        setInvalidKeys(map)
      } else {
        const map = new Map<string, InvalidDirectiveReason>()
        for (const item of resp.failure.invalid_directives ?? []) {
          const key = draft.directives[item.order]?.key
          if (key) map.set(key, item.reason)
        }
        setInvalidKeys(map)
      }
    } catch (err) {
      setResult(null)
      setErrors([err instanceof Error ? err.message : String(err)])
    } finally {
      setBusy(false)
    }
  }

  // 失效指令序号（传编辑器，由其按当前下标对照）
  const invalidByOrder = useMemo(() => {
    const map = new Map<number, InvalidDirectiveReason>()
    draft.directives.forEach((d, i) => {
      const reason = invalidKeys.get(d.key)
      if (reason) map.set(i, reason)
    })
    return map
  }, [draft.directives, invalidKeys])

  const okResult = result?.status === 'ok' ? result : null
  const released: DirectiveRefOut[] =
    !dirty && okResult ? okResult.released_directives ?? [] : []
  const showReleaseSuggestion =
    okResult !== null && !dirty && okResult.release_confirmed === false && released.length > 0

  // 当前生效（未失效、未释放）的锁定断点全局行号，用于页卡片标注；
  // 草稿有未计算改动时，旧响应的释放/失效序号不再可确信，不标注锁定。
  const lockedBreakLines = useMemo(() => {
    if (!okResult || dirty) return new Set<number>()
    const starts = paragraphStartLines(draft.paragraphs)
    const releasedOrders = new Set((okResult.released_directives ?? []).map((d) => d.order))
    const invalidOrders = new Set((okResult.invalid_directives ?? []).map((d) => d.order))
    const lines = new Set<number>()
    draft.directives.forEach((d, order) => {
      if (d.kind !== 'lock_break' || releasedOrders.has(order) || invalidOrders.has(order)) return
      const para = draft.paragraphs.find((p) => p.key === d.paragraphKey)
      if (!para) return
      lines.add((starts.get(para.id) ?? 1) + d.lineInParagraph - 1)
    })
    return lines
  }, [okResult, draft])

  const paragraphLines = useMemo(
    () => new Map(draft.paragraphs.map((p) => [p.id, p.lines])),
    [draft.paragraphs],
  )

  return (
    <div className="app">
      <header className="app-header">
        <h1>古籍校勘版分页</h1>
        <p className="muted">
          页下注反向挤占正文；在全部合法方案中依次最小化页数、剩余容量平方和，并取结束行号字典序最小者。
          可在段界与合法段内行位标注「必须保留」或「禁止断开」，按人工版式指令整篇重算。
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
                onChange={(e) => patchDraft({ capacity: Number(e.target.value) })}
              />
            </label>
          </section>
          <ParagraphEditor
            paragraphs={draft.paragraphs}
            failureParagraphId={failureParagraphId}
            onChange={(paragraphs) => patchDraft({ paragraphs })}
          />
          <FootnoteEditor
            footnotes={draft.footnotes}
            paragraphs={draft.paragraphs}
            onChange={(footnotes) => patchDraft({ footnotes })}
          />
          <DirectiveEditor
            directives={draft.directives}
            paragraphs={draft.paragraphs}
            invalidByOrder={dirty ? new Map() : invalidByOrder}
            onChange={(directives) => patchDraft({ directives })}
          />
          <button
            type="button"
            className="compute"
            data-testid="compute-button"
            disabled={busy}
            onClick={() => compute()}
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
          {okResult !== null && (
            <>
              <p className="summary" data-testid="summary">
                共 {okResult.summary.page_count} 页 · 剩余容量平方和 {okResult.summary.squared_slack} ·
                结束行号 [{okResult.summary.ending_lines.join(', ')}]
              </p>
              {okResult.active_directive_count !== undefined && (
                <p className="directive-status" data-testid="directive-status">
                  有效指令 {okResult.active_directive_count} 条
                  {(okResult.invalid_directives?.length ?? 0) > 0 &&
                    ` · 失效 ${okResult.invalid_directives?.length} 条（已就地标出）`}
                  {!dirty &&
                    okResult.release_confirmed &&
                    released.length > 0 &&
                    ` · 已确认释放 ${released.length} 条`}
                </p>
              )}
              {showReleaseSuggestion && (
                <ReleasePanel
                  released={released}
                  paragraphLines={paragraphLines}
                  busy={busy}
                  onConfirm={() => compute(released.map((d) => d.order))}
                />
              )}
              <Preview
                pages={okResult.pages}
                capacity={okResult.summary.capacity}
                lockedBreakLines={lockedBreakLines}
              />
            </>
          )}
          {result !== null && result.status === 'infeasible' && (
            <FailurePanel
              failure={result.failure}
              invalidDirectives={dirty ? [] : result.failure.invalid_directives ?? []}
            />
          )}
        </div>
      </main>
    </div>
  )
}
