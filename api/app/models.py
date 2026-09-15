"""API 请求 / 响应模型（Pydantic v2）。"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

DirectiveKind = Literal["lock_break", "no_split"]


class ParagraphIn(BaseModel):
    id: str = Field(min_length=1, max_length=64)
    lines: int = Field(ge=1, description="段落行数，正整数")
    keep_with_next: bool = Field(default=False, description="与下段保持")


class FootnoteIn(BaseModel):
    id: str = Field(min_length=1, max_length=64)
    marker_line: int = Field(ge=1, description="标记行（全局 1 基行号）")
    height: int = Field(ge=1, description="注记高度，正整数")


class DirectiveIn(BaseModel):
    kind: DirectiveKind = Field(description="lock_break=必须保留断点；no_split=禁止段内断开")
    paragraph_id: str = Field(min_length=1, max_length=64)
    line_in_paragraph: int = Field(ge=1, description="段内 1 基行号；段界锁定时填段落末行")


class PaginateRequest(BaseModel):
    capacity: int = Field(ge=1, description="页容量 H，正整数")
    paragraphs: list[ParagraphIn] = Field(min_length=1)
    footnotes: list[FootnoteIn] = Field(default_factory=list)
    directives: list[DirectiveIn] = Field(
        default_factory=list,
        description="人工版式指令，按数组下标作为录入序号",
    )
    # 已由用户确认释放的指令录入序号；仅在确认页重算时提供
    release_directives: list[int] = Field(default_factory=list)

    @model_validator(mode="after")
    def check_consistency(self) -> "PaginateRequest":
        paragraph_ids = [p.id for p in self.paragraphs]
        if len(set(paragraph_ids)) != len(paragraph_ids):
            raise ValueError("段落 id 重复")
        footnote_ids = [f.id for f in self.footnotes]
        if len(set(footnote_ids)) != len(footnote_ids):
            raise ValueError("注记 id 重复")
        total = sum(p.lines for p in self.paragraphs)
        for f in self.footnotes:
            if f.marker_line > total:
                raise ValueError(
                    f"注记 {f.id} 的标记行 {f.marker_line} 超出总行数 {total}"
                )
        if any(o < 0 or o >= len(self.directives) for o in self.release_directives):
            raise ValueError("release_directives 含越界的指令序号")
        return self


class FootnoteOut(BaseModel):
    id: str
    marker_line: int
    height: int


class LineOut(BaseModel):
    line: int  # 全局 1 基行号
    paragraph_id: str
    line_in_paragraph: int


class BreakOut(BaseModel):
    kind: Literal["paragraph_boundary", "paragraph_split", "end"]
    after_line: int
    paragraph_id: str | None = None
    lines_before_in_paragraph: int | None = None  # 段内断点时，断点位于本段第几行之后


class DirectiveRefOut(BaseModel):
    """一条指令的定位信息（用于释放建议 / 失效标出）。"""
    order: int  # 录入序号（请求数组下标，0 起）
    kind: DirectiveKind
    paragraph_id: str
    line_in_paragraph: int


class InvalidDirectiveOut(DirectiveRefOut):
    reason: Literal["paragraph_not_found", "line_out_of_range", "illegal_position"]


class PageOut(BaseModel):
    index: int
    start_line: int
    end_line: int
    line_count: int
    lines: list[LineOut]
    footnotes: list[FootnoteOut]
    text_units: int
    footnote_units: int
    used: int
    slack: int
    break_after: BreakOut


class OkSummary(BaseModel):
    capacity: int
    total_lines: int
    page_count: int
    squared_slack: int
    ending_lines: list[int]


class OkResponse(BaseModel):
    status: Literal["ok"] = "ok"
    summary: OkSummary
    pages: list[PageOut]
    # 未携带指令的旧请求这两个字段不出现（exclude_none 装配），响应保持原样
    directives_satisfied: bool | None = None
    active_directive_count: int | None = None
    invalid_directives: list[InvalidDirectiveOut] | None = None
    released_directives: list[DirectiveRefOut] | None = None  # 未生效的有效指令（建议或已确认）
    release_confirmed: bool | None = None  # 建议(false)还是已经用户确认(true)


class FailureOut(BaseModel):
    paragraph_id: str
    paragraph_index: int
    prefix_paragraph_count: int
    prefix_end_line: int
    footnote_ids: list[str]  # 前缀内全部注记编号，按 (标记行, 录入序号) 排序
    footnotes: list[FootnoteOut]
    invalid_directives: list[InvalidDirectiveOut] | None = None


class DocSummary(BaseModel):
    capacity: int
    total_lines: int


class InfeasibleResponse(BaseModel):
    status: Literal["infeasible"] = "infeasible"
    summary: DocSummary
    failure: FailureOut
