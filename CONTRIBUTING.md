# Contributing

Issues and pull requests are welcome.

## Setup

```bash
git clone https://github.com/JCPetrelli/rubrica.git && cd rubrica
just install    # symlink the skill into ~/.claude/skills so Claude Code uses your checkout
just test
```

Python uses only the standard library. The tests run anywhere; the commands that talk to Contacts.app, Mail or WhatsApp need macOS.

## Before opening a pull request

- `just test` passes.
- Test data is invented. Never paste a real export, plan, log or vCard into an issue, a test or a commit.
- If you change a matching rule (`normalize.py`, `dedupe.py`), add a test that shows the case it fixes and a case it must not catch.
- If you change `apply.js`, try it on a throwaway card first: `create` → `merge` → `delete`, and check that the `.undo.vcf` re-imports.
