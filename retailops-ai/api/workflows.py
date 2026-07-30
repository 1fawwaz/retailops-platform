"""Stage 4 Task 4.4: POST /workflow/inventory-health/run, POST
/workflow/business-review/run, and GET /report/{id} (+ markdown export
via ?format=markdown) -- the HTTP layer over
orchestration/workflows.py's two pipelines.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session, sessionmaker

from agents.report import HealthReport, PerformanceReport
from api.deps import get_current_subject, get_db_session_factory, get_stockpilot_client
from clients.stockpilot import StockPilotClient
from orchestration.models.base import JsonDict
from orchestration.models.report import Report as ReportRow
from orchestration.workflows import run_business_review_workflow, run_inventory_health_workflow

router = APIRouter(tags=["workflows"])


class InventoryHealthRequest(BaseModel):
    as_of_date: date | None = None
    max_recommendations: int | None = None


class BusinessReviewRequest(BaseModel):
    as_of_date: date | None = None
    period_days: int | None = None


class RecommendationOut(BaseModel):
    id: uuid.UUID
    sku: str
    action: str
    priority: str
    reason: str
    revenue_at_risk: float | None
    inventory_cost: float
    confidence: float
    risk_if_ignored: str
    evidence: list[str]


class InventoryHealthWorkflowResponse(BaseModel):
    execution_id: uuid.UUID
    report_id: uuid.UUID
    as_of_date: date | None
    backtest: bool
    markdown: str
    report: HealthReport
    recommendations: list[RecommendationOut]
    skipped_skus: list[str]


class BusinessReviewWorkflowResponse(BaseModel):
    execution_id: uuid.UUID
    report_id: uuid.UUID
    as_of_date: date | None
    backtest: bool
    markdown: str
    report: PerformanceReport


class ReportResponse(BaseModel):
    id: uuid.UUID
    execution_id: uuid.UUID
    report_type: str
    inputs: JsonDict | None
    outputs: JsonDict | None
    markdown: str | None
    as_of_date: date | None
    duration_ms: int | None
    cost_tokens: int | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


@router.post("/workflow/inventory-health/run", response_model=InventoryHealthWorkflowResponse)
def run_inventory_health(
    request: InventoryHealthRequest,
    _subject: str = Depends(get_current_subject),
    client: StockPilotClient = Depends(get_stockpilot_client),
    session_factory: sessionmaker[Session] = Depends(get_db_session_factory),
) -> InventoryHealthWorkflowResponse:
    result = run_inventory_health_workflow(
        client,
        session_factory,
        as_of_date=request.as_of_date,
        max_recommendations=request.max_recommendations,
    )
    return InventoryHealthWorkflowResponse(
        execution_id=result.execution_id,
        report_id=result.report_id,
        as_of_date=result.as_of_date,
        backtest=result.backtest,
        markdown=result.markdown,
        report=result.report,
        recommendations=[
            RecommendationOut(id=persisted.id, **persisted.recommendation.model_dump())
            for persisted in result.recommendations
        ],
        skipped_skus=result.skipped_skus,
    )


@router.post("/workflow/business-review/run", response_model=BusinessReviewWorkflowResponse)
def run_business_review(
    request: BusinessReviewRequest,
    _subject: str = Depends(get_current_subject),
    client: StockPilotClient = Depends(get_stockpilot_client),
    session_factory: sessionmaker[Session] = Depends(get_db_session_factory),
) -> BusinessReviewWorkflowResponse:
    result = run_business_review_workflow(
        client,
        session_factory,
        as_of_date=request.as_of_date,
        period_days=request.period_days,
    )
    return BusinessReviewWorkflowResponse(
        execution_id=result.execution_id,
        report_id=result.report_id,
        as_of_date=result.as_of_date,
        backtest=result.backtest,
        markdown=result.markdown,
        report=result.report,
    )


@router.get("/report/{report_id}")
def get_report(
    report_id: uuid.UUID,
    format: Literal["json", "markdown"] = Query(default="json"),
    _subject: str = Depends(get_current_subject),
    session_factory: sessionmaker[Session] = Depends(get_db_session_factory),
) -> Response:
    session = session_factory()
    try:
        report = session.get(ReportRow, report_id)
        if report is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=f"No report with id {report_id}"
            )
        if format == "markdown":
            return Response(content=report.markdown or "", media_type="text/markdown")
        body = ReportResponse.model_validate(report).model_dump_json()
        return Response(content=body, media_type="application/json")
    finally:
        session.close()
