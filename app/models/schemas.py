from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class SimulationOverrides(BaseModel):
    """Karşı-senaryoda eğitim şemasıyla uyumlu değiştirilebilir alanlar."""

    model_config = ConfigDict(extra="forbid")

    missing_document_count: int | None = Field(default=None, ge=0, le=50)
    revision_count: int | None = Field(default=None, ge=0, le=50)
    days_in_current_stage: float | None = Field(default=None, ge=0, le=3650)


class SimulationRequest(BaseModel):
    process_id: int = Field(gt=0)
    overrides: SimulationOverrides


class BatchPredictionRequest(BaseModel):
    process_ids: list[int] | None = Field(default=None, min_length=1)
    limit: int = Field(default=1_000, ge=1, le=10_000)


class FeedbackRequest(BaseModel):
    prediction_id: int = Field(gt=0)
    feedback_type: Literal["useful", "not_useful", "incorrect", "other"]
    comment: str | None = Field(default=None, max_length=1_000)
    actual_outcome: int | None = Field(default=None, ge=0, le=1)
