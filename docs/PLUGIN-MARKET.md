# 插件市场上架

| 项 | 值 |
|---|---|
| 日期 | **2026-11-04** |
| 格式 | `@deepseek-ai/dsh-plugin-market-index` format 1 |
| 索引地址 | `https://raw.githubusercontent.com/Icefox12138/socratic-tutor/main/market/index.json` |
| 校验 | 用官方 `parseMarketIndex` 验证通过 |

---

## 1. DSH 市场是什么

不是集中式商店，而是**用户自己配置的索引 URL 列表**：

- DSH 默认不配置任何索引（`indexes` 为空，Host 不发请求）；
- 用户在 **Settings → Plugins** 里添加一个 JSON 索引地址；
- Discover 页读取它，展示插件、检查与当前 DSH 版本的兼容性，并给出精确安装参数。

所以"上架"= **生成一个合法索引 JSON 并让它可被 HTTPS 访问**，没有审批流程。

## 2. 索引结构

```json
{
  "format": 1,
  "title": "Socratic Tutor",
  "description": { "en": "...", "zh": "..." },
  "plugins": [{
    "name": "dsh-socratic",
    "title": "Socratic Tutor",
    "description": { "en": "...", "zh": "..." },
    "homepage": "https://github.com/Icefox12138/socratic-tutor/tree/main/plugin-socratic",
    "author": "Icefox12138",
    "versions": [{
      "version": "0.2.0",
      "source": { "type": "npm" },
      "engines": { "dsh": ">=0.2.1-rc.2 <0.3.0-0" },
      "publishTimestamp": 1793760887
    }]
  }]
}
```

各字段的硬性要求（照官方校验器）：

| 字段 | 规则 |
|---|---|
| `name` | 合法 npm 包名，**必须与 registry 上的包名一致**，安装时用 `name@version` |
| `version` | 严格 SemVer；每个插件内不得重复 |
| `publishTimestamp` | Unix 秒，整数，`[0, 10^11)` |
| `engines.dsh` | SemVer 范围，不能是 `workspace:` |
| `icon` | 相对路径（按索引 URL 解析）或 base64 data URL，解码后 ≤ 32 KiB |
| `source` | `{"type":"npm"}` 或 `{"type":"git","url","commit"(40 位小写 sha),"path"?}` |

## 3. 本地校验

```bash
# 用 DSH 自带的校验器（不需要安装任何东西）
ELECTRON_RUN_AS_NODE=1 "D:/Program Files/dsh/DeepSeek Harness.exe" tmp/validate-market.mjs
```

`tmp/validate-market.mjs` 的核心三行：

```js
import { parseMarketIndex } from "file:///D:/Program Files/dsh/resources/app.asar/dsh/node_modules/@deepseek-ai/dsh-plugin-market-index/lib/index.js";
const ok = parseMarketIndex(json, "https://raw.githubusercontent.com/.../market/index.json");
```

校验器会报出 JSON 路径，例如第一次跑就抓到我们漏了 `publishTimestamp`：

```
$.plugins[0].versions[0].publishTimestamp must be an integer number of Unix seconds in [0, 10^11)
```

## 4. 发布一个版本后要做的两件事

1. 把新版本加进 `versions` 数组（旧版本保留，Discover 会按 SemVer 排序并挑兼容的那个）；
2. `publishTimestamp` 用 npm registry 上该版本的真实时间：

```bash
curl -s https://registry.npmjs.org/dsh-socratic | jq '.time["0.2.1"]'
```

## 5. 兼容性是怎么判的

Discover 用 `engines.dsh` 与当前 DSH 版本做 SemVer 匹配，并显示"不兼容"；安装参数由 `marketInstallTarget` 生成：npm 源就是 `dsh-socratic@0.2.0`，git 源是 `git+https://...#<40位sha>`（锁定提交，不用 tag）。

**因此 `engines.dsh` 必须与 `package.json` 里的范围保持一致**，否则市场显示可装、实际装不上。
