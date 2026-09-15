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

export type DirectiveKind = 'lock_break' | 'no_split'

export interface DirectiveInput {
  kind: DirectiveKind
  paragraph_id: string
  line_in_paragraph: number
}

export interface PaginateRequest {
  capacity: number
  paragraphs: ParagraphInput[]
  footnotes: FootnoteInput[]
  directives?: DirectiveInput[]
  release_directives?: number[]
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
  directives_satisfied?: boolean
  active_directive_count?: number
  invalid_directives?: InvalidDirectiveOut[]
  released_directives?: DirectiveRefOut[]
  /** false = released_directives 是待用户确认的最小释放建议；true = 已确认重算 */
  release_confirmed?: boolean
}

export interface DirectiveRefOut {
  order: number
  kind: DirectiveKind
  paragraph_id: string
  line_in_paragraph: number
}

export type InvalidDirectiveReason =
  | 'paragraph_not_found'
  | 'line_out_of_range'
  | 'illegal_position'

export interface InvalidDirectiveOut extends DirectiveRefOut {
  reason: InvalidDirectiveReason
}

export interface FailureOut {
  paragraph_id: string
  paragraph_index: number
  prefix_paragraph_count: number
  prefix_end_line: number
  footnote_ids: string[]
  footnotes: FootnoteOut[]
  invalid_directives?: InvalidDirectiveOut[]
}

export interface InfeasibleResponse {
  status: 'infeasible'
  summary: { capacity: number; total_lines: number }
  failure: FailureOut
}

export type PaginateResponse = OkResponse | InfeasibleResponse
