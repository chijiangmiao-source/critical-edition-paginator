import { describe, expect, it } from 'vitest'
import { buildRequest, paragraphStartLines, totalLines, type Draft } from '../lib/model'

function draft(overrides: Partial<Draft> = {}): Draft {
  return {
    capacity: 10,
    paragraphs: [
      { key: 'k1', id: 'p1', lines: 3, keepWithNext: false },
      { key: 'k2', id: 'p2', lines: 4, keepWithNext: true },
    ],
    footnotes: [],
    ...overrides,
  }
}

describe('paragraphStartLines / totalLines', () => {
  it('按段落顺序累计首行号', () => {
    const starts = paragraphStartLines(draft().paragraphs)
    expect(starts.get('p1')).toBe(1)
    expect(starts.get('p2')).toBe(4)
    expect(totalLines(draft().paragraphs)).toBe(7)
  })
})

describe('buildRequest', () => {
  it('把段内标记行换算为全局行号', () => {
    const built = buildRequest(
      draft({
        footnotes: [
          { key: 'f1', id: 'n1', paragraphId: 'p2', lineInParagraph: 2, height: 3 },
          { key: 'f2', id: 'n2', paragraphId: 'p1', lineInParagraph: 1, height: 1 },
        ],
      }),
    )
    expect(built.ok).toBe(true)
    if (!built.ok) return
    expect(built.request).toEqual({
      capacity: 10,
      paragraphs: [
        { id: 'p1', lines: 3, keep_with_next: false },
        { id: 'p2', lines: 4, keep_with_next: true },
      ],
      footnotes: [
        { id: 'n1', marker_line: 5, height: 3 },
        { id: 'n2', marker_line: 1, height: 1 },
      ],
    })
  })

  it('标记行超出段落行数时报错', () => {
    const built = buildRequest(
      draft({
        footnotes: [{ key: 'f1', id: 'n1', paragraphId: 'p1', lineInParagraph: 4, height: 1 }],
      }),
    )
    expect(built.ok).toBe(false)
    if (built.ok) return
    expect(built.errors.join('\n')).toContain('超出段落 p1 的范围 1–3')
  })

  it('引用不存在的段落时报错', () => {
    const built = buildRequest(
      draft({
        footnotes: [{ key: 'f1', id: 'n1', paragraphId: 'ghost', lineInParagraph: 1, height: 1 }],
      }),
    )
    expect(built.ok).toBe(false)
    if (built.ok) return
    expect(built.errors.join('\n')).toContain('不存在的段落 ghost')
  })

  it('段落 id 重复时报错', () => {
    const built = buildRequest(
      draft({
        paragraphs: [
          { key: 'k1', id: 'p1', lines: 2, keepWithNext: false },
          { key: 'k2', id: 'p1', lines: 2, keepWithNext: false },
        ],
      }),
    )
    expect(built.ok).toBe(false)
    if (built.ok) return
    expect(built.errors.join('\n')).toContain('段落 id 重复：p1')
  })

  it('容量与行数必须为正整数', () => {
    const built = buildRequest(
      draft({
        capacity: 0,
        paragraphs: [{ key: 'k1', id: 'p1', lines: 0, keepWithNext: false }],
      }),
    )
    expect(built.ok).toBe(false)
    if (built.ok) return
    expect(built.errors.join('\n')).toContain('页容量 H 须为正整数')
    expect(built.errors.join('\n')).toContain('行数须为正整数')
  })

  it('注记 id 重复时报错', () => {
    const built = buildRequest(
      draft({
        footnotes: [
          { key: 'f1', id: 'n1', paragraphId: 'p1', lineInParagraph: 1, height: 1 },
          { key: 'f2', id: 'n1', paragraphId: 'p2', lineInParagraph: 1, height: 1 },
        ],
      }),
    )
    expect(built.ok).toBe(false)
    if (built.ok) return
    expect(built.errors.join('\n')).toContain('注记 id 重复：n1')
  })
})
