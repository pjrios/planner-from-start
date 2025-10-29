"""FastAPI application exposing ingestion endpoints."""
from __future__ import annotations

import logging
from pathlib import Path
from datetime import date
from typing import List

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, validator

from .config import FRONTEND_DIR, TEMP_UPLOAD_DIR
from .pipeline import ingest_files
from . import database, scheduler, vector_store

LOGGER = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Planner Ingestion Service", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


if FRONTEND_DIR.exists():
    app.mount("/frontend", StaticFiles(directory=FRONTEND_DIR), name="frontend")
else:
    LOGGER.warning("Frontend directory %s not found", FRONTEND_DIR)


@app.on_event("startup")
def startup_event() -> None:
    database.init_db()


class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1)
    n_results: int = Field(5, ge=1, le=50)


class QueryResult(BaseModel):
    document: str
    metadata: dict[str, str]
    distance: float | None = None


class QueryResponse(BaseModel):
    query: str
    results: list[QueryResult]


class AcademicYearResponse(BaseModel):
    id: int
    name: str
    start_date: date
    end_date: date


class ReschedulingSuggestion(BaseModel):
    id: int
    class_id: int
    holiday_id: int
    suggestion: str
    class_name: str | None = None
    scheduled_date: date | None = None


class HolidayBase(BaseModel):
    name: str = Field(..., min_length=1)
    start_date: date
    end_date: date
    academic_year_id: int

    @validator("end_date")
    def validate_date_range(cls, end_date: date, values: dict) -> date:  # noqa: N805
        start = values.get("start_date")
        if start and end_date < start:
            raise ValueError("end_date must be on or after start_date")
        return end_date


class HolidayCreate(HolidayBase):
    pass


class HolidayUpdate(HolidayBase):
    pass


class HolidayResponse(BaseModel):
    id: int
    name: str
    start_date: date
    end_date: date
    academic_year_id: int
    suggestions: list[ReschedulingSuggestion] = Field(default_factory=list)


class ClassResponse(BaseModel):
    id: int
    name: str
    scheduled_date: date
    academic_year_id: int
    suggestions: list[ReschedulingSuggestion] = Field(default_factory=list)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/", include_in_schema=False)
def serve_frontend() -> FileResponse:
    index_path = FRONTEND_DIR / "index.html"
    if not index_path.exists():
        raise HTTPException(status_code=404, detail="Frontend assets not found")
    return FileResponse(index_path)


@app.post("/ingest")
async def ingest_endpoint(files: List[UploadFile] = File(...)) -> dict[str, int]:
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded")

    temp_paths: List[Path] = []
    try:
        for upload in files:
            destination = TEMP_UPLOAD_DIR / upload.filename
            with destination.open("wb") as buffer:
                buffer.write(await upload.read())
            temp_paths.append(destination)
            LOGGER.info("Saved upload %s", destination)

        result = ingest_files(temp_paths)
    except Exception as exc:  # noqa: BLE001 - convert to HTTP error
        LOGGER.exception("Ingestion failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        for path in temp_paths:
            if path.exists():
                path.unlink()
    return result


@app.post("/query", response_model=QueryResponse)
def query_endpoint(payload: QueryRequest) -> QueryResponse:
    results = vector_store.similarity_search(
        payload.query, n_results=payload.n_results
    )
    return QueryResponse(
        query=payload.query,
        results=[QueryResult(**item) for item in results],
    )


@app.get("/academic-years", response_model=list[AcademicYearResponse])
def list_academic_years() -> list[AcademicYearResponse]:
    with database.get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM academic_years ORDER BY DATE(start_date)"
        ).fetchall()
    return [AcademicYearResponse(**dict(row)) for row in rows]


