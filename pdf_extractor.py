# 文件名：pdf_extractor.py
"""使用 tabula-py 提取原生文本型 PDF 中的表格及单元格坐标。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import re


@dataclass
class CellPosition:
    """单元格文本及其在 PDF 页面中的原始坐标。"""

    text: str
    left: Optional[float] = None
    top: Optional[float] = None
    width: Optional[float] = None
    height: Optional[float] = None


@dataclass
class ExtractedTable:
    """单个 PDF 表格，第一行为约定的表头。"""

    page_number: int
    table_index: int
    rows: List[List[str]]
    cell_positions: List[List[CellPosition]]

    @property
    def headers(self) -> List[str]:
        return self.rows[0] if self.rows else []


class PdfExtractionError(RuntimeError):
    """表格提取失败时使用的可读异常。"""


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).replace("\r", " ").replace("\n", " ")
    return re.sub(r"\s+", " ", text).strip()


def _number(value: Any) -> Optional[float]:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _count_pdf_pages(pdf_path: Path) -> int:
    """轻量级估算页数，避免为课程项目再引入 PDF 解析依赖。"""

    data = pdf_path.read_bytes()
    matches = re.findall(rb"/Type\s*/Page\b", data)
    return len(matches)


def _normalise_json_table(raw_table: Dict[str, Any], page_number: int, table_index: int) -> Optional[ExtractedTable]:
    raw_rows = raw_table.get("data") if isinstance(raw_table, dict) else None
    if not raw_rows:
        return None

    rows: List[List[str]] = []
    positions: List[List[CellPosition]] = []
    max_columns = 0
    for raw_row in raw_rows:
        if not isinstance(raw_row, list):
            continue
        row_values: List[str] = []
        row_positions: List[CellPosition] = []
        for raw_cell in raw_row:
            if isinstance(raw_cell, dict):
                row_values.append(_clean_text(raw_cell.get("text", "")))
                row_positions.append(
                    CellPosition(
                        text=_clean_text(raw_cell.get("text", "")),
                        left=_number(raw_cell.get("left")),
                        top=_number(raw_cell.get("top")),
                        width=_number(raw_cell.get("width")),
                        height=_number(raw_cell.get("height")),
                    )
                )
            else:
                row_values.append(_clean_text(raw_cell))
                row_positions.append(CellPosition(text=_clean_text(raw_cell)))
        if any(row_values):
            rows.append(row_values)
            positions.append(row_positions)
            max_columns = max(max_columns, len(row_values))

    if not rows:
        return None

    # 将 tabula 对缺失单元格的短行补齐，保证后续 CSV 列数稳定。
    for row, row_positions in zip(rows, positions):
        while len(row) < max_columns:
            row.append("")
            row_positions.append(CellPosition(text=""))
    return ExtractedTable(page_number, table_index, rows, positions)


def extract_page_tables(pdf_path: Union[str, Path], page_number: int) -> List[ExtractedTable]:
    """提取指定页的表格；返回空列表表示该页没有可识别表格。"""

    try:
        import tabula
    except ImportError as exc:
        raise PdfExtractionError("缺少 tabula-py，请先安装 requirements.txt 中的依赖。") from exc

    def _read(extraction_mode: str):
        return tabula.read_pdf(
            str(pdf_path),
            pages=page_number,
            multiple_tables=True,
            output_format="json",
            lattice=extraction_mode == "lattice",
            stream=extraction_mode == "stream",
            guess=False,
        )

    try:
        # 有边框的原生表格优先使用 lattice，可保留换行表头在同一单元格内；
        # 对无边框文本表格回退到 stream 模式。
        raw_tables = _read("lattice")
        if not raw_tables:
            raw_tables = _read("stream")
    except Exception as exc:  # tabula 对 Java、PDF 解析错误的异常类型跨版本不同
        message = str(exc)
        if "java" in message.lower() or "jpype" in message.lower():
            message += "；请确认已安装 Java 8+ 并设置 JAVA_HOME。"
        raise PdfExtractionError(f"第 {page_number} 页表格提取失败：{message}") from exc

    if isinstance(raw_tables, dict):
        raw_tables = [raw_tables]
    result: List[ExtractedTable] = []
    for index, raw_table in enumerate(raw_tables or [], start=1):
        table = _normalise_json_table(raw_table, page_number, index)
        if table is not None and len(table.rows) >= 1:
            result.append(table)
    return result


def extract_pdf_tables(pdf_path: Union[str, Path]) -> List[ExtractedTable]:
    """按页提取 PDF 中的所有表格，并保留页码、表格号和单元格坐标。"""

    path = Path(pdf_path)
    if not path.exists():
        raise PdfExtractionError(f"输入文件不存在：{path}")
    if path.suffix.lower() != ".pdf":
        raise PdfExtractionError(f"输入文件不是 PDF：{path}")

    page_count = _count_pdf_pages(path)
    if page_count <= 0:
        raise PdfExtractionError("无法读取 PDF 页数，文件可能损坏或不是标准 PDF。")

    tables: List[ExtractedTable] = []
    for page_number in range(1, page_count + 1):
        tables.extend(extract_page_tables(path, page_number))
    return tables

