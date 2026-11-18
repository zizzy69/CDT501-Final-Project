# C1 项目需求核对与运行审计报告

## 1. 结论

当前项目已经覆盖 C1「Auditable cross-page PDF table reconstruction」的原型和路线 A 鲁棒性评测要求，并已完成一次真实运行验证。评测使用 3 类、每类 5 份、每份 3 页的 reportlab 原生文本型 PDF，共 15 份样本；baseline 和 improved 两种模式共 30 个组合均成功运行。

实际汇总结果如下：

| 测试类别 | 模式 | 平均 False joins | 平均 Unit errors | Traceability rate |
|---|---:|---:|---:|---:|
| 标准布局 | baseline | 0.0 | 0.0 | 1.000000 |
| 标准布局 | improved | 0.0 | 0.0 | 1.000000 |
| 表头格式变化 | baseline | 0.0 | 0.0 | 1.000000 |
| 表头格式变化 | improved | 0.0 | 0.0 | 1.000000 |
| 陌生布局 | baseline | 4.0 | 3.0 | 1.000000 |
| 陌生布局 | improved | 1.0 | 0.0 | 1.000000 |

陌生布局的第 3 页故意包含列数变化、多行列头和单位行位置变化。改进模式将它分成独立表格组并输出冲突报告，因此没有把单位错误强行混入主表；剩余 1 个 false join 来自边界内未解释的多行子表头，已被 `conflict_report.csv` 和独立分组文件保留为可疑数据。

## 2. 原始课程材料核对

### 2.1 题目来源

题库第 4 页和第 14 页将 C1 定义为可审计的跨页 PDF 表格重建，要求关注跨页拼接、表头/单位保留、页码和单元格证据，并以 false joins、unit errors 和 traceable cells 衡量。当前项目的输入、输出、baseline、改进模式和三项指标均与该描述一致。

### 2.2 小组报告要求

课程写作指南要求小组报告最多 8 页（不含参考文献），包括真实问题、至少 3 个相关专利、技术问题、带标签流程图、coding agent 实现、baseline 对照、失败与代价、至少 3 个真实 agent errors，以及总结和限制。当前代码已经提供了可复现实验和失败案例，但以下内容需要由小组补齐，不能由程序自动代替：

- 小组成员、学号和贡献证据；
- 3 个专利的独立权利要求/机制阅读及 APA 7 引用；
- 3 个真实 agent errors 的对话证据、检测方法、修正和复核；
- 15 分钟演示和流程图。

### 2.3 个人报告要求

课程模板要求个人报告最多 10 页（不含参考文献），用学术英语，围绕个人问题、继承的小组代码、个人新增实验、结果解释、限制和 AI assistance disclosure 展开。当前个人扩展是路线 A 鲁棒性评测套件，已经有独立的生成、真值、批量运行、指标和失败案例代码。

## 3. 代码符合性矩阵

| 要求 | 实现位置 | 状态 |
|---|---|---|
| 单页表格提取 | `pdf_extractor.py` | 已实现，保留 page/table/row/cell 坐标 |
| baseline 简单拼接 | `table_merger.py` | 已实现 |
| 表头相似度与单位检查 | `table_merger.py` | 已实现，支持大小写、空格、换行和常见缩写归一化 |
| 冲突不强行合并 | `table_merger.py`、`audit_trail.py` | 已实现，独立组 + 冲突报告 |
| 单元格审计日志 | `audit_trail.py` | 已实现，CSV 记录页码、原始行号和坐标 |
| CLI 参数 | `main.py` | 已实现，支持 `--baseline` |
| 无表格/文件不存在/Java 缺失提示 | `main.py`、`pdf_extractor.py` | 已实现 |
| 3 类自动测试数据 | `test/generate_test_pdfs.py` | 已实现，每类 5 份、每份 3 页 |
| 真值和标注 | `test/generate_test_pdfs.py` | 已实现 CSV + JSON |
| 批量 baseline/improved 评测 | `test/evaluate.py` | 已实现 |
| 失败案例明细 | `test/evaluate.py` | 已实现，包含错误类型、PDF 和页码 |
| VS Code 可运行配置 | `.vscode/` | 已提供 tasks 和 launch 配置 |

## 4. 已发现并修正的问题

1. 初版统一使用 stream 提取时，带换行的表头被 tabula 拆成多行，类别 2 的改进模式错误地报告冲突。修正为优先 lattice、无结果再回退 stream 后，类别 2 的改进模式恢复为 0 false joins。
2. 评测脚本重复运行时，旧的 `reconstructed_table_group_N.csv` 可能残留并污染指标。现在每个样本运行前只清理自身输出文件，不影响输入数据。
3. 课程原始要求强调多行列头和单位位置变化，测试生成器已在类别 3 第 3 页显式加入第二行子表头/单位行，并把该边界行为保留在失败案例中。

## 5. VS Code 运行环境

项目本地 `.venv` 已安装 `requirements.txt` 中的依赖，并用它完成了编译、PDF 生成和完整评测。项目本地 `.runtime/temurin17-jre` 也已提供 JRE 17，使 tabula-py 可以实际启动 tabula-java；若提交压缩包过大，可不提交 `.venv` 和 `.runtime`，由接收者按 README 安装。

在 VS Code 中打开项目根目录，选择 `.venv\Scripts\python.exe`，然后执行：

```powershell
$env:JAVA_HOME = "$PWD\.runtime\temurin17-jre"
$env:Path = "$env:JAVA_HOME\bin;$env:Path"
python main.py input.pdf output
python test\generate_test_pdfs.py --output-dir test\data
python test\evaluate.py --data-dir test\data --output-dir test\results
```

也可以使用 `.vscode/tasks.json` 中的任务。实际结果位于 `test/results/summary_results.csv`，失败案例位于 `test/results/failure_cases.csv`。

## 6. 提交前清单

- [ ] 替换个人报告中的姓名、学号、Section、Group 和项目链接；
- [ ] 将个人报告文件名改为 `YourName_StudentID_TopicName.docx`；
- [ ] 小组报告补齐 3 个专利和 3 个真实 agent error 证据；
- [ ] 将最终代码、README、`.vscode` 配置和评测脚本一起压缩或提交私有仓库；
- [ ] 若不提交本地 JRE，确保 README 中的 Java 安装说明保留；
- [ ] 在最终环境重新运行完整评测，并把新的 `summary_results.csv` 作为报告证据。
