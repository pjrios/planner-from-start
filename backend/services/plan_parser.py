"""Parsing utilities for uploaded lesson plans."""
from __future__ import annotations

import csv
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Iterator, List, Sequence, Tuple
from xml.etree import ElementTree
from zipfile import ZipFile

from ..document_loaders import load_document

LOGGER = logging.getLogger(__name__)


@dataclass
class ParsedTable:
    """Representation of a table extracted from a tabular document."""

    name: str
    headers: List[str]
    rows: List[dict[str, str]]

    def to_dict(self) -> dict[str, object]:
        return {"name": self.name, "headers": self.headers, "rows": self.rows}


@dataclass
class ParsedPlan:
    """Aggregated content produced after parsing uploaded plan files."""

    text_segments: List[str] = field(default_factory=list)
    tables: List[ParsedTable] = field(default_factory=list)
    sources: List[Path] = field(default_factory=list)

    @property
    def combined_text(self) -> str:
        return "\n\n".join(segment.strip() for segment in self.text_segments if segment.strip())


class PlanParser:
    """Parse teacher plan uploads into normalised text and table data."""

    TEXT_EXTENSIONS = {".pdf", ".docx", ".txt", ".md"}
    TABLE_EXTENSIONS = {".csv", ".xlsx"}

    def __init__(self) -> None:
        self._text_loader = load_document

    def parse(self, paths: Sequence[Path]) -> ParsedPlan:
        parsed = ParsedPlan()
        for path in paths:
            self._validate_path(path)
            suffix = path.suffix.lower()
            if suffix in self.TEXT_EXTENSIONS:
                LOGGER.debug("Parsing text document: %s", path)
                parsed.text_segments.append(self._parse_text(path))
            elif suffix == ".csv":
                LOGGER.debug("Parsing CSV document: %s", path)
                parsed.tables.append(self._parse_csv(path))
            elif suffix == ".xlsx":
                LOGGER.debug("Parsing XLSX document: %s", path)
                parsed.tables.extend(self._parse_xlsx(path))
            else:
                LOGGER.warning("Unsupported file extension for path %s", path)
                raise ValueError(f"Unsupported plan file type: {suffix}")
            parsed.sources.append(path)
        return parsed

    def _validate_path(self, path: Path) -> None:
        if not isinstance(path, Path):
            raise TypeError("PlanParser expects pathlib.Path instances")
        if not path.exists():
            raise FileNotFoundError(path)
        if not path.is_file():
            raise ValueError(f"Upload path is not a file: {path}")

    def _parse_text(self, path: Path) -> str:
        try:
            return self._text_loader(path)
        except Exception as exc:  # noqa: BLE001 - convert to ValueError
            LOGGER.exception("Failed to parse text document: %s", path)
            raise ValueError(f"Failed to parse text document: {path}") from exc

    def _parse_csv(self, path: Path) -> ParsedTable:
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            headers = reader.fieldnames or []
            rows: List[dict[str, str]] = []
            for row in reader:
                normalised_row: dict[str, str] = {}
                for index, (key, value) in enumerate(row.items()):
                    column_name = key or f"column_{index+1}"
                    normalised_row[column_name] = (value or "").strip()
                rows.append(normalised_row)
        if not headers and rows:
            headers = list(rows[0].keys())
        return ParsedTable(name=path.stem, headers=headers, rows=rows)

    def _parse_xlsx(self, path: Path) -> Iterable[ParsedTable]:
        with ZipFile(path) as archive:
            shared_strings = self._read_shared_strings(archive)
            sheets = list(self._iter_sheet_manifest(archive))
            tables: List[ParsedTable] = []
            for sheet_name, sheet_path in sheets:
                rows = self._read_sheet_rows(archive, sheet_path, shared_strings)
                if not rows:
                    continue
                headers = [
                    self._normalise_header(value, index)
                    for index, value in enumerate(rows[0])
                ]
                records: List[dict[str, str]] = []
                for raw_row in rows[1:]:
                    padded_row = list(raw_row) + [""] * (len(headers) - len(raw_row))
                    record = {
                        headers[index]: self._normalise_cell(value, index)
                        for index, value in enumerate(padded_row[: len(headers)])
                    }
                    if any(value for value in record.values()):
                        records.append(record)
                tables.append(
                    ParsedTable(
                        name=f"{path.stem}:{sheet_name}",
                        headers=headers,
                        rows=records,
                    )
                )
        return tables

    def _read_shared_strings(self, archive: ZipFile) -> List[str]:
        try:
            with archive.open("xl/sharedStrings.xml") as shared_file:
                tree = ElementTree.parse(shared_file)
        except KeyError:
            return []
        namespace = {"main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
        strings: List[str] = []
        for item in tree.findall("main:si", namespace):
            text_fragments = [node.text or "" for node in item.findall(".//main:t", namespace)]
            strings.append("".join(text_fragments))
        return strings

    def _iter_sheet_manifest(self, archive: ZipFile) -> Iterator[Tuple[str, str]]:
        namespace = {
            "main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
            "rel": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
            "pkg": "http://schemas.openxmlformats.org/package/2006/relationships",
        }
        with archive.open("xl/workbook.xml") as workbook_file:
            workbook_tree = ElementTree.parse(workbook_file)
        rels_path = "xl/_rels/workbook.xml.rels"
        with archive.open(rels_path) as rels_file:
            rels_tree = ElementTree.parse(rels_file)
        rel_map = {
            rel.attrib["Id"]: rel.attrib["Target"]
            for rel in rels_tree.findall("pkg:Relationship", namespace)
        }
        for sheet in workbook_tree.findall("main:sheets/main:sheet", namespace):
            sheet_name = sheet.attrib.get("name", "Sheet")
            rel_id = sheet.attrib.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")
            target = rel_map.get(rel_id)
            if not target:
                continue
            yield sheet_name, f"xl/{target}"

    def _read_sheet_rows(
        self,
        archive: ZipFile,
        sheet_path: str,
        shared_strings: Sequence[str],
    ) -> List[List[str]]:
        with archive.open(sheet_path) as sheet_file:
            tree = ElementTree.parse(sheet_file)
        namespace = {"main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
        rows: List[List[str]] = []
        for row in tree.findall("main:sheetData/main:row", namespace):
            values: List[str] = []
            for cell in row.findall("main:c", namespace):
                column_index = self._column_index(cell.attrib.get("r", ""))
                cell_value = self._resolve_cell_value(cell, shared_strings, namespace)
                while len(values) <= column_index:
                    values.append("")
                values[column_index] = cell_value
            rows.append(values)
        return rows

    def _resolve_cell_value(
        self,
        cell: ElementTree.Element,
        shared_strings: Sequence[str],
        namespace: dict[str, str],
    ) -> str:
        cell_type = cell.attrib.get("t")
        value_node = cell.find("main:v", namespace)
        if value_node is None:
            inline = cell.find("main:is/main:t", namespace)
            return (inline.text or "") if inline is not None else ""
        raw_value = value_node.text or ""
        if cell_type == "s":
            try:
                index = int(raw_value)
            except ValueError:
                return raw_value
            return shared_strings[index] if index < len(shared_strings) else raw_value
        return raw_value

    @staticmethod
    def _column_index(cell_reference: str) -> int:
        match = re.match(r"([A-Z]+)", cell_reference)
        if not match:
            return len(cell_reference)
        column_str = match.group(1)
        index = 0
        for char in column_str:
            index = index * 26 + (ord(char) - ord("A") + 1)
        return index - 1

    @staticmethod
    def _normalise_cell(value: object, index: int) -> str:
        if value is None:
            return ""
        return str(value).strip()

    @staticmethod
    def _normalise_header(value: object, index: int) -> str:
        base = PlanParser._normalise_cell(value, index)
        return base or f"column_{index+1}"


__all__ = ["PlanParser", "ParsedPlan", "ParsedTable"]
