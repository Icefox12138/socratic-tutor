# Contributing

Thanks for looking. This is a single-machine research project, so the most useful
contributions are narrow and testable.

## Before you start

- **Never include book pages.** No scanned images, no OCR dumps of copyrighted
  editions, no embeddings derived from them. This is the one rule that will get a
  pull request closed without discussion.
- Code is MIT, but `sidecar/` is AGPL-3.0 (it links PyMuPDF). Contributions to
  `sidecar/` are accepted under AGPL-3.0-or-later.

## What's most useful

| Area | Why it helps |
|---|---|
| Retrieval quality | Two gates are unmet: monolingual recall 0.82 (target 0.85), cross-lingual 0.688 (target 0.70) |
| Vertical / classical OCR | Running-header detection is the weakest link for 竖排 books |
| Another sidecar implementation | The HTTP contract is documented and probe-able; a second implementation would keep it honest |
| Cypriot edge cases in `classics-index` | It is pure logic with a synthetic fixture — easy to test |

## Workflow

```bash
git clone https://github.com/Icefox12138/socratic-tutor.git
cd socratic-tutor

# the four suites (no library needed)
(cd sidecar && python -m unittest discover -s tests -p "test_*.py")
(cd packages/classics-index && python -m unittest discover -s tests -p "test_*.py" -t .)
(cd packages/socratic-mcp && python -m unittest discover -s tests -p "test_*.py" -t .)
(cd plugin-socratic && node --test test/plugin.test.mjs)

# the gates CI runs
python scripts/publish_lint.py
python scripts/publish_lint.py --scope source
```

Open an issue before a large change; small fixes can go straight to a pull request.

## Commit messages

`<type>: <what changed>` — `feat`, `fix`, `docs`, `test`, `chore`, `release`.
Say *why* in the body when the reason is not obvious from the diff.
