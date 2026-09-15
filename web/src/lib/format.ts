/** 展示层格式化：容量算式与断点说明。 */
import type { BreakOut, PageOut } from './types'

export function capacityFormula(page: PageOut, capacity: number): string {
  const notePart =
    page.footnotes.length > 0
      ? ` + 注记 ${page.footnotes.map((f) => f.height).join(' + ')}`
      : ''
  return (
    `正文 ${page.text_units} 行 × 1${notePart} = ${page.used} / 容量 ${capacity}` +
    `（剩余 ${page.slack}）`
  )
}

export function breakLabel(b: BreakOut): string {
  switch (b.kind) {
    case 'end':
      return '文档结束'
    case 'paragraph_boundary':
      return `段界断点（${b.paragraph_id} 结束）`
    case 'paragraph_split':
      return `段内断点（${b.paragraph_id} 第 ${b.lines_before_in_paragraph} 行后，两侧均 ≥ 2 行）`
  }
}
