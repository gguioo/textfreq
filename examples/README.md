# 示例数据说明

`sample_txts/` 内是 6 个**虚构**的模拟文献摘要（内容为杜撰，仅演示工具用法），
文件名按 `主题_年份.txt` 命名，用于演示年度趋势识别。

试跑命令（在仓库根目录）：

```bash
pip install -e .
textfreq run examples/sample_txts -o examples/out
```
