import { breakLabel, capacityFormula } from '../lib/format'
import type { PageOut } from '../lib/types'

interface Props {
  pages: PageOut[]
  capacity: number
}

export function Preview({ pages, capacity }: Props) {
  return (
    <div className="pages">
      {pages.map((page) => (
        <section key={page.index} className="page-card" data-testid="page-card">
          <header className="page-header">
            第 {page.index} 页（第 {page.start_line}–{page.end_line} 行）
          </header>
          <div className="page-body">
            <ol className="page-lines">
              {page.lines.map((line) => (
                <li key={line.line} data-testid="page-line">
                  <span className="line-no">#{line.line}</span>
                  {line.paragraph_id} · 第 {line.line_in_paragraph} 行
                </li>
              ))}
            </ol>
            <footer className="page-footnotes">
              <h3>页下注</h3>
              {page.footnotes.length === 0 ? (
                <p className="muted">本页无注记</p>
              ) : (
                <ul>
                  {page.footnotes.map((f) => (
                    <li key={f.id} data-testid="page-footnote">
                      {f.id}（标记第 {f.marker_line} 行，高 {f.height}）
                    </li>
                  ))}
                </ul>
              )}
            </footer>
          </div>
          <p className="formula" data-testid="capacity-formula">
            {capacityFormula(page, capacity)}
          </p>
          <p className="break-label" data-testid="break-label">
            断点：{breakLabel(page.break_after)}
          </p>
        </section>
      ))}
    </div>
  )
}
