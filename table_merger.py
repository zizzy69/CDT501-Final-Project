# 文件名：table_merger.py
"""跨页表格拼接、表头相似度判断和冲突检测。"""

from __future__ import annotations

from dataclasses import dataclass, field
from difflib import SequenceMatcher
import re
from typing import Dict, Iterable, List, Sequence

from pdf_extractor import CellPosition, ExtractedTable


@dataclass
class MergedRow:
    values: List[str]
    page_number: int
    source_row_number: int
    table_index: int
    cell_positions: List[CellPosition]
    table_group: int


@dataclass
class MergedGroup:
    group_id: int
    headers: List[str]
    rows: List[MergedRow] = field(default_factory=list)


@dataclass
class Conflict:
    page_number: int
    table_index: int
    conflict_type: str
    message: str
    expected_header: str
    actual_header: str
    similarity: float


@dataclass
class MergeResult:
    groups: List[MergedGroup]
    conflicts: List[Conflict]
    mode: str


_UNIT_RE = re.compile(r"(?:\[|\(|/|\b)([a-zA-Zµμ%°]+(?:/[a-zA-Z]+)?)(?:\]|\)|\b)")
_ALIASES = {
    "temp": "temperature",
    "temperature": "temperature",
    "conc": "concentration",
    "concentration": "concentration",
    "qty": "quantity",
    "quantity": "quantity",
    "id": "id",
    "identifier": "id",
    "no": "id",
    "recordid": "id",
}


def _normalise_header_cell(value: str) -> str:
    value = str(value or "").lower().replace("µ", "u").replace("μ", "u")
    value = re.sub(r"\([^)]*\)|\[[^]]*\]", " ", value)
    value = re.sub(r"[^a-z0-9%°]+", " ", value)
    tokens = [_ALIASES.get(token, token) for token in value.split()]
    return "".join(tokens)


def _units(value: str) -> List[str]:
    text = str(value or "").lower().replace("µ", "u").replace("μ", "u")
    found = re.findall(r"(?:\[|\(|/|\b)([a-zA-Zu%°]+(?:/[a-zA-Z]+)?)(?:\]|\)|\b)", text)
    stop_words = {"id", "record", "name", "status", "value", "region", "unit", "pressure"}
    return [item for item in found if item not in stop_words]


def header_similarity(expected: Sequence[str], actual: Sequence[str]) -> float:
    """返回 0-1 的列级平均相似度；列数不同直接返回 0。"""

    if len(expected) != len(actual) or not expected:
        return 0.0
    scores = []
    for left, right in zip(expected, actual):
        left_norm = _normalise_header_cell(left)
        right_norm = _normalise_header_cell(right)
        if left_norm == right_norm and left_norm:
            scores.append(1.0)
        else:
            scores.append(SequenceMatcher(None, left_norm, right_norm).ratio())
    return sum(scores) / len(scores)


def _unit_mismatch(expected: Sequence[str], actual: Sequence[str]) -> bool:
    if len(expected) != len(actual):
        return True
    for left, right in zip(expected, actual):
        left_units = _units(left)
        right_units = _units(right)
        if left_units and right_units and left_units != right_units:
            return True
        if bool(left_units) != bool(right_units):
            return True
    return False


def _add_table_rows(group: MergedGroup, table: ExtractedTable, start_index: int = 1) -> None:
    for row_index in range(start_index, len(table.rows)):
        row = table.rows[row_index]
        positions = table.cell_positions[row_index]
        values = list(row[: len(group.headers)])
        values.extend([""] * (len(group.headers) - len(values)))
        group.rows.append(
            MergedRow(
                values=values,
                page_number=table.page_number,
                source_row_number=row_index + 1,
                table_index=table.table_index,
                cell_positions=positions[: len(group.headers)],
                table_group=group.group_id,
            )
        )


def merge_baseline(tables: Iterable[ExtractedTable]) -> MergeResult:
    """基线：以首页表头为 CSV 列名，后续页不做表头校验。"""

    tables = list(tables)
    if not tables:
        return MergeResult([], [], "baseline")
    first = tables[0]
    group = MergedGroup(group_id=1, headers=list(first.headers))
    for table in tables:
        _add_table_rows(group, table, start_index=1)
    return MergeResult([group], [], "baseline")


def merge_improved(tables: Iterable[ExtractedTable], similarity_threshold: float = 0.72) -> MergeResult:
    """改进模式：只将与首页表头兼容的表格放入主组，其余表格另建组并报警。"""

    tables = list(tables)
    if not tables:
        return MergeResult([], [], "improved")

    first = tables[0]
    groups = [MergedGroup(group_id=1, headers=list(first.headers))]
    conflicts: List[Conflict] = []
    _add_table_rows(groups[0], first, start_index=1)

    for table in tables[1:]:
        actual_header = list(table.headers)
        similarity = header_similarity(groups[0].headers, actual_header)
        type_name = ""
        if len(actual_header) != len(groups[0].headers):
            type_name = "column_count_mismatch"
        elif _unit_mismatch(groups[0].headers, actual_header):
            type_name = "unit_mismatch"
        elif similarity < similarity_threshold:
            type_name = "header_mismatch"

        if not type_name:
            _add_table_rows(groups[0], table, start_index=1)
            continue

        conflicts.append(
            Conflict(
                page_number=table.page_number,
                table_index=table.table_index,
                conflict_type=type_name,
                message="该页未与首页表头兼容，已单独建组，未强行拼接。",
                expected_header=" | ".join(groups[0].headers),
                actual_header=" | ".join(actual_header),
                similarity=round(similarity, 4),
            )
        )
        new_group = MergedGroup(group_id=len(groups) + 1, headers=actual_header)
        _add_table_rows(new_group, table, start_index=1)
        groups.append(new_group)

    return MergeResult(groups, conflicts, "improved")

