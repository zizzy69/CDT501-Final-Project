# 文件名：test/evaluate.py
"""批量运行原型并计算 False joins、Unit errors、Traceability rate。"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Dict, Iterable, List, Tuple, Union


METRIC_FIELDS = ["false_joins", "unit_errors", "traceability_rate"]


@dataclass
class Failure:
    category: str
    mode: str
    pdf: str
    error_type: str
    page: str
    detail: str


def _normalise(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def _extract_unit(header: str) -> str:
    tokens = re.findall(r"(?:\(|\[|/|\b)([a-zA-Zµμ%°]+)(?:\]|\)|\b)", str(header))
    stop_words = {"record", "id", "name", "value", "status", "region", "unit", "pressure"}
    for token in reversed(tokens):
        token = token.lower().replace("µ", "u").replace("μ", "u")
        if token not in stop_words:
            return token
    return ""


def _read_csv(path: Path) -> List[Dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def _output_files(output_dir: Path) -> List[Path]:
    return sorted(output_dir.glob("reconstructed_table*.csv"))


def _evaluate_case(category: str, mode: str, pdf_path: Path, output_dir: Path, truth_path: Path) -> Tuple[Dict[str, object], List[Failure]]:
    truth = _read_csv(truth_path)
    truth_by_id = {row["record_id"]: row for row in truth}
    failures: List[Failure] = []
    false_joins = 0
    unit_errors = 0
    traceable_cells = 0
    total_cells = 0
    output_rows = 0

    for csv_path in _output_files(output_dir):
        records = _read_csv(csv_path)
        headers: List[str] = []
        if records:
            headers = [key for key in records[0] if not key.startswith("__")]
        measurement_columns = [(index, header, _extract_unit(header)) for index, header in enumerate(headers) if _extract_unit(header)]
        for record in records:
            output_rows += 1
            record_id = str(record.get("Record ID") or record.get("record id") or record.get("ID") or "").strip()
            truth_row = truth_by_id.get(record_id)
            page = str(record.get("__source_page", ""))
            actual_group = int(record.get("__table_group") or 0)
            if truth_row is None:
                false_joins += 1
                failures.append(Failure(category, mode, pdf_path.name, "false_join", page, f"输出记录 {record_id or '<空>'} 不在真值中；文件 {csv_path.name}"))
            else:
                expected_group = int(truth_row["expected_group"])
                if actual_group != expected_group:
                    false_joins += 1
                    failures.append(Failure(category, mode, pdf_path.name, "false_join", page, f"记录 {record_id} 应在组 {expected_group}，实际在组 {actual_group}"))
                for _, header, actual_unit in measurement_columns:
                    expected_unit = truth_row["measurement_unit"].lower()
                    if actual_unit != expected_unit:
                        unit_errors += 1
                        failures.append(Failure(category, mode, pdf_path.name, "unit_error", page, f"记录 {record_id} 的列 {header} 单位为 {actual_unit or '<空>'}，真值为 {expected_unit}"))

            for header in headers:
                total_cells += 1
                if page.isdigit() and int(page) > 0 and str(record.get("__source_row", "")).isdigit():
                    traceable_cells += 1
                else:
                    failures.append(Failure(category, mode, pdf_path.name, "untraceable", page, f"记录 {record_id or '<空>'} 的列 {header} 缺少有效页码或原始行号"))

    traceability_rate = traceable_cells / total_cells if total_cells else 0.0
    sample_result = {
        "category": category,
        "mode": mode,
        "pdf": pdf_path.name,
        "false_joins": false_joins,
        "unit_errors": unit_errors,
        "traceability_rate": round(traceability_rate, 6),
        "output_rows": output_rows,
        "process_ok": True,
    }
    return sample_result, failures


def _run_prototype(root: Path, pdf_path: Path, output_dir: Path, mode: str, python_executable: str) -> Tuple[bool, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    # 防止重复评测时遗留旧的分组 CSV 污染当前指标。
    old_outputs = list(output_dir.glob("reconstructed_table*.csv"))
    old_outputs.extend([output_dir / "audit_trail.csv", output_dir / "conflict_report.csv"])
    for old_output in old_outputs:
        if old_output.exists():
            old_output.unlink()
    command = [python_executable, str(root / "main.py"), str(pdf_path), str(output_dir)]
    if mode == "baseline":
        command.append("--baseline")
    completed = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if completed.returncode != 0:
        return False, (completed.stderr or completed.stdout).strip()
    return True, completed.stdout.strip()


def _write_csv(path: Path, rows: Iterable[Dict[str, object]], fields: List[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def evaluate(data_dir: Union[str, Path], output_dir: Union[str, Path], root: Union[str, Path], python_executable: str = sys.executable) -> None:
    data_root = Path(data_dir)
    result_root = Path(output_dir)
    project_root = Path(root)
    sample_results: List[Dict[str, object]] = []
    failures: List[Failure] = []

    for category_dir in sorted(path for path in data_root.iterdir() if path.is_dir()):
        for pdf_path in sorted(category_dir.glob("*.pdf")):
            stem = pdf_path.stem
            truth_path = category_dir / f"{stem}_truth.csv"
            if not truth_path.exists():
                failures.append(Failure(category_dir.name, "all", pdf_path.name, "missing_truth", "", str(truth_path)))
                continue
            for mode in ("baseline", "improved"):
                case_dir = result_root / mode / category_dir.name / stem
                ok, process_message = _run_prototype(project_root, pdf_path, case_dir, mode, python_executable)
                if not ok:
                    sample_results.append({"category": category_dir.name, "mode": mode, "pdf": pdf_path.name, "false_joins": "", "unit_errors": "", "traceability_rate": 0.0, "output_rows": 0, "process_ok": False})
                    failures.append(Failure(category_dir.name, mode, pdf_path.name, "process_error", "", process_message))
                    continue
                case_result, case_failures = _evaluate_case(category_dir.name, mode, pdf_path, case_dir, truth_path)
                sample_results.append(case_result)
                failures.extend(case_failures)

    _write_csv(result_root / "per_sample_results.csv", sample_results, ["category", "mode", "pdf", "false_joins", "unit_errors", "traceability_rate", "output_rows", "process_ok"])

    summary: List[Dict[str, object]] = []
    for category in sorted({str(row["category"]) for row in sample_results}):
        for mode in ("baseline", "improved"):
            rows = [row for row in sample_results if row["category"] == category and row["mode"] == mode and row["process_ok"]]
            if not rows:
                summary.append({"category": category, "mode": mode, "sample_count": 0, "avg_false_joins": "", "avg_unit_errors": "", "avg_traceability_rate": 0.0})
                continue
            summary.append(
                {
                    "category": category,
                    "mode": mode,
                    "sample_count": len(rows),
                    "avg_false_joins": round(sum(float(row["false_joins"]) for row in rows) / len(rows), 4),
                    "avg_unit_errors": round(sum(float(row["unit_errors"]) for row in rows) / len(rows), 4),
                    "avg_traceability_rate": round(sum(float(row["traceability_rate"]) for row in rows) / len(rows), 6),
                }
            )
    _write_csv(result_root / "summary_results.csv", summary, ["category", "mode", "sample_count", "avg_false_joins", "avg_unit_errors", "avg_traceability_rate"])
    _write_csv(result_root / "failure_cases.csv", [failure.__dict__ for failure in failures], ["category", "mode", "pdf", "error_type", "page", "detail"])

    print(f"评测完成：{len(sample_results)} 个模式-样本组合")
    print(f"汇总结果：{result_root / 'summary_results.csv'}")
    print(f"失败案例：{result_root / 'failure_cases.csv'}（{len(failures)} 条）")


def main() -> int:
    parser = argparse.ArgumentParser(description="批量评测跨页 PDF 表格重建原型")
    parser.add_argument("--data-dir", default="test/data", help="测试数据目录")
    parser.add_argument("--output-dir", default="test/results", help="评测输出目录")
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[1]), help="项目根目录")
    parser.add_argument("--python", default=sys.executable, dest="python_executable", help="运行原型的 Python 解释器")
    args = parser.parse_args()
    if not Path(args.data_dir).exists():
        print(f"错误：数据目录不存在，请先运行 generate_test_pdfs.py：{args.data_dir}", file=sys.stderr)
        return 2
    evaluate(args.data_dir, args.output_dir, args.root, args.python_executable)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

