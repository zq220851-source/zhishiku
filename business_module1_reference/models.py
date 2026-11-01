"""Typed feedback; malformed or invented evidence never becomes a score."""
from pydantic import BaseModel, ConfigDict, Field
from typing import Literal


class Observation(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    criterion_id: str
    status: Literal['demonstrated', 'needs_work', 'uncertain']
    evidence_id: str | None = None
    quote: str = Field(default='', max_length=1600)
    turn_index: int = Field(default=0, ge=0)
    reason: str = Field(min_length=1, max_length=500)
    source_ids: list[str]


class Review(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    observations: list[Observation]
    next_question: str = Field(max_length=220)
    feedback: str = Field(min_length=1, max_length=600)
    focus: str = Field(min_length=1, max_length=300)
