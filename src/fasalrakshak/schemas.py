"""Typed schemas for the knowledge base and the safety gate inputs.

These models are the contract written in docs/DATA_SCHEMA.md, enforced in
code. Every knowledge base file must validate against them before it may be
used by any agent.
"""

from __future__ import annotations

from datetime import date as date_cls
from typing import Literal

from pydantic import BaseModel, Field, field_validator

BannedStatus = Literal["banned", "restricted"]


class Source(BaseModel):
    """Origin of a knowledge base entry. No source, no entry."""

    org: str = Field(min_length=3)
    title: str = Field(min_length=3)
    url: str = ""
    accessed: str

    @field_validator("accessed")
    @classmethod
    def _iso_date(cls, value: str) -> str:
        date_cls.fromisoformat(value)
        return value


class Product(BaseModel):
    """A registered crop-protection product with its label limits."""

    name: str = Field(min_length=3)
    active_ingredient: str
    dose: str
    dose_max: str
    unit: str = Field(min_length=1)
    phi_days: int = Field(ge=0)
    label_source: str = Field(min_length=3)

    @field_validator("dose", "dose_max")
    @classmethod
    def _decimal_string(cls, value: str) -> str:
        number = float(value)
        if number <= 0:
            raise ValueError("dose values must be positive")
        return value

    @field_validator("active_ingredient")
    @classmethod
    def _lowercase(cls, value: str) -> str:
        cleaned = value.strip().lower()
        if not cleaned:
            raise ValueError("active_ingredient must not be empty")
        return cleaned

    @property
    def dose_value(self) -> float:
        return float(self.dose)

    @property
    def dose_max_value(self) -> float:
        return float(self.dose_max)


class Treatment(BaseModel):
    summary: str = Field(min_length=3)
    steps: list[str] = Field(min_length=1)
    products: list[Product] = Field(default_factory=list)
    organic: list[str] = Field(default_factory=list)


class KBEntry(BaseModel):
    """One disease or pest entry in the knowledge base."""

    id: str
    crop: str
    disease: str = Field(min_length=3)
    pathogen: str = Field(min_length=3)
    aliases: list[str] = Field(default_factory=list)
    symptoms: list[str] = Field(min_length=2)
    severity_cues: dict[str, str] = Field(default_factory=dict)
    favorable_conditions: str = ""
    treatment: Treatment
    source: Source
    safety_notes: list[str] = Field(default_factory=list)

    @field_validator("id")
    @classmethod
    def _id_format(cls, value: str) -> str:
        if not value or value != value.strip() or " " in value:
            raise ValueError("id must be a non-empty slug without spaces")
        return value


class BannedEntry(BaseModel):
    """One active ingredient from the CIB&RC banned or restricted lists."""

    active_ingredient: str
    status: BannedStatus
    citation: str = Field(min_length=3)
    notes: str = ""

    @field_validator("active_ingredient")
    @classmethod
    def _lowercase(cls, value: str) -> str:
        cleaned = value.strip().lower()
        if not cleaned:
            raise ValueError("active_ingredient must not be empty")
        return cleaned


class BannedList(BaseModel):
    """Snapshot of the CIB&RC lists, dated, with a citation per entry."""

    snapshot_date: str
    source: str = Field(min_length=3)
    entries: list[BannedEntry] = Field(min_length=10)

    @field_validator("snapshot_date")
    @classmethod
    def _iso_date(cls, value: str) -> str:
        date_cls.fromisoformat(value)
        return value

    def ingredient_status(self, active_ingredient: str) -> BannedStatus | None:
        wanted = active_ingredient.strip().lower()
        for entry in self.entries:
            if entry.active_ingredient == wanted:
                return entry.status
        return None
