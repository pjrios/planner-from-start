"""Async AI planning service used to generate topic activities and resources."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Iterable, Sequence


@dataclass(slots=True)
class PlannerTopic:
    """Context passed to the planner service when generating content."""

    topic_title: str
    topic_description: str | None
    scheduled_date: datetime
    class_name: str
    subject: str | None = None
    grade_level: str | None = None


@dataclass(slots=True)
class ActivityPlan:
    """Individual activity suggestion returned by the planner."""

    title: str
    description: str


@dataclass(slots=True)
class ResourcePlan:
    """Instructional resource suggestion returned by the planner."""

    name: str
    url: str | None = None
    type: str | None = None
    notes: str | None = None


@dataclass(slots=True)
class PlannerOutput:
    """Container for planner results and provenance metadata."""

    activities: Sequence[ActivityPlan] = field(default_factory=list)
    resources: Sequence[ResourcePlan] = field(default_factory=list)
    provenance: dict[str, Any] = field(default_factory=dict)


class _TemplatePlanner:
    """Fallback planner that produces structured but generic suggestions.

    The project expects to connect to a local LLM for real deployments. For unit and
    integration tests we rely on deterministic mocked responses. This lightweight
    fallback keeps the API functional without depending on heavyweight model
    downloads during development and CI runs.
    """

    model_name = "template-local-llm"

    def generate(self, topic: PlannerTopic) -> PlannerOutput:
        prompt_context = {
            "topic": topic.topic_title,
            "subject": topic.subject,
            "grade_level": topic.grade_level,
        }
        base_description = (
            topic.topic_description
            or f"Exploratory session covering {topic.topic_title.lower()}"
        )
        activity = ActivityPlan(
            title=f"Collaborative exploration of {topic.topic_title}",
            description=(
                f"Guide learners through a hands-on activity about {topic.topic_title}. "
                f"Use exit tickets to reinforce key takeaways. Context: {base_description}."
            ),
        )
        resource = ResourcePlan(
            name=f"Teacher notes for {topic.topic_title}",
            type="planning-notes",
            notes="Auto-generated outline; refine before sharing with students.",
        )
        provenance = {
            "model": self.model_name,
            "strategy": "template",
            "prompt_context": prompt_context,
            "generated_at": datetime.utcnow().isoformat(),
        }
        return PlannerOutput(
            activities=[activity],
            resources=[resource],
            provenance=provenance,
        )


class AIPlannerService:
    """Async adapter that wraps the local LLM/embedding powered planner."""

    def __init__(self, planner_impl: _TemplatePlanner | None = None) -> None:
        self._planner = planner_impl or _TemplatePlanner()

    async def generate(self, topic: PlannerTopic) -> PlannerOutput:
        """Generate activities and resources for a single topic."""

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._planner.generate, topic)

    async def generate_many(self, topics: Iterable[PlannerTopic]) -> list[PlannerOutput]:
        """Batch generate plans for a collection of topics."""

        tasks = [self.generate(topic) for topic in topics]
        if not tasks:
            return []
        return await asyncio.gather(*tasks)
