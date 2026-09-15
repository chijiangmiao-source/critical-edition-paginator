import { describe, expect, it } from 'vitest'
import { breakLabel, capacityFormula } from '../lib/format'
import type { PageOut } from '../lib/types'

function page(overrides: Partial<PageOut> = {}): PageOut {
  return {
    index: 1,
    start_line: 1,
    end_line: 4,
    line_count: 4,
    lines: [],
    footnotes: [],
    text_units: 4,
    footnote_units: 0,
    used: 4,
    slack: 6,
    break_after: { kind: 'end', after_line: 4, paragraph_id: null, lines_before_in_paragraph: null },
    ...overrides,
  }
}

describe('capacityFormula', () => {
  it('无注记时只列正文行', () => {
    expect(capacityFormula(page(), 10)).toBe('正文 4 行 × 1 = 4 / 容量 10（剩余 6）')
  })

  it('有注记时列出各注记高度', () => {
    const p = page({
      footnotes: [
        { id: 'n1', marker_line: 2, height: 3 },
        { id: 'n2', marker_line: 3, height: 2 },
      ],
      footnote_units: 5,
      used: 9,
      slack: 1,
    })
    expect(capacityFormula(p, 10)).toBe('正文 4 行 × 1 + 注记 3 + 2 = 9 / 容量 10（剩余 1）')
  })
})

describe('breakLabel', () => {
  it('段界断点', () => {
    expect(
      breakLabel({ kind: 'paragraph_boundary', after_line: 4, paragraph_id: 'p1', lines_before_in_paragraph: null }),
    ).toBe('段界断点（p1 结束）')
  })

  it('段内断点', () => {
    expect(
      breakLabel({ kind: 'paragraph_split', after_line: 3, paragraph_id: 'p2', lines_before_in_paragraph: 3 }),
    ).toBe('段内断点（p2 第 3 行后，两侧均 ≥ 2 行）')
  })

  it('文档结束', () => {
    expect(
      breakLabel({ kind: 'end', after_line: 8, paragraph_id: null, lines_before_in_paragraph: null }),
    ).toBe('文档结束')
  })
})
