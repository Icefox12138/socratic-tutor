# 仓库拓扑：一个 monorepo，还是每个包一个仓库？

| 项 | 值 |
|---|---|
| 日期 | **2026-11-04** |
| 现状 | 单仓库 monorepo（392 文件 / 5.11 MB），四个产物分属四个目录 |
| 结论 | **先 monorepo 发布**；`classics-index` 若独立生长，再用 `git subtree split` 拆出去 |

---

## 0. 包与仓库是什么关系：一对一还是一对多？

**先给结论：注册中心和 git 之间没有任何强绑定。** PyPI / npm 只认「包名 + 版本 + 产物」，不知道你的代码住在哪个仓库。所以这是**约定**，不是机制：

| 关系 | 形态 | 谁在用 | 我们 |
|---|---|---|---|
| **N:1** | 一个仓库发多个包 | monorepo（Rust 的 workspace、pnpm/uv workspace 都是这个模式） | ✅ 现在：1 仓 → 3 包 |
| **1:1** | 一个仓库发一个包 | 多数中小型库 | 拆分后才成立 |
| **1:N** | 一个仓库发多个**渠道**（PyPI + Docker + conda） | 服务型项目 | sidecar 若发镜像会变成这样 |
| **N:N** | 一个包由多仓库构建 | 聚合式发行（Debian、Nix） | ❌ 不适用 |

### 我们的实际映射

```
socratic-tutor（git）
├── packages/classics-index  → PyPI  classics-index@0.1.0
├── packages/socratic-mcp    → PyPI  socratic-mcp@0.1.0
├── plugin-socratic          → npm   dsh-socratic@0.2.0
└── sidecar/                 → （只发源码，不发包）
```

**3 个包 : 1 个仓库。** 版本互相独立（0.1.0 / 0.1.0 / 0.2.0），这也是 monorepo 的常规做法——**同仓不等于同版本**。

### 关系记在哪

注册中心不存这个关系，是包**自己声明**的：

| 生态 | 字段 | 作用 |
|---|---|---|
| npm | `repository.url` + `repository.directory` | 包页显示「来源仓库 + 子目录」 |
| PyPI | `[project.urls]`（Homepage / Repository / Issues） | 侧栏出现对应链接 |
| 两者 | `description` 里写清定位 | 搜索命中时的第一印象 |

**唯一的"强制"来自常识**：如果包页链接到仓库根目录而用户在那个目录找不到这个包，这个链接就是负资产。monorepo 必须用 `directory` / 子目录 URL 补上这一层。

### 什么时候该从 N:1 变成 1:1

| 信号 | 判断 |
|---|---|
| 包有了本仓库之外的使用者 | 拆 |
| 发布节奏与主仓不同（比如库每月发、应用每月不发） | 拆 |
| CI 因为跑全仓测试而变慢 | 拆（或做路径过滤） |
| 契约变更需要同时改三个包 | **不拆** —— 这正是 monorepo 的价值 |
| 文档是三个包共用的决策记录 | **不拆** |

### 常见误解

- ❌ 「一个仓库只能对应一个 PyPI 包」——不对，setuptools/pnpm 都支持一个仓库出多个包；
- ❌ 「包名必须等于仓库名」——不对，`dsh-socratic` 住在 `socratic-tutor` 里完全正常；
- ❌ 「同仓就必须同版本」——不对，每个包各自 version，各自 tag（`classics-index-v0.1.0`）；
- ✅ 「1:1 更容易被搜索到」——这部分成立，这也是拆分的唯一强动机。

## 1. 三个方案

