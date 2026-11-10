"""
genai_jobs/models.py
─────────────────────────────────────────────────────────────────────────────
Shared Pydantic data model for a normalised job posting.
"""
from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class JobPosting(BaseModel):
    """Normalised, deduplicated job record surfaced by any engine."""

    company: str
    title: str
    location: str = ""
    date_posted: Optional[date] = None
    url: str
    source: str  # e.g. "jobspy/linkedin", "dork/ddg", "amazon-api"
    description_snippet: str = ""  # first ~300 chars of description for display

    # Parsed experience bounds (EXPERIENCE_UNKNOWN = -1 means not found)
    exp_min: int = -1   # minimum years required
    exp_max: int = -1   # maximum years required (-1 = open-ended / unknown)

    # Detected skillset tags (e.g. GenAI, Agentic AI, RAG, Python)
    skills: list[str] = Field(default_factory=list)

    # ── validators ───────────────────────────────────────────────────────────

    @field_validator("url", mode="before")
    @classmethod
    def _clean_url(cls, v: str) -> str:
        v = str(v).strip()
        if v and not v.startswith("http"):
            v = "https://" + v
        return v

    @field_validator("title", "company", "location", mode="before")
    @classmethod
    def _strip_strings(cls, v: str) -> str:
        return str(v).strip() if v else ""

    # ── dedup key ────────────────────────────────────────────────────────────

    @property
    def dedup_key(self) -> str:
        """Canonical key used for deduplication across sources."""
        return "|".join([
            self.url.rstrip("/"),
            self.company.lower(),
            self.title.lower(),
            self.location.lower(),
        ])

    # ── display helpers ───────────────────────────────────────────────────────

    @property
    def date_str(self) -> str:
        return self.date_posted.strftime("%Y-%m-%d") if self.date_posted else "N/A"

    @property
    def experience_label(self) -> str:
        """Human-readable experience string for table/report display."""
        lo, hi = self.exp_min, self.exp_max
        if lo == -1 and hi == -1:
            return "N/A"
        if lo == 0 and hi == 0:
            return "Fresher"
        if lo == -1:
            return f"≤ {hi} yr"
        if hi == -1:
            return f"{lo}+ yr"
        if lo == hi:
            return f"{lo} yr"
        return f"{lo}–{hi} yr"

    @property
    def skills_label(self) -> str:
        """Comma-separated skills label (e.g. 'GenAI, Agentic AI, Python')."""
        return ", ".join(self.skills) if self.skills else "GenAI"

    def to_dict(self) -> dict:
        return {
            "company": self.company,
            "title": self.title,
            "location": self.location,
            "date_posted": self.date_str,
            "experience": self.experience_label,
            "skills": self.skills_label,
            "source": self.source,
            "url": self.url,
            "description_snippet": self.description_snippet,
        }
