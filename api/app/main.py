"""FastAPI 入口：分页计算 API。"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from . import models, solver

app = FastAPI(title="古籍校勘版分页 API", version="1.1.0")

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
        directives=tuple(
            solver.Directive(d.kind, d.paragraph_id, d.line_in_paragraph, order)
            for order, d in enumerate(req.directives)
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


def _invalid_directive_out(item: solver.InvalidDirective) -> models.InvalidDirectiveOut:
    return models.InvalidDirectiveOut(
        order=item.order,
        kind=item.kind,
        paragraph_id=item.paragraph_id,
        line_in_paragraph=item.line_in_paragraph,
        reason=item.reason,
    )


def _directive_ref(doc: solver.Document, order: int) -> models.DirectiveRefOut:
    d = next(d for d in doc.directives if d.order == order)
    return models.DirectiveRefOut(
        order=d.order,
        kind=d.kind,
        paragraph_id=d.paragraph_id,
        line_in_paragraph=d.line_in_paragraph,
    )


def _ok_response(
    doc: solver.Document,
    solution: solver.Solution,
    *,
    has_directives: bool,
    confirmed_releases: frozenset[int],
) -> models.OkResponse:
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
    valid_orders = {d.order for d in doc.directives} - {
        i.order for i in solution.invalid_directives
    }
    released = set(solution.violated_directives)
    if has_directives:
        # 求解器是否在用户已确认释放之外又追加了释放：追加即为「待确认建议」
        release_confirmed = released <= {o for o in confirmed_releases if o in valid_orders}
        directive_fields = {
            "directives_satisfied": len(released) == 0,
            "active_directive_count": len(valid_orders),
            "invalid_directives": [_invalid_directive_out(i) for i in solution.invalid_directives],
            "released_directives": [_directive_ref(doc, o) for o in sorted(released)],
            "release_confirmed": release_confirmed,
        }
    else:
        directive_fields = {
            "directives_satisfied": None,
            "active_directive_count": None,
            "invalid_directives": None,
            "released_directives": None,
            "release_confirmed": None,
        }
    return models.OkResponse(
        summary=models.OkSummary(
            capacity=doc.capacity,
            total_lines=total,
            page_count=len(solution.pages),
            squared_slack=solution.squared_slack,
            ending_lines=list(solution.ending_lines),
        ),
        pages=pages,
        **directive_fields,
    )


def _infeasible_response(
    doc: solver.Document,
    failure: solver.Failure,
    *,
    has_directives: bool,
) -> models.InfeasibleResponse:
    total = sum(p.lines for p in doc.paragraphs)
    invalid_out = (
        [_invalid_directive_out(i) for i in failure.invalid_directives]
        if has_directives
        else None
    )
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
            invalid_directives=invalid_out,
        ),
    )


@app.post(
    "/api/paginate",
    response_model=models.OkResponse | models.InfeasibleResponse,
)
def paginate(req: models.PaginateRequest):
    doc = _to_document(req)
    result = solver.solve(doc, released_orders=frozenset(req.release_directives))
    has_directives = bool(req.directives)
    if isinstance(result, solver.Failure):
        resp = _infeasible_response(doc, result, has_directives=has_directives)
        payload = resp.model_dump()
        # 未携带指令的旧失败请求：failure 内不出现新字段，其余逐字段保持原样
        if not has_directives:
            payload["failure"].pop("invalid_directives", None)
    else:
        resp = _ok_response(
            doc,
            result,
            has_directives=has_directives,
            confirmed_releases=frozenset(req.release_directives),
        )
        payload = resp.model_dump()
        # 未携带指令的旧成功请求：顶层不出现任何指令字段
        if not has_directives:
            for key in (
                "directives_satisfied",
                "active_directive_count",
                "invalid_directives",
                "released_directives",
                "release_confirmed",
            ):
                payload.pop(key, None)
    # 直接返回 JSONResponse 以避免 response_model 二次序列化把已剔除字段补回；
    # break_after 等旧结构中的 null 字段（paragraph_id 等）保持原样不动。
    return JSONResponse(payload)
