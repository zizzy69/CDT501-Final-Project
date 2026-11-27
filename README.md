# 文件名：README.md

# 可审计的跨页 PDF 表格重建工具

本项目对应课程 C1 选题，包含两部分：

GitHub repository: https://github.com/zizzy69/CDT501-Final-Project

1. 小组原型：从原生文本型 PDF 提取标准行列表格，按表头和布局规则进行跨页重建，并输出可审计的单元格来源日志。
2. 个人自动化评测套件：自动生成 3 类测试 PDF，分别运行基线模式和改进模式，计算 False joins、Unit errors 和 Traceability rate。

## 适用范围

- 输入必须是原生文本型 PDF，不包含 OCR。
- 目标是标准行列表格；不处理复杂嵌套表格和斜线表头。
- `tabula-py` 依赖 Java 8+，请先安装 Java，并确保 `java -version` 可用。

## 安装

建议使用 Python 3.9 或更高版本并创建虚拟环境：

```bash
python -m venv .venv
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
# macOS/Linux
# source .venv/bin/activate
python -m pip install -r requirements.txt
```

## 原型运行

改进模式是默认模式：

```bash
python main.py input.pdf ./output
```

基线模式用于对照实验：

```bash
python main.py input.pdf ./output_baseline --baseline
```

## 本地 UI 演示

项目提供了一个基于 Python 标准库 Tkinter 的本地界面，不需要新增依赖：

```bash
python ui.py
```

界面可以选择 PDF 和输出目录，并分别运行改进模式或基线模式。运行完成后，右侧会列出 `reconstructed_table.csv`、`audit_trail.csv`、`conflict_report.csv` 和其他表格组 CSV；双击文件即可打开。界面会优先使用项目内的 `.runtime/temurin17-jre`，因此课堂演示时无需单独配置全局 Java。

课堂演示建议选择 `test/data/category3_unfamiliar_layout/sample_01.pdf`，这样可以同时展示改进模式的冲突检测和审计日志。

输出文件：

- `reconstructed_table.csv`：首页表头兼容的主表，数据行附带 `__source_page`、`__source_row` 和 `__table_group`。
- `reconstructed_table_group_N.csv`：改进模式发现不兼容表格时的独立表格组，避免把不同表格强行混在一起。
- `audit_trail.csv`：每个输出单元格的值、来源页、来源行、表格号和原始 PDF 坐标（left/top/width/height）。
- `conflict_report.csv`：表头相似度、列数变化、单位变化和未拼接页的冲突说明。

没有表格、输入文件不存在或缺少 Java 时，程序会输出清晰提示并返回非零状态，不会产生未声明的数据。

## 完整评测流程

```bash
python -m pip install -r requirements.txt
python test/generate_test_pdfs.py --output-dir test/data
python test/evaluate.py --data-dir test/data --output-dir test/results
```

## 在 VS Code 中运行

打开项目文件夹 `C:\Users\Dorian\Desktop\CDT501\501大作业`，选择解释器 `.venv\Scripts\python.exe`。项目已提供 `.vscode` 配置：

- `Run PDF table reconstruction`：运行改进模式，默认读取根目录的 `input.pdf`。
- `Run baseline reconstruction`：运行基线模式。
- `Ctrl+Shift+P` → `Tasks: Run Task` → `Generate test PDFs`：生成测试数据。
- `Ctrl+Shift+P` → `Tasks: Run Task` → `Evaluate prototype`：运行完整评测。

首次运行前必须安装 Java 8 或更高版本，并确保在 VS Code 新终端中执行 `java -version` 有输出。安装 Java 后重启 VS Code，再运行任务。

评测结果位于 `test/results/`：

- `summary_results.csv`：按测试类别和模式汇总平均值。
- `per_sample_results.csv`：每份 PDF 的详细指标。
- `failure_cases.csv`：错误类型、PDF 文件、页码和具体说明。

快速试跑可减少样本数：

```bash
python test/generate_test_pdfs.py --output-dir test/data --samples-per-category 1
python test/evaluate.py --data-dir test/data --output-dir test/results_quick
```

## 算法说明

- 基线模式使用首页表头作为 CSV 列名，后续表格只跳过其第一行并直接追加，不进行表头或单位检查。
- 改进模式将后续表头与首页表头按列进行字符串相似度匹配；大小写、空白、换行和常见缩写会归一化。
- 列数变化、单位变化或相似度低于阈值时，记录冲突，并将该表格放入新的输出组，不强行改写数据。
- 坐标来自 tabula-py 的 JSON 表格输出；审计日志同时保留来源页码和原始行号。

