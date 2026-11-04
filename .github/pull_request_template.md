## What this changes

## Why

## Checks

- [ ] `python -m unittest` passes in the directories I touched
- [ ] `node --test test/plugin.test.mjs` still passes (if `plugin-socratic/` changed)
- [ ] `python scripts/publish_lint.py` and `--scope source` are green
- [ ] No book pages, OCR dumps or derived embeddings are included
- [ ] If `docs/SIDECAR-CONTRACT.md` changed: the version note is updated and `scripts/contract_check.py` still passes

## Notes for the reviewer
