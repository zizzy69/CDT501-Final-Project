# 文件名：test/generate_test_pdfs.py
"""自动生成三类跨页表格 PDF、标准答案 CSV 和评测标注 JSON。"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Dict, List, Sequence, Union

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import PageBreak, SimpleDocTemplate, Spacer, Table, TableStyle


CATEGORIES = {
    "category1_standard": "标准布局",
    "category2_header_variation": "表头格式不一致",
    "category3_unfamiliar_layout": "陌生布局",
}


def _rows_for_sample(category: str, sample_number: int) -> List[Dict[str, object]]:
    rows: List[Dict[str, object]] = []
    for page in range(1, 4):
        for row_number in range(1, 4):
            record_id = f"{category[-1]}-{sample_number:02d}-{page:02d}-{row_number:02d}"
            group = 1
            unit = "kg"
            if category == "category3_unfamiliar_layout" and page == 3:
                record_id = f"{category[-1]}-{sample_number:02d}-B-{row_number:02d}"
                group = 2
                unit = "kPa"
            rows.append(
                {
                    "record_id": record_id,
                    "name": f"Item-{page}-{row_number}",
                    "value": f"{sample_number * 10 + page + row_number / 10:.1f}",
                    "status": "OK" if row_number != 3 else "CHECK",
                    "page": page,
                    "source_row": row_number + 1,
                    "expected_group": group,
                    "measurement_unit": unit,
                }
            )
    return rows


def _headers(category: str, page: int) -> Sequence[str]:
    if category == "category1_standard":
        return ["Record ID", "Name", "Value (kg)", "Status"]
    if category == "category2_header_variation":
        variants = [
            ["record id", "name", "value (kg)", "status"],
            ["Record\nID", " Name ", "Value [kg]", "STATUS"],
            ["ID", "Name", "Value / kg", "Status"],
        ]
        return variants[page - 1]
    if page < 3:
        return ["Record ID", "Name", "Value (kg)", "Status"]
    return ["ID", "Region", "Pressure (kPa)", "Unit", "Status"]


def _page_table(category: str, page: int, sample_number: int, truth_rows: List[Dict[str, object]]) -> Table:
    headers = list(_headers(category, page))
    page_rows = [row for row in truth_rows if row["page"] == page]
    data = [headers]
    if category == "category3_unfamiliar_layout" and page == 3:
        # 第二行模拟多行列头/单位行；原型边界不强行解释它，评测会记录该可疑行。
        data.append(["Code", "Area", "Measured pressure", "kPa", "State"])
    for row in page_rows:
        if category == "category3_unfamiliar_layout" and page == 3:
            data.append([row["record_id"], f"Region-{sample_number}", row["value"], "kPa", row["status"]])
        else:
            data.append([row["record_id"], row["name"], row["value"], row["status"]])

    table = Table(data, colWidths=[34 * mm, 38 * mm, 34 * mm, 30 * mm, 25 * mm][: len(headers)], repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#D9EAF7")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F5F8FA")]),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    return table


def _write_truth(path: Path, rows: List[Dict[str, object]]) -> None:
    fields = ["record_id", "name", "value", "status", "page", "source_row", "expected_group", "measurement_unit"]
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def generate_dataset(output_dir: Union[str, Path], samples_per_category: int = 5) -> None:
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    for category, description in CATEGORIES.items():
        category_dir = root / category
        category_dir.mkdir(parents=True, exist_ok=True)
        for sample_number in range(1, samples_per_category + 1):
            stem = f"sample_{sample_number:02d}"
            truth_rows = _rows_for_sample(category, sample_number)
            pdf_path = category_dir / f"{stem}.pdf"
            document = SimpleDocTemplate(
                str(pdf_path),
                pagesize=A4,
                rightMargin=18 * mm,
                leftMargin=18 * mm,
                topMargin=25 * mm,
                bottomMargin=25 * mm,
                title=f"C1 table reconstruction {category} {stem}",
            )
            story = []
            for page in range(1, 4):
                story.append(Spacer(1, 35 * mm))
                story.append(_page_table(category, page, sample_number, truth_rows))
                if page < 3:
                    story.append(PageBreak())
            document.build(story)
            _write_truth(category_dir / f"{stem}_truth.csv", truth_rows)
            labels = {
                "category": category,
                "description": description,
                "pdf": pdf_path.name,
                "truth_csv": f"{stem}_truth.csv",
                "expected_pages": 3,
                "expected_groups": sorted({int(row["expected_group"]) for row in truth_rows}),
                "measurement_units": sorted({str(row["measurement_unit"]) for row in truth_rows}),
                "layout_features": ["column_count_change", "multi_row_header", "unit_row_position_change"] if category == "category3_unfamiliar_layout" else [],
            }
            (category_dir / f"{stem}_labels.json").write_text(json.dumps(labels, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"已生成 {len(CATEGORIES) * samples_per_category} 份测试 PDF，位置：{root.resolve()}")


def main() -> int:
    parser = argparse.ArgumentParser(description="生成跨页 PDF 表格鲁棒性评测数据")
    parser.add_argument("--output-dir", default="test/data", help="数据集输出目录")
    parser.add_argument("--samples-per-category", type=int, default=5, help="每类样本数量，默认 5")
    args = parser.parse_args()
    generate_dataset(args.output_dir, args.samples_per_category)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

