"""Routes handling authenticated plan ingestion uploads."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from ..config import INGESTION_API_TOKEN, PLAN_UPLOAD_ROOT
from ..services.plan_extractor import PlanExtractor
from ..services.plan_parser import PlanParser
from ..services.plan_repository import PlanDraftRepository

LOGGER = logging.getLogger(__name__)

router = APIRouter(prefix="/plans", tags=["plans"])
security = HTTPBearer()

_parser = PlanParser()
_extractor = PlanExtractor()
_repository = PlanDraftRepository()


def _authenticate(credentials: HTTPAuthorizationCredentials = Depends(security)) -> None:
    if credentials.scheme.lower() != "bearer" or credentials.credentials != INGESTION_API_TOKEN:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")


@router.post("/{teacher_id}/{year}")
async def ingest_plan(
    teacher_id: str,
    year: int,
    files: List[UploadFile] = File(...),
    _: None = Depends(_authenticate),
) -> dict[str, object]:
    if not files:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No files provided")

    upload_dir = PLAN_UPLOAD_ROOT / teacher_id / str(year)
    upload_dir.mkdir(parents=True, exist_ok=True)

    stored_paths: list[Path] = []
    try:
        for upload in files:
            destination = upload_dir / upload.filename
            with destination.open("wb") as buffer:
                buffer.write(await upload.read())
            stored_paths.append(destination)
            LOGGER.info("Stored plan upload at %s", destination)

        parsed = _parser.parse(stored_paths)
        extraction = _extractor.extract(parsed, teacher_id=teacher_id, year=year)
        draft = _repository.save(
            teacher_id=teacher_id,
            academic_year=year,
            structured_plan=extraction.structured_plan,
            raw_text=parsed.combined_text,
            tables=[table.to_dict() for table in parsed.tables],
            metadata=extraction.metadata,
        )
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001 - convert to HTTP errors
        LOGGER.exception("Plan ingestion failed")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc

    return {
        "draft_id": draft.id,
        "teacher_id": draft.teacher_id,
        "academic_year": draft.academic_year,
        "status": "pending_review",
        "metadata": draft.metadata,
    }


__all__ = ["router"]
