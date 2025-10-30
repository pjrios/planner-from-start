"""LLM-assisted extraction of structured lesson plan data."""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable, List, Optional

try:  # pragma: no cover - optional heavy dependency
    from sentence_transformers import SentenceTransformer
except Exception:  # noqa: BLE001 - optional dependency may not be available
    SentenceTransformer = None  # type: ignore[assignment]

from .plan_parser import ParsedPlan

LOGGER = logging.getLogger(__name__)


@dataclass
class ExtractionResult:
    """Container for structured plan data and provenance metadata."""

    structured_plan: dict[str, Any]
    metadata: dict[str, Any]


class PlanExtractor:
    """Transform raw parsed content into the canonical plan schema."""

    def __init__(
        self,
        model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
        *,
        load_model: bool = True,
    ) -> None:
        self.model_name = model_name
        self._model: Optional[SentenceTransformer] = None
        if load_model and SentenceTransformer is not None:
            try:
                self._model = SentenceTransformer(model_name)
                LOGGER.info("Loaded sentence-transformers model '%s'", model_name)
            except Exception as exc:  # noqa: BLE001 - optional dependency
                LOGGER.warning("Falling back to heuristic extraction: %s", exc)
                self._model = None
        elif SentenceTransformer is None:
            LOGGER.info("sentence-transformers not available, using heuristics")

    def extract(self, parsed: ParsedPlan, *, teacher_id: str, year: int) -> ExtractionResult:
        combined_text = parsed.combined_text
        sentences = self._split_sentences(combined_text)
        title = self._extract_title(sentences)
        objectives = self._extract_bullet_list(combined_text, ("objective", "goal"))
        standards = self._extract_bullet_list(combined_text, ("standard", "curriculum"))
        summary = self._summarise(sentences)
        tables = [table.to_dict() for table in parsed.tables]

        structured_plan: dict[str, Any] = {
            "teacher_id": teacher_id,
            "academic_year": year,
            "title": title,
            "summary": summary,
            "objectives": objectives,
            "standards": standards,
            "tables": tables,
        }

        metadata = {
            "extracted_at": datetime.now(tz=timezone.utc).isoformat(),
            "source_files": [str(path) for path in parsed.sources],
            "extraction_method": "sentence-transformers" if self._model else "heuristic",
            "confidence": self._estimate_confidence(title, objectives, standards, tables),
        }

        return ExtractionResult(structured_plan=structured_plan, metadata=metadata)

    def _split_sentences(self, text: str) -> List[str]:
        sentences = re.split(r"(?<=[.!?])\s+", text.strip())
        return [sentence.strip() for sentence in sentences if sentence.strip()]

    def _extract_title(self, sentences: Iterable[str]) -> str:
        for sentence in sentences:
            title_match = re.search(r"^(lesson\s+plan\s*:?|title\s*:)(?P<title>.+)$", sentence, re.I)
            if title_match:
                return title_match.group("title").strip()
        return next(iter(sentences), "Untitled Lesson Plan")

    def _extract_bullet_list(self, text: str, keywords: Iterable[str]) -> List[str]:
        keyword_pattern = "|".join(keywords)
        pattern = rf"(?:^|\n)(?:{keyword_pattern})s?\s*:\s*(?P<body>.*?)(?:\n\s*\n|$)"
        match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        if not match:
            return []
        body = match.group("body")
        bullet_lines = re.split(r"\n|;", body)
        values = []
        for line in bullet_lines:
            normalised = line.strip(" -*\t")
            if normalised:
                values.append(normalised)
        return values

    def _summarise(self, sentences: List[str]) -> str:
        if not sentences:
            return ""
        if self._model is None or len(sentences) == 1:
            return sentences[0]
        # Use embeddings to choose the most representative sentence when model is available.
        try:
            embeddings = self._model.encode(sentences)  # type: ignore[union-attr]
        except Exception as exc:  # noqa: BLE001 - fallback to heuristic summary
            LOGGER.debug("Embedding-based summary failed: %s", exc)
            return sentences[0]
        centroid = embeddings.mean(axis=0)
        best_index = int(((embeddings - centroid) ** 2).sum(axis=1).argmin())
        return sentences[best_index]

    def _estimate_confidence(
        self,
        title: str,
        objectives: List[str],
        standards: List[str],
        tables: List[dict[str, Any]],
    ) -> float:
        score = 0.25
        if title and title.lower() != "untitled lesson plan":
            score += 0.25
        if objectives:
            score += 0.25
        if standards or tables:
            score += 0.25
        return round(min(score, 0.99), 2)


__all__ = ["PlanExtractor", "ExtractionResult"]
