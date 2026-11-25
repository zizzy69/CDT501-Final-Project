# AGENTS.md

## 项目概览

这是 CDT501 C1 课程项目：从原生文本型 PDF 中提取标准行列表格，重建跨页表格，并生成可审计的单元格来源日志。项目还包含自动生成测试 PDF 和评测基线/改进模式的套件。

## 目录职责

- `main.py`：命令行入口，负责参数解析、运行流程和输出文件生成。
- `pdf_extractor.py`：使用 `tabula-py` 从 PDF 提取表格及单元格坐标。
- `table_merger.py`：实现基线模式、改进模式、表头相似度和冲突检测。
- `audit_trail.py`：写出重建表、审计日志和冲突报告。
- `test/`：测试 PDF 生成器、评测脚本和评测说明。
- `demo_output/`、`demo_baseline/`：示例运行结果；除非任务明确要求，不要把临时输出混入这里。
- `report/`：课程报告、证据截图和分析材料。
- `课程作业要求和报告模板/`：课程提供的要求与报告模板，仅作参考资料。

## 环境与运行

建议使用项目内的 Python 虚拟环境：

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

`tabula-py` 需要 Java 8 或更高版本。项目已包含 `.runtime/temurin17-jre`，如系统未配置 Java，先确认项目约定的 Java 配置是否可用。

运行改进模式：

```powershell
python main.py <input.pdf> <output_dir>
```

运行基线模式：

```powershell
python main.py <input.pdf> <output_dir> --baseline
```

运行完整评测：

```powershell
python test/generate_test_pdfs.py --output-dir test/data
python test/evaluate.py --data-dir test/data --output-dir test/results
```

快速评测可加入 `--samples-per-category 1`。

## 修改约定

- 保持 Python 3.9+ 兼容性，并遵循现有模块的类型标注和 dataclass 风格。
- 改动表格提取、合并或输出格式时，同时检查 `test/` 评测脚本及 `README.md` 中的行为描述。
- 改进模式必须保留表头/列数/单位冲突检测；不要为了提高拼接数量而静默合并不兼容表格。
- 审计信息是核心功能。新增或调整输出数据时，应保留来源页码、来源行号、表格组和坐标信息。
- 不要提交 `.venv/`、`__pycache__/`、临时 PDF、临时输出目录或本地环境配置；以 `.gitignore` 为准。
- 不要修改课程模板、报告证据或示例结果，除非任务明确涉及这些文件。

## 验证要求

完成代码修改后，至少运行相关 Python 文件的语法检查或对应评测；涉及跨页合并逻辑时，运行完整评测并检查：

- `summary_results.csv`
- `per_sample_results.csv`
- `failure_cases.csv`
- 改进模式生成的 `audit_trail.csv` 与 `conflict_report.csv`

命令失败时应记录具体原因，不要用删除测试数据或放宽断言的方式掩盖失败。

## 输出说明

默认改进模式输出主表 `reconstructed_table.csv`，不兼容表格输出为 `reconstructed_table_group_N.csv`，同时生成 `audit_trail.csv` 和 `conflict_report.csv`。输入不存在、缺少可用 Java 或 PDF 中没有标准表格时，应保持程序的明确报错/非零返回行为。
