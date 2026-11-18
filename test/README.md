# 文件名：test/README.md

# 个人自动化评测套件

该目录对应路线 A：鲁棒性测试。它自动生成三类原生文本型 PDF，每类 5 份，每份 3 页，并分别用基线模式和改进模式运行项目原型。

## 测试类别

- `category1_standard`：表头统一、列数固定的标准布局。
- `category2_header_variation`：大小写、空格、换行、缩写和单位书写格式发生变化，但列含义不变。
- `category3_unfamiliar_layout`：前两页为主表，第三页列数、列含义和单位位置发生变化，用于测试不应强行拼接的场景。

每份样本包含：`sample_XX.pdf`、`sample_XX_truth.csv` 和 `sample_XX_labels.json`。

## 指标定义

- **False joins**：输出记录无法在真值中找到，或记录所属的输出表格组与真值组不一致的行数。
- **Unit errors**：输出表头中的测量单位与该记录真值单位不一致的测量单元格数。
- **Traceability rate**：输出数据单元格中，具有有效 `__source_page` 和 `__source_row` 的单元格占比。

## 运行

在项目根目录执行：

```bash
python test/generate_test_pdfs.py --output-dir test/data
python test/evaluate.py --data-dir test/data --output-dir test/results
```

结果文件：

- `test/results/summary_results.csv`：按类别和模式汇总平均指标。
- `test/results/per_sample_results.csv`：每份 PDF 的指标。
- `test/results/failure_cases.csv`：错误类型、PDF、页码和错误说明。
- `test/results/{baseline,improved}/...`：每个样本的原型输出，可直接检查审计日志和冲突报告。

若只想快速试跑，可使用 `--samples-per-category 1` 生成每类 1 份样本。

