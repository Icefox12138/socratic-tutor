# P2-5 对话评估

- `run_p2_5.py`：跑 100 段 API 级对话（需 sidecar 在 8765）。
- `run_p2_5.py --rewrite`：对导师输出先做单问重写，再继续对话；结果写 `results-rewritten.json`。
- `traces/*.json`、`traces-rewrite/*.json`：每段对话的导师回合、状态、判定、掌握度。
- `results.json`、`results-rewritten.json`：汇总指标与 Wilson 95% CI。
- `rescore.py` / `rescore_rewritten.py`：修正泄漏检测后重算。
- `human-rubric.csv`：20 个样本的人工评分表（5 维 1–5）。

运行：

```powershell
cd D:\Guo-Code\socratic-tutor
python -u eval/p2/dialogues/run_p2_5.py
python -u eval/p2/dialogues/rescore.py
```

注意：导师是 API 级 harness，不是 DSH 插件；学生回答是脚本模板。
