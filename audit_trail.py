# 文件名：audit_trail.py
"""写出重建表、单元格审计日志和冲突报告。"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterable, List, Union

import pandas as pd

from table_merger import Conflict, MergedGroup, MergedRow


def _safe(value: object) -> object:
    return "" if value is None else value


def write_reconstructed_csv(group: MergedGroup, output_path: Union[str, Path]) -> None:
    """写出一个表格组；元数据列以双下划线开头，避免与原始列名冲突。"""

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(group.headers) + ["__source_page", "__source_row", "__table_group"]
    records = []
    for row in group.rows:
        record = {header: _safe(row.values[index] if index < len(row.values) else "") for index, header in enumerate(group.headers)}
        record.update(
            {
                "__source_page": row.page_number,
                "__source_row": row.source_row_number,
                "__table_group": row.table_group,
            }
        )
        records.append(record)
    # 使用 pandas 统一处理 CSV 编码和列顺序，避免不同表格组的空列被丢弃。
    pd.DataFrame(records, columns=fieldnames).to_csv(path, index=False, encoding="utf-8-sig")


def write_audit_log(groups: Iterable[MergedGroup], output_path: Union[str, Path]) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "table_group",
        "output_row",
        "column_index",
        "column_name",
        "cell_value",
        "source_page",
        "source_table_index",
        "source_row",
        "left",
        "top",
        "width",
        "height",
        "coordinate_system",
    ]
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for group in groups:
            for output_row, row in enumerate(group.rows, start=1):
                for index, header in enumerate(group.headers):
                    position = row.cell_positions[index] if index < len(row.cell_positions) else None
                    writer.writerow(
                        {
                            "table_group": group.group_id,
                            "output_row": output_row,
                            "column_index": index + 1,
                            "column_name": header,
                            "cell_value": row.values[index] if index < len(row.values) else "",
                            "source_page": row.page_number,
                            "source_table_index": row.table_index,
                            "source_row": row.source_row_number,
                            "left": getattr(position, "left", None),
                            "top": getattr(position, "top", None),
                            "width": getattr(position, "width", None),
                            "height": getattr(position, "height", None),
                            "coordinate_system": "PDF points; origin is top-left in tabula JSON output",
                        }
                    )


def write_conflict_report(conflicts: Iterable[Conflict], output_path: Union[str, Path]) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "page_number",
        "table_index",
        "conflict_type",
        "message",
        "expected_header",
        "actual_header",
        "similarity",
    ]
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for conflict in conflicts:
            writer.writerow(
                {
                    "page_number": conflict.page_number,
                    "table_index": conflict.table_index,
                    "conflict_type": conflict.conflict_type,
                    "message": conflict.message,
                    "expected_header": conflict.expected_header,
                    "actual_header": conflict.actual_header,
                    "similarity": conflict.similarity,
                }
            )

