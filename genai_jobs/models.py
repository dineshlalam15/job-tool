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
    source: str  # e.g. "ats/workday", "amazon-api", "dork/ddg"
    description_snippet: str = ""  # first ~300 chars of description

    # Parsed experience bounds (-1 means not found)
    exp_min: int = -1   # minimum years required
    exp_max: int = -1   # maximum years required (-1 = open-ended / unknown)

    # Detected skillset tags (e.g. Generative AI, Agentic AI, LLM, RAG)
    skills: list[str] = Field(default_factory=list)

    # ── validators ───────────────────────────────────────────────────────────

    @field_validator("url", mode="before")
    @classmethod
    def _clean_url(cls, v: str) -> str:
        """
        Trim surrounding whitespace from a raw URL and prepend ``https://`` when
        no scheme is present.

        Args:
            v (str): Raw job application URL value supplied to the model.

        Returns:
            str: Cleaned URL string with an explicit HTTP/HTTPS scheme when non-empty.
        """
        v = str(v).strip()
        if v and not v.startswith("http"):
            v = "https://" + v
        return v

    @field_validator("title", "company", "location", mode="before")
    @classmethod
    def _strip_strings(cls, v: str) -> str:
        """
        Normalize text fields by converting falsy values to empty strings and
        stripping leading/trailing whitespace.

        Args:
            v (str): Raw field value for ``title``, ``company``, or ``location``.

        Returns:
            str: Trimmed string, or ``""`` when input is None or empty.
        """
        return str(v).strip() if v else ""

    # ── dedup key ────────────────────────────────────────────────────────────

    @property
    def dedup_key(self) -> str:
        """
        Compute a composite pipe-delimited canonical key from normalized URL,
        company, title, and location for deduplicating postings across engines.

        Args:
            None.

        Returns:
            str: Canonical lowercase deduplication identifier.
        """
        return "|".join([
            self.url.rstrip("/"),
            self.company.lower(),
            self.title.lower(),
            self.location.lower(),
        ])

    # ── display helpers ───────────────────────────────────────────────────────

    @property
    def date_str(self) -> str:
        """
        Format the job's ``date_posted`` attribute as ``YYYY-MM-DD`` for terminal display.

        Args:
            None.

        Returns:
            str: ISO date string when ``date_posted`` is present, otherwise ``"N/A"``.
        """
        return self.date_posted.strftime("%Y-%m-%d") if self.date_posted else "N/A"

    @property
    def experience_label(self) -> str:
        """
        Format parsed minimum/maximum experience year bounds into a concise label
        such as ``"Fresher"``, ``"≤ 2 yr"``, ``"3+ yr"``, ``"2–4 yr"``, or ``"N/A"``.

        Args:
            None.

        Returns:
            str: Human-readable required experience range string.
        """
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
        """
        Join detected skillset tags into a comma-separated display string,
        defaulting to ``"GenAI"`` when ``skills`` is empty.

        Args:
            None.

        Returns:
            str: Comma-separated skills label (e.g. ``"Generative AI, LLM, RAG"``).
        """
        return ", ".join(self.skills) if self.skills else "GenAI"
