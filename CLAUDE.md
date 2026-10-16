# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A Claude Code skill plus its engine, meant for public release (MIT). The skill is `skills/rubrica/SKILL.md`. It is distributed as a plugin (`.claude-plugin/`) or by symlink with `just install`. The skill finds the engine two directories above its base directory, so never hardcode machine paths in it.

The engine is a stdlib-only Python package (`rubrica/`) plus three JXA scripts (`rubrica/jxa/`) that talk to Contacts.app through `osascript`:
- `export.js` and `backup.js` only read.
- `apply.js` is the only code that changes Contacts. It runs a reviewed plan and appends each card's vCard to an undo file before its first change.

Python never mutates anything: scans turn an exported `contacts.json` into a plan (`plan.py`), `cli.py apply` hands the plan to `apply.js`, and does so only with `--yes`.

## Commands

```bash
just test                                   # python3 -m pytest -q (stdlib only, no venv)
python3 -m pytest tests/test_dedupe.py -q   # one file
just run                                    # backup + export + inventory into ./work (read-only)
just scan linked                            # export + build work/plan-linked.json (read-only)
python3 -m rubrica --help
```

## Rules

- Tests use invented people only. Never commit an export, plan, candidates file, log or `.vcf`; `.gitignore` covers the default names and `./work`.
- In JXA, create elements with `C.Email({...})` and `push()`. `C.make()` fails with error -10002. Images cannot be read in bulk (-1741): read them one card at a time.
- Matching keys live in `normalize.py` (phone = last 9 digits, e-mail = lower case). `apply.js` repeats the phone and alias rules in JavaScript; change both together.
