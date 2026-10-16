---
name: rubricai
description: Use when the user wants to clean up, deduplicate, merge or complete their Apple / macOS Contacts address book — duplicate cards, the same person saved twice under nicknames ("Tom cell" and "Tommaso Ferri"), cards named only by an e-mail address, messy capitalisation, or people they e-mail (Apple Mail) or chat with (WhatsApp Desktop) who are missing from Contacts. Triggers on "clean up my contacts", "merge duplicate contacts", "dedupe Contacts.app", "who do I email that isn't in my contacts", "add my WhatsApp contacts".
---

# Rubricai

Clean up a macOS address book as a ladder of reviewed plans. Each rung needs more judgement than the one before it. Nothing changes without a plan the user approved, and every applied plan leaves a vCard undo file. "Just do it, I trust you" does not remove the approvals: merges cannot be undone in place.

## Setup

The engine is two directories above this skill's base directory. Shell variables do not survive between tool calls, so start every command with the full prefix:

```bash
PYTHONPATH="<skill base directory>/../.." python3 -m rubricai --help
```

Below, `rb` stands for that prefix. Ask the user for a working folder first: exports, plans and backups hold personal data. Needs macOS and `python3` 3.10+, no packages. The first run triggers the Automation prompt for Contacts; `rb mail` needs Full Disk Access for the terminal.

If Contacts shows more than one account (iCloud plus Exchange or Google), ask before merging: scripting cannot see which account a card lives in, and a server-managed account may restore cards you delete.

## The ladder

Start with `rb backup` (all cards to one `.vcf`). Then `rb export` → `contacts.json`, and `rb inventory`.

**Re-export after every applied plan**, before the next scan, `pick`, `mail` or `add-plan`. Merges delete card ids, and a plan built on a stale export points at cards that no longer exist.

| Rung | Command | What it finds | Who decides |
|---|---|---|---|
| 1 | `rb scan exact --plan p1.json` | Cards identical in every field | Show the count, apply on a yes |
| 2 | `rb scan same-name --plan p2.json` | Same display name | Merge list on a yes, after checking it for common full names (two "Marco Rossi" can be two people). `review`: one-word names with nothing shared |
| 3 | `rb scan linked --plan p3.json` | Different names sharing a phone or e-mail, names compatible ("Rob landi" ~ "Roberto Landi") | Merge list on a yes; every `review` pair and chain to the user |
| 4 | `rb scan name-only --plan p4.json` | No shared data: e-mail-named cards, descriptor variants ("Dad Tim" / "Dad Work"), nicknames ("Gabri" / "Gabriella"), accent variants | Only the user. Add each approved group with `rb pick p4.json --merge "Keeper" "Other"` |
| 5 | `rb scan in-card --plan p5.json` | A value stored twice on one card (keeps `+39 347…` over `347…`), repeated note lines | Show, apply on a yes |
| 6 | `rb mail …` | People the user e-mails who are missing | User approves the curated list |
| 7 | `rb whatsapp --out wa.json` | WhatsApp address-book entries and unsaved chat numbers | User picks |
| 8 | `rb scan title-case --plan p8.json` | Names in lower or upper case, including the cards just added | Show a sample, apply on a yes |

Apply any plan with `rb apply plan.json`, a dry run that prints the counts. `rb apply plan.json --offline contacts.json` applies it to the export instead, to preview the result (then export again before the real apply). Then run `rb apply plan.json --yes`. It writes `plan.undo.vcf` (each touched card, before its first change) and `plan.log.json`. `pick --merge` takes exact card names or card ids (from the plan file), keeper first.

## Rules for each rung

- **Show before you change.** Print the groups (`--limit`), say how many cards will disappear, wait for a yes. Lists longer than about 40 rows: show them in pages and collect approvals per page.
- **Review items are questions.** Present them as a short table: names, what links them, your guess. A shared landline links different people in one household. One number on "Nora (vet)" and "Ivo (judo)" means two people. A chain usually means one corrupted card holds strangers' e-mails: never merge a chain, pick the real pairs out of it.
- **The survivor** is the card with the most complete real name ("Marco Neri" over "Marco (cello)" or `marco@…`). The other names go into the note as `Also saved as: …`, so labels like "(neighbour)" survive. If the user names a different keeper, put that name first in `pick`.
- **Never invent a name.** An e-mail-named card stays as it is unless it matches a real card or the user names it.
- **Never infer family** from a shared surname.

## Mail (rung 6)

1. `rb mail` with no `--me` lists addresses that send and receive a lot. Ask which are the user's own (old ISP, university and work addresses count) and which are bots or aliases (`--ignore`). An own address left out turns into a fake "contact" and hides everyone written to from it.
2. `rb mail --me … --years 10 --out mail-candidates.json`. To go further back, run a second pass with `--since` / `--until`. Tiers: A two-way, B wrote once, C they wrote two or more times, D often on Cc.
3. Curate the JSON: keep people and the organisations the user deals with (adviser, school, landlord). Drop customer service, rows marked `automated`, one-off job or sales enquiries, and the user's aliases. Fix names; set `organization`, or `company: true` for a company card. `name_guessed: true` means the name came from `first.last@`: say so. A row with no name is skipped unless the user names it.
4. `rb add-plan mail-candidates.json --plan p6.json`. Rows matching exactly one card with a two-word name are added to that card; the rest become new cards. Show the counts, then apply.

## WhatsApp (rung 7)

`rb whatsapp --out wa.json` copies WhatsApp Desktop's databases to a temp folder and compares numbers. Address-book entries carry names from the user's phone. For chats, `push_name` is the name the person gave themselves. Single unanswered messages from unknown countries are usually spam. Write the user's picks as rows of `{name, phone}` and run `rb add-plan` on them.

## Undo

- Cards a plan deleted or changed: import `plan.undo.vcf` (double-click, or File → Import). After a merge this also brings back the old version of the surviving card, so delete the merged version first.
- Everything: the `rb backup` file, or a Contacts archive (File → Export → Contacts Archive).

## Common mistakes

| Mistake | Instead |
|---|---|
| Scanning or picking from an old export | `rb export` after every apply |
| Merging everything that shares a phone | Rung 3 already holds back names that do not fit; ask about them |
| Treating one-word names as one person | Two "Nina" cards with different numbers stay apart |
| `make new email at end of emails` in JXA | `apply.js` uses `C.Email({...})` + `push()`; `make` fails with -10002 |
| Adding every Mail address | Read the list; relays, bulk and automated senders are only pre-filtered |
| Title Case before adding people | Run it last, so new cards are covered |
| Skipping the backup | `rb backup` first, every session |

## Finish

Report each rung (cards before → after), where the backup and undo files are, and what is still open: deferred review items, e-mail-named cards without a match. Run a fresh `rb backup`.
