"""FastAPI 入口：分页计算 API。"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import models, solver

app = FastAPI(title="古籍校勘版分页 API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


def _to_document(req: models.PaginateRequest) -> solver.Document:
    return solver.Document(
        capacity=req.capacity,
        paragraphs=tuple(
            solver.Paragraph(p.id, p.lines, p.keep_with_next) for p in req.paragraphs
        ),
        footnotes=tuple(
            solver.Footnote(f.id, f.marker_line, f.height, order)
            for order, f in enumerate(req.footnotes)
        ),
    )


def _line_owners(doc: solver.Document) -> list[tuple[str, int]]:
    """每个全局行号对应的 (段落 id, 段内行号)。"""
    owners: list[tuple[str, int]] = [(doc.paragraphs[0].id, 1)]  # 占位，行号从 1 起
    for p in doc.paragraphs:
        for i in range(1, p.lines + 1):
            owners.append((p.id, i))
    return owners


def _break_out(doc: solver.Document, after_line: int, total: int) -> models.BreakOut:
    if after_line >= total:
        return models.BreakOut(kind="end", after_line=after_line)
    spans = solver.paragraph_spans(doc.paragraphs)
    for para, (s, e) in zip(doc.paragraphs, spans):
        if s <= after_line <= e:
            if after_line == e:
                return models.BreakOut(
                    kind="paragraph_boundary", after_line=after_line, paragraph_id=para.id
                )
            return models.BreakOut(
                kind="paragraph_split",
                after_line=after_line,
                paragraph_id=para.id,
                lines_before_in_paragraph=after_line - s + 1,
            )
    raise AssertionError("断点必落在某段内")


def _ok_response(doc: solver.Document, solution: solver.Solution) -> models.OkResponse:
    owners = _line_owners(doc)
    total = len(owners) - 1  # owners[0] 为占位，行号从 1 起
    pages: list[models.PageOut] = []
    for page in solution.pages:
        lines = [
            models.LineOut(line=n, paragraph_id=owners[n][0], line_in_paragraph=owners[n][1])
            for n in range(page.start_line, page.end_line + 1)
        ]
        pages.append(
            models.PageOut(
                index=page.index,
                start_line=page.start_line,
                end_line=page.end_line,
                line_count=page.end_line - page.start_line + 1,
                lines=lines,
                footnotes=[
                    models.FootnoteOut(id=f.id, marker_line=f.marker_line, height=f.height)
                    for f in page.footnotes
                ],
                text_units=page.text_units,
                footnote_units=page.footnote_units,
                used=page.used,
                slack=page.slack,
                break_after=_break_out(doc, page.end_line, total),
            )
        )
    return models.OkResponse(
        summary=models.OkSummary(
            capacity=doc.capacity,
            total_lines=total,
            page_count=len(solution.pages),
            squared_slack=solution.squared_slack,
            ending_lines=list(solution.ending_lines),
        ),
        pages=pages,
    )


def _infeasible_response(
    doc: solver.Document, failure: solver.Failure
) -> models.InfeasibleResponse:
    total = sum(p.lines for p in doc.paragraphs)
    return models.InfeasibleResponse(
        summary=models.DocSummary(capacity=doc.capacity, total_lines=total),
        failure=models.FailureOut(
            paragraph_id=failure.paragraph_id,
            paragraph_index=failure.paragraph_index,
            prefix_paragraph_count=failure.paragraph_index,
            prefix_end_line=failure.prefix_end_line,
            footnote_ids=[f.id for f in failure.footnotes],
            footnotes=[
                models.FootnoteOut(id=f.id, marker_line=f.marker_line, height=f.height)
                for f in failure.footnotes
            ],
        ),
    )


@app.post(
    "/api/paginate",
    response_model=models.OkResponse | models.InfeasibleResponse,
)
def paginate(req: models.PaginateRequest) -> models.OkResponse | models.InfeasibleResponse:
    doc = _to_document(req)
    result = solver.solve(doc)
    if isinstance(result, solver.Failure):
        return _infeasible_response(doc, result)
    return _ok_response(doc, result)