@app.get("/classes", response_model=list[ClassResponse])
def list_classes(academic_year_id: int | None = None) -> list[ClassResponse]:
    with database.get_connection() as conn:
        query = "SELECT * FROM classes"
        params: tuple = ()
        if academic_year_id is not None:
            query += " WHERE academic_year_id = ?"
            params = (academic_year_id,)
        query += " ORDER BY DATE(scheduled_date)"
        rows = conn.execute(query, params).fetchall()
        class_ids = [row["id"] for row in rows]
        suggestions_lookup: dict[int, list[ReschedulingSuggestion]] = {id_: [] for id_ in class_ids}
        if class_ids:
            placeholders = ",".join(["?"] * len(class_ids))
            suggestion_rows = conn.execute(
                f"""
                SELECT rs.*, c.name AS class_name, c.scheduled_date
                FROM rescheduling_suggestions rs
                JOIN classes c ON c.id = rs.class_id
                WHERE rs.class_id IN ({placeholders})
                ORDER BY rs.id
                """,
                tuple(class_ids),
            ).fetchall()
            for row in suggestion_rows:
                suggestions_lookup[row["class_id"]].append(
                    ReschedulingSuggestion(**dict(row))
                )

        return [
            ClassResponse(
                id=row["id"],
                name=row["name"],
                scheduled_date=row["scheduled_date"],
                academic_year_id=row["academic_year_id"],
                suggestions=suggestions_lookup[row["id"]],
            )
            for row in rows
        ]


@app.get("/classes/{class_id}", response_model=ClassResponse)
def get_class(class_id: int) -> ClassResponse:
    with database.get_connection() as conn:
        return _load_class(conn, class_id)


@app.get("/holidays", response_model=list[HolidayResponse])
def list_holidays(academic_year_id: int | None = None) -> list[HolidayResponse]:
    with database.get_connection() as conn:
        query = "SELECT * FROM holidays"
        params: tuple = ()
        if academic_year_id is not None:
            query += " WHERE academic_year_id = ?"
            params = (academic_year_id,)
        query += " ORDER BY DATE(start_date)"
        rows = conn.execute(query, params).fetchall()

        responses = []
        for row in rows:
            suggestions_rows = conn.execute(
                """
                SELECT rs.*, c.name AS class_name, c.scheduled_date
                FROM rescheduling_suggestions rs
                JOIN classes c ON c.id = rs.class_id
                WHERE rs.holiday_id = ?
                ORDER BY rs.id
                """,
                (row["id"],),
            ).fetchall()

            responses.append(
                HolidayResponse(
                    id=row["id"],
                    name=row["name"],
                    start_date=row["start_date"],
                    end_date=row["end_date"],
                    academic_year_id=row["academic_year_id"],
                    suggestions=[ReschedulingSuggestion(**dict(item)) for item in suggestions_rows],
                )
            )
        return responses


@app.get("/holidays/{holiday_id}", response_model=HolidayResponse)
def get_holiday(holiday_id: int) -> HolidayResponse:
    with database.get_connection() as conn:
        holiday_row = conn.execute(
            "SELECT * FROM holidays WHERE id = ?", (holiday_id,)
        ).fetchone()
        if holiday_row is None:
            raise HTTPException(status_code=404, detail="Holiday not found")
        suggestions = conn.execute(
            """
            SELECT rs.*, c.name AS class_name, c.scheduled_date
            FROM rescheduling_suggestions rs
            JOIN classes c ON c.id = rs.class_id
            WHERE rs.holiday_id = ?
            ORDER BY rs.id
            """,
            (holiday_id,),
        ).fetchall()
        return HolidayResponse(
            id=holiday_row["id"],
            name=holiday_row["name"],
            start_date=holiday_row["start_date"],
            end_date=holiday_row["end_date"],
            academic_year_id=holiday_row["academic_year_id"],
            suggestions=[ReschedulingSuggestion(**dict(item)) for item in suggestions],
        )


