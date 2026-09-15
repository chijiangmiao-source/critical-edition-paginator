/** 编辑器草稿模型：校验并转换为 API 请求（标记行换算为全局行号）。 */
import type { PaginateRequest } from './types'

export interface ParagraphDraft {
  key: string
  id: string
  lines: number
  keepWithNext: boolean
}

export interface FootnoteDraft {
  key: string
  id: string
  /** 以段落的内部 key 关联：段落 id 改名后引用仍然有效 */
  paragraphKey: string
  lineInParagraph: number
  height: number
}

export interface Draft {
  capacity: number
  paragraphs: ParagraphDraft[]
  footnotes: FootnoteDraft[]
}

let keyCounter = 0

export function nextKey(): string {
  keyCounter += 1
  return `k${keyCounter}`
}

/** 每个段落首行的全局行号（1 基）。 */
export function paragraphStartLines(paragraphs: ParagraphDraft[]): Map<string, number> {
  const starts = new Map<string, number>()
  let start = 1
  for (const p of paragraphs) {
    starts.set(p.id, start)
    start += p.lines
  }
  return starts
}

export function totalLines(paragraphs: ParagraphDraft[]): number {
  return paragraphs.reduce((acc, p) => acc + p.lines, 0)
}

export type BuildResult =
  | { ok: true; request: PaginateRequest }
  | { ok: false; errors: string[] }

export function buildRequest(draft: Draft): BuildResult {
  const errors: string[] = []
  if (!Number.isInteger(draft.capacity) || draft.capacity < 1) {
    errors.push('页容量 H 须为正整数')
  }
  if (draft.paragraphs.length === 0) {
    errors.push('至少需要一段')
  }
  const paragraphIds = new Set<string>()
  for (const p of draft.paragraphs) {
    if (!p.id.trim()) errors.push('段落 id 不能为空')
    if (paragraphIds.has(p.id)) errors.push(`段落 id 重复：${p.id}`)
    paragraphIds.add(p.id)
    if (!Number.isInteger(p.lines) || p.lines < 1) {
      errors.push(`段落 ${p.id || '(未命名)'} 的行数须为正整数`)
    }
  }
  const starts = paragraphStartLines(draft.paragraphs)
  const byKey = new Map(draft.paragraphs.map((p) => [p.key, p]))
  const footnoteIds = new Set<string>()
  const footnotes: PaginateRequest['footnotes'] = []
  for (const f of draft.footnotes) {
    if (!f.id.trim()) errors.push('注记 id 不能为空')
    if (footnoteIds.has(f.id)) errors.push(`注记 id 重复：${f.id}`)
    footnoteIds.add(f.id)
    const para = byKey.get(f.paragraphKey)
    if (!para) {
      errors.push(`注记 ${f.id || '(未命名)'} 引用的段落不存在（可能已被删除）`)
      continue
    }
    if (
      !Number.isInteger(f.lineInParagraph) ||
      f.lineInParagraph < 1 ||
      f.lineInParagraph > para.lines
    ) {
      errors.push(
        `注记 ${f.id || '(未命名)'} 的标记行 ${f.lineInParagraph} 超出段落 ${para.id} 的范围 1–${para.lines}`,
      )
    }
    if (!Number.isInteger(f.height) || f.height < 1) {
      errors.push(`注记 ${f.id || '(未命名)'} 的高度须为正整数`)
    }
    footnotes.push({
      id: f.id,
      marker_line: (starts.get(para.id) ?? 1) + f.lineInParagraph - 1,
      height: f.height,
    })
  }
  if (errors.length > 0) return { ok: false, errors }
  return {
    ok: true,
    request: {
      capacity: draft.capacity,
      paragraphs: draft.paragraphs.map((p) => ({
        id: p.id,
        lines: p.lines,
        keep_with_next: p.keepWithNext,
      })),
      footnotes,
    },
  }
}