| | A. Monorepo（现在） | B. 每包一仓 | C. 混合 |
|---|---|---|---|
| 仓库数 | 1 | 4（+ docs 仓？） | 1 主仓 + 1~2 独立库 |
| 版本发布 | 各包独立版本，互不影响 | 同左 | 同左 |
| 契约改动 | **一次 PR 改完插件+sidecar+文档** | 跨仓三个 PR，容易漂 | 同 A，除拆出去的包 |
| CI | 一份 | 四份，其中三份几乎相同 | 两份 |
| 文档 | 与代码同仓，不会失联 | 必须另立仓库，或散落 | 主仓保留 |
| 发现性 | 中：包页链接到子目录 | **高**：包页链接到独立仓库 | 中高 |
| 新人上手 | 克隆即得全部上下文 | 要克隆四个 | 两个 |
| 历史 | 一条线性历史 | 拆分时用 subtree 保留 | 同 B |

## 2. 为什么先选 monorepo

1. **契约是耦合点**：`docs/SIDECAR-CONTRACT.md` 同时约束插件、sidecar、MCP 包装。拆仓后，一次契约变更要开三个 PR，且无法原子回滚。
2. **docs 是这个项目的记忆**：大量文档是 AI 会话交接记录，它们同时描述插件、sidecar 与评测。拆开就没有归处。
3. **规模不构成问题**：5.11 MB、392 文件、跑一次测试两秒。
4. **发布本来就已经分离**：包是独立版本、独立产物，monorepo 只影响"代码住哪"，不影响"包怎么发"。

## 3. 但要解决 monorepo 的两个硬伤

### 硬伤一：包页链接指向整个仓库，用户找不到自己的目录

在**下一次发版**时补上元数据（现在改不会被已发布版本吸收）：

```toml
# packages/classics-index/pyproject.toml
[project.urls]
Homepage = "https://github.com/OWNER/socratic-tutor/tree/main/packages/classics-index"
Repository = "https://github.com/OWNER/socratic-tutor"
Issues = "https://github.com/OWNER/socratic-tutor/issues"
```

```json
// plugin-socratic/package.json
"repository": {
  "type": "git",
  "url": "git+https://github.com/OWNER/socratic-tutor.git",
  "directory": "plugin-socratic"
}
```

npm 的 `repository.directory` 是专门为 monorepo 设计的字段，包页会显示"包在仓库的哪个子目录"。

### 硬伤二：clone 下来 5 MB，其中一半是 eval

如果将来 eval 变大，可先拆成独立仓库（`socratic-tutor-eval`），因为它只读、不被任何包依赖。

## 4. 真想每包一仓：怎么拆而不丢历史

假设主仓已有提交历史，拆 `classics-index`：

```bash
# 1) 把子目录的历史抽成一条独立分支（保留原作者与提交信息）
git subtree split -P packages/classics-index -b split/classics-index

# 2) 建空仓库并推上去
git init ../classics-index && cd ../classics-index
git pull ../socratic-tutor split/classics-index
git remote add origin git@github.com:OWNER/classics-index.git
git push -u origin main
```

之后主仓里删掉该目录，并在 `pyproject.toml` 里把包指向新仓库。

**注意**：`subtree split` 只能从**已有提交**里抽；现在主仓还没有任何 commit，先提交再拆才不丢东西。

## 5. 若走多仓，四个仓库的边界与顺序

| 仓库 | 内容 | 依赖 |
|---|---|---|
| `classics-index` | 卷/篇/回 逻辑 + CLI | 无 |
| `socratic-mcp` | MCP 包装 | 契约（HTTP） |
| `dsh-socratic` | DSH 插件 | 契约（HTTP） |
| `socratic-tutor` | sidecar + docs + eval + samples | `classics-index` |

依赖只能是单向的：契约文档放在主仓，其他仓库的 CI 都跑 `scripts/contract_check.py` 作为门禁——否则版本一多必然漂移。

## 6. 决策

- **现在**：单仓发布（本文件 §3 的两处元数据在下一次发版前补上）。
- **触发拆分**：`classics-index` 有了本仓库之外的使用者、或 eval 体积超过 50 MB。
- **永不拆分**：侧车、插件、契约文档——它们改动是同步的。
