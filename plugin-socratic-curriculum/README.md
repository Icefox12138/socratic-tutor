# dsh-socratic-curriculum

The **course layer** of the Socratic tutor. The engine (`socratic-sidecar`) ships
the curriculum *contract*, not the courses: it serves whatever lesson packs live
in `SOCRATIC_CURRICULUM` (see [docs/CURRICULUM-SCHEMA.md](../docs/CURRICULUM-SCHEMA.md)).
This bundle is the thin host adapter that lets an agent see and follow them.

## What it adds

| Piece | What it does |
|---|---|
| `curriculum_list` tool | The lesson catalogue (`line / unit / lesson` order). |
| `curriculum_lesson` tool | One lesson: passage page range, vocabulary (resolved against `lexicon.db`), grammar refs, background, worked example, questions, review-card seeds. |
| `curriculum_start` tool | Binds a lesson to this session: `POST /v1/state/init` with `lesson=<id>, learn=true` (preview phase) or `review=true` (review-first opening). |
| `agent/pre-step` hook | At the **first step of each turn**, injects the active lesson block — so the model teaches the lesson instead of the whole library. |

"Active lesson" means the bundle config `lesson`, or whatever the sidecar state
already carries (`state.lesson`, set by `curriculum_start`). With neither, the
hook injects nothing and this bundle stays out of the way.

## Install combinations

| Installed | Behaviour |
|---|---|
| tools only (`dsh-socratic`) | Free-form Q&A over your library. |
| tools + persona | Teaching discipline (charter, citations, hint ladder) without courses. |
| **tools + persona + curriculum** | **Course mode**: pick a lesson, preview it, practise it, review it. |

Like the persona bundle, this one is intentionally separate: installing it is
the switch.

## Configuration

| Key | Default | Meaning |
|---|---|---|
| `baseUrl` | `SOCRATIC_SIDECAR_URL` or `http://127.0.0.1:8765` | Sidecar address. |
| `token` | `SOCRATIC_TOKEN` | Sent as `X-Sidecar-Token` when set. |
| `lesson` | *(empty)* | Fixed lesson for the profile; overrides the session state. |
| `lang` | `zh` | Passed to `/v1/state/init` by `curriculum_start`. |

`SOCRATIC_DEBUG=1` writes `curriculum.log` next to the bundle.

## Requirements

- A running sidecar with the curriculum endpoints (`socratic-sidecar` ≥ 0.3.0,
  i.e. `uvx --from socratic-sidecar socratic-sidecar --data <data> --port 8765`).
- Lesson packs as JSON files in the sidecar's `SOCRATIC_CURRICULUM` directory;
  validate them before publishing a course:

  ```bash
  python scripts/curriculum_check.py --dir <lesson-dir>
  ```

- Without that directory the tools answer `lessons: []` and the hook is inert —
  a missing curriculum is a normal state, not an error.

## Limitations

- Host-only for now (no client panel); the companion card UI is a later step.
- One lesson per session; switching courses means calling `curriculum_start`
  again.
- This bundle never writes lesson files — authoring stays outside the harness.

## 中文摘要

课程层插件：引擎只发布课程**契约**与 `/v1/curriculum` 端点，本插件让 Agent
能看到并跟随课程包。三个工具（列目录 / 读一课 / 绑定一课到会话状态机）＋一个
钩子（每轮第一步注入"当前课"块）。装它 = 课程模式；不装 = 自由问答。课程包由第三方
按 `docs/CURRICULUM-SCHEMA.md` 编写，发布前用 `curriculum_check.py` 校验。
