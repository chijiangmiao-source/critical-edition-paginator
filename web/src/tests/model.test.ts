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
    directives: [],
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
          { key: 'f1', id: 'n1', paragraphKey: 'k2', lineInParagraph: 2, height: 3 },
          { key: 'f2', id: 'n2', paragraphKey: 'k1', lineInParagraph: 1, height: 1 },
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
      directives: [],
    })
  })

  it('段落改名后注记仍关联同一段落', () => {
    const d = draft({
      footnotes: [{ key: 'f1', id: 'n1', paragraphKey: 'k2', lineInParagraph: 2, height: 3 }],
    })
    d.paragraphs[1] = { ...d.paragraphs[1], id: 'p2-renamed' }
    const built = buildRequest(d)
    expect(built.ok).toBe(true)
    if (!built.ok) return
    expect(built.request.paragraphs[1].id).toBe('p2-renamed')
    expect(built.request.footnotes).toEqual([{ id: 'n1', marker_line: 5, height: 3 }])
  })

  it('标记行超出段落行数时报错', () => {
    const built = buildRequest(
      draft({
        footnotes: [{ key: 'f1', id: 'n1', paragraphKey: 'k1', lineInParagraph: 4, height: 1 }],
      }),
    )
    expect(built.ok).toBe(false)
    if (built.ok) return
    expect(built.errors.join('\n')).toContain('超出段落 p1 的范围 1–3')
  })

  it('引用已被删除的段落时报错', () => {
    const built = buildRequest(
      draft({
        footnotes: [{ key: 'f1', id: 'n1', paragraphKey: 'ghost', lineInParagraph: 1, height: 1 }],
      }),
    )
    expect(built.ok).toBe(false)
    if (built.ok) return
    expect(built.errors.join('\n')).toContain('引用的段落不存在')
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
          { key: 'f1', id: 'n1', paragraphKey: 'k1', lineInParagraph: 1, height: 1 },
          { key: 'f2', id: 'n1', paragraphKey: 'k2', lineInParagraph: 1, height: 1 },
        ],
      }),
    )
    expect(built.ok).toBe(false)
    if (built.ok) return
    expect(built.errors.join('\n')).toContain('注记 id 重复：n1')
  })
})

describe('buildRequest · 版式指令', () => {
  it('把指令按段落 id 与段内行号输出，数组顺序即录入序号', () => {
    const built = buildRequest(
      draft({
        directives: [
          { key: 'd1', kind: 'lock_break', paragraphKey: 'k1', paragraphIdSnapshot: 'p1', lineInParagraph: 2 },
          { key: 'd2', kind: 'no_split', paragraphKey: 'k2', paragraphIdSnapshot: 'p2', lineInParagraph: 3 },
        ],
      }),
    )
    expect(built.ok).toBe(true)
    if (!built.ok) return
    expect(built.request.directives).toEqual([
      { kind: 'lock_break', paragraph_id: 'p1', line_in_paragraph: 2 },
      { kind: 'no_split', paragraph_id: 'p2', line_in_paragraph: 3 },
    ])
  })

  it('段落改名后指令仍跟随当前 id（按内部 key 关联）', () => {
    const d = draft({
      directives: [
        { key: 'd1', kind: 'lock_break', paragraphKey: 'k1', paragraphIdSnapshot: 'p1', lineInParagraph: 2 },
      ],
    })
    d.paragraphs[0] = { ...d.paragraphs[0], id: 'p1-renamed' }
    const built = buildRequest(d)
    expect(built.ok).toBe(true)
    if (!built.ok) return
    expect(built.request.directives).toEqual([
      { kind: 'lock_break', paragraph_id: 'p1-renamed', line_in_paragraph: 2 },
    ])
  })

  it('目标段落删除后仍按 id 快照发送，交后端就地标失效（不拦截其余编辑）', () => {
    const built = buildRequest(
      draft({
        paragraphs: [{ key: 'k1', id: 'p1', lines: 3, keepWithNext: false }],
        directives: [
          { key: 'd1', kind: 'lock_break', paragraphKey: 'ghost', paragraphIdSnapshot: 'p9', lineInParagraph: 2 },
        ],
      }),
    )
    expect(built.ok).toBe(true)
    if (!built.ok) return
    expect(built.request.directives).toEqual([
      { kind: 'lock_break', paragraph_id: 'p9', line_in_paragraph: 2 },
    ])
  })

  it('段内行越界不客户端拦截，原样发送由后端判失效', () => {
    const built = buildRequest(
      draft({
        directives: [
          { key: 'd1', kind: 'lock_break', paragraphKey: 'k1', paragraphIdSnapshot: 'p1', lineInParagraph: 99 },
        ],
      }),
    )
    expect(built.ok).toBe(true)
    if (!built.ok) return
    expect(built.request.directives?.[0].line_in_paragraph).toBe(99)
  })

  it('行号非正整数才在客户端报错', () => {
    const built = buildRequest(
      draft({
        directives: [
          { key: 'd1', kind: 'no_split', paragraphKey: 'k1', paragraphIdSnapshot: 'p1', lineInParagraph: 0 },
        ],
      }),
    )
    expect(built.ok).toBe(false)
    if (built.ok) return
    expect(built.errors.join('\n')).toContain('行号须为正整数')
  })
})
