# packages/

可独立发布的代码。其余目录（`sidecar/`、`plugin-socratic/`、`eval/`）是**项目本体**，与个人书库、实验数据绑定，暂不作为包发布。

| 包 | 形态 | 状态 | 依赖 |
|---|---|---|---|
| [classics-index](classics-index/) | Python CLI / 库 | **可发布**（缺 license） | 纯标准库；OCR 为可选依赖 |
| [socratic-mcp](socratic-mcp/) | MCP server（Python） | **可发布**（缺 license） | 纯标准库；需要一个 sidecar |

## classics-index

```
pip install -e packages/classics-index
classics-index volumes --headers heads.jsonl --out toc.json
```

把"扫描本页眉 OCR → 卷/篇/回索引"这段逻辑从 sidecar 里抽出来，去掉了 SQLite、HTTP 和项目私有路径。测试 16 条，能直接跑真实数据（见 README 的验证表）。

## 为什么只有这一个

其余代码的复用屏障是**数据**而不是**代码**：

- `sidecar/`：检索/引用/页图都假设 `D:\Guo-Code\PDF` 这样的本地书库与 BGE 向量文件存在；
- `plugin-socratic/`：DSH 插件本身可打包，但工具全都调 sidecar 的私有 API，别人装上没有 sidecar 就只剩报错；
- `eval/`：一次性实验脚本（TEDS、token 对比、复盘评估），价值在方法，不在可安装性。

详见 `docs/OPEN-SOURCE.md` 的评估表。
