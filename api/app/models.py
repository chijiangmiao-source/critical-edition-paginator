"""API 请求 / 响应模型（Pydantic v2）。"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator


class ParagraphIn(BaseModel):
    id: str = Field(min_length=1, max_length=64)
    lines: int = Field(ge=1, description="段落行数，正整数")
    keep_with_next: bool = Field(default=False, description="与下段保持")


class FootnoteIn(BaseModel):
    id: str = Field(min_length=1, max_length=64)
    marker_line: int = Field(ge=1, description="标记行（全局 1 基行号）")
    height: int = Field(ge=1, description="注记高度，正整数")


class PaginateRequest(BaseModel):
    capacity: int = Field(ge=1, description="页容量 H，正整数")
    paragraphs: list[ParagraphIn] = Field(min_length=1)
    footnotes: list[FootnoteIn] = Field(default_factory=list)

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


class FailureOut(BaseModel):
    paragraph_id: str
    paragraph_index: int
    prefix_paragraph_count: int
    prefix_end_line: int
    footnote_ids: list[str]  # 前缀内全部注记编号，按 (标记行, 录入序号) 排序
    footnotes: list[FootnoteOut]


class DocSummary(BaseModel):
    capacity: int
    total_lines: int


class InfeasibleResponse(BaseModel):
    status: Literal["infeasible"] = "infeasible"
    summary: DocSummary
    failure: FailureOut
