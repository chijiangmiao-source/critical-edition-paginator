/** 与后端契约对应的类型定义。 */

export interface ParagraphInput {
  id: string
  lines: number
  keep_with_next: boolean
}

export interface FootnoteInput {
  id: string
  marker_line: number
  height: number
}

export interface PaginateRequest {
  capacity: number
  paragraphs: ParagraphInput[]
  footnotes: FootnoteInput[]
}

export interface FootnoteOut {
  id: string
  marker_line: number
  height: number
}

export interface LineOut {
  line: number
  paragraph_id: string
  line_in_paragraph: number
}

export type BreakKind = 'paragraph_boundary' | 'paragraph_split' | 'end'

export interface BreakOut {
  kind: BreakKind
  after_line: number
  paragraph_id: string | null
  lines_before_in_paragraph: number | null
}

export interface PageOut {
  index: number
  start_line: number
  end_line: number
  line_count: number
  lines: LineOut[]
  footnotes: FootnoteOut[]
  text_units: number
  footnote_units: number
  used: number
  slack: number
  break_after: BreakOut
}

export interface OkSummary {
  capacity: number
  total_lines: number
  page_count: number
  squared_slack: number
  ending_lines: number[]
}

export interface OkResponse {
  status: 'ok'
  summary: OkSummary
  pages: PageOut[]
}

export interface FailureOut {
  paragraph_id: string
  paragraph_index: number
  prefix_paragraph_count: number
  prefix_end_line: number
  footnote_ids: string[]
  footnotes: FootnoteOut[]
}

export interface InfeasibleResponse {
  status: 'infeasible'
  summary: { capacity: number; total_lines: number }
  failure: FailureOut
}

export type PaginateResponse = OkResponse | InfeasibleResponse
