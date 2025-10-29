"""Unit tests for the plan parser and extractor services."""
from __future__ import annotations

import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import pytest

from ..services.plan_extractor import PlanExtractor
from ..services.plan_parser import PlanParser


@pytest.fixture()
def sample_plan_files(tmp_path: Path) -> list[Path]:
    text_content = (
        "Title: Sample Lesson Plan\n"
        "Objectives:\n"
        "- Understand fractions\n"
        "- Apply knowledge to word problems\n\n"
        "Standards:\n"
        "- Common Core MAFS.3.NF.1.1\n\n"
        "Lesson Overview: Students will explore fractions using manipulatives."
    )
    text_path = tmp_path / "plan.txt"
    text_path.write_text(text_content, encoding="utf-8")

    csv_path = tmp_path / "schedule.csv"
    csv_path.write_text("day,activity\nMonday,Group work\nTuesday,Assessment\n", encoding="utf-8")

    xlsx_path = tmp_path / "materials.xlsx"
    _write_simple_xlsx(
        xlsx_path,
        headers=["Item", "Quantity"],
        rows=[["Fraction tiles", "30"], ["Worksheets", "60"]],
        sheet_name="Resources",
    )

    return [text_path, csv_path, xlsx_path]


def test_plan_parser_collects_text_and_tables(sample_plan_files: list[Path]) -> None:
    parser = PlanParser()
    parsed = parser.parse(sample_plan_files)

    assert "Sample Lesson Plan" in parsed.combined_text
    assert len(parsed.text_segments) == 1
    assert len(parsed.tables) == 2
    table_names = {table.name for table in parsed.tables}
    assert "schedule" in table_names
    assert any(name.endswith(":Resources") for name in table_names)


def test_plan_extractor_generates_structured_json(sample_plan_files: list[Path]) -> None:
    parser = PlanParser()
    parsed = parser.parse(sample_plan_files)

    extractor = PlanExtractor(load_model=False)
    result = extractor.extract(parsed, teacher_id="teacher-123", year=2024)

    structured = result.structured_plan
    assert structured["teacher_id"] == "teacher-123"
    assert structured["academic_year"] == 2024
    assert "Sample Lesson Plan" in structured["title"]
    assert "Understand fractions" in structured["objectives"][0]
    assert structured["tables"], "Expected tabular data to be preserved"

    # Ensure JSON serialisability for downstream review flows.
    json.dumps(structured)
    json.dumps(result.metadata)

    assert result.metadata["extraction_method"] in {"heuristic", "sentence-transformers"}
    assert sample_plan_files[0].as_posix() in result.metadata["source_files"][0]


def _write_simple_xlsx(
    path: Path,
    *,
    headers: list[str],
    rows: list[list[str]],
    sheet_name: str,
) -> None:
    from xml.sax.saxutils import escape

    def column_letter(index: int) -> str:
        index += 1
        letters = ""
        while index:
            index, remainder = divmod(index - 1, 26)
            letters = chr(ord("A") + remainder) + letters
        return letters

    all_rows = [headers, *rows]
    sheet_rows: list[str] = []
    for row_idx, values in enumerate(all_rows, start=1):
        cells: list[str] = []
        for col_idx, value in enumerate(values):
            cell_ref = f"{column_letter(col_idx)}{row_idx}"
            cell_value = escape(str(value))
            cells.append(
                f'<c r="{cell_ref}" t="inlineStr"><is><t>{cell_value}</t></is></c>'
            )
        sheet_rows.append(f'<row r="{row_idx}">' + "".join(cells) + "</row>")

    sheet_xml = (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
        "<worksheet xmlns=\"http://schemas.openxmlformats.org/spreadsheetml/2006/main\">"
        "<sheetData>"
        + "".join(sheet_rows)
        + "</sheetData></worksheet>"
    )

    workbook_xml = (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
        "<workbook xmlns=\"http://schemas.openxmlformats.org/spreadsheetml/2006/main\" "
        "xmlns:r=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships\">"
        "<sheets><sheet name=\""
        + escape(sheet_name)
        + "\" sheetId=\"1\" r:id=\"rId1\"/></sheets></workbook>"
    )

    workbook_rels = (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
        "<Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\">"
        "<Relationship Id=\"rId1\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet\" Target=\"worksheets/sheet1.xml\"/>"
        "</Relationships>"
    )

    root_rels = (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
        "<Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\">"
        "<Relationship Id=\"rId1\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument\" Target=\"xl/workbook.xml\"/>"
        "</Relationships>"
    )

    styles_xml = (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
        "<styleSheet xmlns=\"http://schemas.openxmlformats.org/spreadsheetml/2006/main\">"
        "<fonts count=\"1\"><font/></fonts>"
        "<fills count=\"1\"><fill/></fills>"
        "<borders count=\"1\"><border/></borders>"
        "<cellStyleXfs count=\"1\"><xf/></cellStyleXfs>"
        "<cellXfs count=\"1\"><xf/></cellXfs>"
        "</styleSheet>"
    )

    app_xml = (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
        "<Properties xmlns=\"http://schemas.openxmlformats.org/officeDocument/2006/extended-properties\" "
        "xmlns:vt=\"http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes\">"
        "<Application>Planner</Application></Properties>"
    )

    core_xml = (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
        "<cp:coreProperties xmlns:cp=\"http://schemas.openxmlformats.org/package/2006/metadata/core-properties\" "
        "xmlns:dc=\"http://purl.org/dc/elements/1.1/\" xmlns:dcterms=\"http://purl.org/dc/terms/\" "
        "xmlns:dcmitype=\"http://purl.org/dc/dcmitype/\" xmlns:xsi=\"http://www.w3.org/2001/XMLSchema-instance\">"
        "<dc:title>Generated</dc:title></cp:coreProperties>"
    )

    content_types = (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
        "<Types xmlns=\"http://schemas.openxmlformats.org/package/2006/content-types\">"
        "<Default Extension=\"rels\" ContentType=\"application/vnd.openxmlformats-package.relationships+xml\"/>"
        "<Default Extension=\"xml\" ContentType=\"application/xml\"/>"
        "<Override PartName=\"/xl/workbook.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml\"/>"
        "<Override PartName=\"/xl/worksheets/sheet1.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml\"/>"
        "<Override PartName=\"/xl/styles.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml\"/>"
        "<Override PartName=\"/docProps/core.xml\" ContentType=\"application/vnd.openxmlformats-package.core-properties+xml\"/>"
        "<Override PartName=\"/docProps/app.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.extended-properties+xml\"/>"
        "</Types>"
    )

    with ZipFile(path, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("_rels/.rels", root_rels)
        archive.writestr("docProps/app.xml", app_xml)
        archive.writestr("docProps/core.xml", core_xml)
        archive.writestr("xl/workbook.xml", workbook_xml)
        archive.writestr("xl/_rels/workbook.xml.rels", workbook_rels)
        archive.writestr("xl/styles.xml", styles_xml)
        archive.writestr("xl/worksheets/sheet1.xml", sheet_xml)
