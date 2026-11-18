# 文件名：main.py
"""可审计的跨页 PDF 表格重建工具命令行入口。"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Union

from audit_trail import write_audit_log, write_conflict_report, write_reconstructed_csv
from pdf_extractor import PdfExtractionError, extract_pdf_tables
from table_merger import merge_baseline, merge_improved


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="从原生文本型 PDF 中重建可审计的跨页表格")
    parser.add_argument("input_pdf", help="输入 PDF 文件路径")
    parser.add_argument("output_dir", help="输出目录")
    parser.add_argument("--baseline", action="store_true", help="使用基线模式：不检查跨页表头")
    return parser


def run(input_pdf: Union[str, Path], output_dir: Union[str, Path], baseline: bool = False) -> int:
    pdf_path = Path(input_pdf)
    output_path = Path(output_dir)
    if not pdf_path.exists():
        print(f"错误：输入文件不存在：{pdf_path}", file=sys.stderr)
        return 2
    output_path.mkdir(parents=True, exist_ok=True)

    try:
        tables = extract_pdf_tables(pdf_path)
    except PdfExtractionError as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 2

    if not tables:
        print("提示：PDF 中没有识别到标准行列表格，未生成重建表。", file=sys.stderr)
        write_audit_log([], output_path / "audit_trail.csv")
        write_conflict_report([], output_path / "conflict_report.csv")
        return 1

    result = merge_baseline(tables) if baseline else merge_improved(tables)
    main_file = output_path / "reconstructed_table.csv"
    write_reconstructed_csv(result.groups[0], main_file)
    for group in result.groups[1:]:
        write_reconstructed_csv(group, output_path / f"reconstructed_table_group_{group.group_id}.csv")
    write_audit_log(result.groups, output_path / "audit_trail.csv")
    write_conflict_report(result.conflicts, output_path / "conflict_report.csv")

    mode = "baseline" if baseline else "improved"
    total_rows = sum(len(group.rows) for group in result.groups)
    print(f"完成：{mode} 模式，识别 {len(tables)} 个表格，输出 {total_rows} 行数据。")
    print(f"主表：{main_file}")
    print(f"审计日志：{output_path / 'audit_trail.csv'}")
    print(f"冲突报告：{output_path / 'conflict_report.csv'}（{len(result.conflicts)} 条）")
    if len(result.groups) > 1:
        print(f"提示：检测到 {len(result.groups) - 1} 个不兼容表格组，已分别输出。")
    return 0


def main() -> int:
    args = build_parser().parse_args()
    return run(args.input_pdf, args.output_dir, baseline=args.baseline)


if __name__ == "__main__":
    raise SystemExit(main())

