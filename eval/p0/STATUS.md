# P0 执行状态

| 日 | 状态 | 产物 |
|---|---|---|
| D0 preflight | **DONE（PASS）** | `preflight.md`、`catalog/preflight.json`、`catalog/hash-manifest.jsonl` |
| D1–D2 capability-probe | **DONE（部分验证）** | `capability/api-matrix.md`、`capability/probe-log.jsonl` |
| D3 catalog + 20 本 manifest | **DONE** | `catalog/sample-manifest.json`、`catalog/sample-manifest.md`、`catalog/catalog.jsonl` |
| D4 检索层对照 | **DONE（PASS，A 分支）** | `retrieval/retrieval-compare.md`、`retrieval/selfbuild-eval.json`、`docs/decisions/ADR-012-retrieval-selection.md` |
| D5–D7 分支 A（理工） | **DONE（降级通过）** | `bench/A/A-report.json`、`A-formula.md`、`A-math.json`、`pages/*` |
| D8–D10 分支 B（现代汉语） | **DONE（FAIL：CER）** | `bench/B/B-report.json`、`B-ocr.md`、`B1-300dpi.json`、`B2/B3_ocr.txt` |
| D11–D13 分支 C（繁体竖排） | **DONE（FAIL：注文/OCR）** | `bench/C/C-report.json`、`C-layout.md`、`pages/*_annot.png`、`C-upscale-ocr.json` |
| D14–D15 分支 D + canary | **DONE（条件通过）** | `bench/D/D-report.json`、`D-classics.md`、`identity/loeb-teubner.csv`、`D-canary.json` |
| D16 go/no-go | **DONE（收窄 GO）** | `go-no-go.md`、`ADR-012` 已转 Accepted |

**D0 结论**：PASS。馆藏 801 / 27.46 GB；哈希 801 文件 / 800 唯一（1 组重复）；D: 468.7 GB 可用；工具链就绪；20 本样本全部命中。

**D1–D2 结论**：部分通过。`ctx.tools.register`（原始 JSON Schema）、`tools/pre-execute`、`tools/post-execute`（签名 `(exec, result)`，返回 `{content}`）已实测可用；`systemPrompt.context`、`jobs.start`、`storage` 存在但未验证回放/生命周期；`ConversationNodeDefinition`、token 文件、出站钩子未验证。全部有 fallback，不阻塞 D3。

**D3 结论**：PASS。`catalog.jsonl` 905 条（904 唯一：801 馆藏 + 100 Steadman + 2 Loeb + 2 Teubner）；20 本样本全部命中，`book_id` 均在 catalog，窗口/金标均在页范围内；K5–K8 已按实际正文起点对齐（p82 / p249 / p48 / p62）。

**D4 结论**：PASS，走 **A 分支（自建 `socratic-search`）**。5 本文字层书 / 109,229 chunks；recall@10 **0.95**；p95 **38.7 ms**；canary 在 student/tutor 下均 **0 命中**。`dsh-knowledge` 未安装（AGPL、无 chunk 可见性、22 MB、构建成本），P4 再评估。ADR-012 已落盘（Provisional）。

**D5–D7 结论**：**降级通过**。A1 文字层 964 字/页但公式结构丢失（代理可编译 55.4%）；A2/A4 OCR 公式不可用（下标/分式错位）；A3 代码正文可读但标点有误；SymPy 10/10。按 fallback：公式只做页图 + VLM，计算只认键入表达式或高置信 LaTeX。

**D8–D10 结论**：**FAIL（CER）**。B1 文字层 1,508 字/页、224 行脚注样式但未分离；合成 OCR CER 12.1%（200dpi）/10.5%（300dpi），远高于 2%；B2/B3 OCR 523/665 字/页、脚注混排。处置：OCR 降级为检索/提示，引用回页图；P1 换 PP-StructureV3/VLM；阈值改分级（检索级 ≤10%、引用级页图核验）。

**D11–D13 结论**：**FAIL**。C1 史记列切分 18 列、右起顺序正确（人工核对标注图），但正文/三家注同列未分离；C2 首块 525px 把注疏合并。PP-OCR 旋转/放大后竖排 OCR 仍不可读（0–46 字/列）。处置：竖排只做页图引用 + 卷次索引，P1 用 VLM/古籍专用 OCR 重做。

**D14–D15 结论**：**条件通过**。Steadman 三流机械可用，但 K2/K4 抽样页无原文（注释/词表卷），入库须逐卷查 `text_share`；Loeb/Teubner 身份 4/4；CER 复现：拉丁行级 0.64%（96.4%）、希腊句级 6.07%（88.4%）、Conte 1.9%（100%）；canary：student/tutor 0、answer_key 1、无过滤 1。LLM 30 轮延后 P1-0。

**关键约束**：插件必须声明 `inject`；开发用 `link:` 而非 `file:`；profile `package.json` 必须无 BOM；headless 需 `@deepseek-ai/dsh-headless` + `DEEPSEEK_API_KEY`。