@app.post("/holidays", response_model=HolidayResponse, status_code=201)
def create_holiday(payload: HolidayCreate) -> HolidayResponse:
    with database.get_connection() as conn:
        _ensure_academic_year(conn, payload.academic_year_id)
        cursor = conn.execute(
            """
            INSERT INTO holidays (name, start_date, end_date, academic_year_id)
            VALUES (?, ?, ?, ?)
            """,
            (
                payload.name,
                payload.start_date,
                payload.end_date,
                payload.academic_year_id,
            ),
        )
        holiday_id = cursor.lastrowid
        suggestions = scheduler.recompute_for_holiday(conn, holiday_id)
        holiday_row = conn.execute(
            "SELECT * FROM holidays WHERE id = ?", (holiday_id,)
        ).fetchone()
        return HolidayResponse(
            id=holiday_row["id"],
            name=holiday_row["name"],
            start_date=holiday_row["start_date"],
            end_date=holiday_row["end_date"],
            academic_year_id=holiday_row["academic_year_id"],
            suggestions=[ReschedulingSuggestion(**item) for item in suggestions],
        )


@app.put("/holidays/{holiday_id}", response_model=HolidayResponse)
def update_holiday(holiday_id: int, payload: HolidayUpdate) -> HolidayResponse:
    with database.get_connection() as conn:
        _ensure_academic_year(conn, payload.academic_year_id)
        existing = conn.execute(
            "SELECT id FROM holidays WHERE id = ?", (holiday_id,)
        ).fetchone()
        if existing is None:
            raise HTTPException(status_code=404, detail="Holiday not found")
        conn.execute(
            """
            UPDATE holidays
            SET name = ?, start_date = ?, end_date = ?, academic_year_id = ?
            WHERE id = ?
            """,
            (
                payload.name,
                payload.start_date,
                payload.end_date,
                payload.academic_year_id,
                holiday_id,
            ),
        )
        suggestions = scheduler.recompute_for_holiday(conn, holiday_id)
        holiday_row = conn.execute(
            "SELECT * FROM holidays WHERE id = ?", (holiday_id,)
        ).fetchone()
        return HolidayResponse(
            id=holiday_row["id"],
            name=holiday_row["name"],
            start_date=holiday_row["start_date"],
            end_date=holiday_row["end_date"],
            academic_year_id=holiday_row["academic_year_id"],
            suggestions=[ReschedulingSuggestion(**item) for item in suggestions],
        )


@app.delete("/holidays/{holiday_id}")
def delete_holiday(holiday_id: int) -> dict[str, str]:
    with database.get_connection() as conn:
        deleted = conn.execute(
            "DELETE FROM holidays WHERE id = ?", (holiday_id,)
        )
        if deleted.rowcount == 0:
            raise HTTPException(status_code=404, detail="Holiday not found")
    return {"status": "deleted"}


def _ensure_academic_year(conn, academic_year_id: int) -> None:
    year = conn.execute(
        "SELECT id FROM academic_years WHERE id = ?", (academic_year_id,)
    ).fetchone()
    if year is None:
        raise HTTPException(status_code=400, detail="Academic year not found")


def _load_class(conn, class_id: int) -> ClassResponse:
    class_row = conn.execute(
        "SELECT * FROM classes WHERE id = ?", (class_id,)
    ).fetchone()
    if class_row is None:
        raise HTTPException(status_code=404, detail="Class not found")

    suggestions_rows = conn.execute(
        """
        SELECT rs.*, c.name AS class_name, c.scheduled_date
        FROM rescheduling_suggestions rs
        JOIN classes c ON c.id = rs.class_id
        WHERE rs.class_id = ?
        ORDER BY rs.id
        """,
        (class_id,),
    ).fetchall()

    suggestions = [ReschedulingSuggestion(**dict(row)) for row in suggestions_rows]
    return ClassResponse(
        id=class_row["id"],
        name=class_row["name"],
        scheduled_date=class_row["scheduled_date"],
        academic_year_id=class_row["academic_year_id"],
        suggestions=suggestions,
    )
