# Rubrica

[![tests](https://github.com/JCPetrelli/rubrica/actions/workflows/test.yml/badge.svg)](https://github.com/JCPetrelli/rubrica/actions/workflows/test.yml) [![license: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

A [Claude Code](https://claude.com/claude-code) skill that cleans up and completes the macOS Contacts address book (*rubrica* is Italian for address book). You talk, Claude runs the tools, and nothing changes until you approve a plan.

It was built while cleaning a real address book: 2,037 cards went down to 1,440. Along the way, about 250 people from 20 years of e-mail and WhatsApp were added, and 90 more addresses were attached to existing cards.

## What it does

The cleanup is a ladder. Each rung needs more judgement than the one before it:

| Rung | Finds | Example |
|---|---|---|
| Exact copies | cards identical in every field | the same card imported three times |
| Same name | equal display names | two "Maria Rossi" cards with different numbers |
| Linked | different names that share a phone or e-mail | "Rob landi" and "Roberto Landi" |
| Name only | the same person with nothing in common but the name | "Dad Tim" and "Dad Work"; "Gabri" and "Gabriella"; `anna_bell@…` and "Anna Bell" |
| Inside a card | one value stored twice | `0176 1234…` next to `+49 176 1234…` |
| Apple Mail | people you e-mail who are missing | ranked: two-way, wrote once, wrote to you, often on Cc |
| WhatsApp Desktop | numbers you chat with that are not saved | names from your phone's address book |
| Title Case | shouting and lower-case names, last so new cards are included | "GIULIA MORETTI" → "Giulia Moretti", "(VE)" and "SMS" stay |

What makes it safe:
- **A plan before every change.** Each scan writes a JSON plan. Claude shows it, you say yes, then `apply --yes` runs it. Without `--yes`, `apply` is a dry run.
- **Undo files.** Before its first change to a card, `apply` saves the card to `plan.undo.vcf`. A full backup (`backup`) comes first.
- **No guessing on doubtful pairs.** A shared landline does not make two people one ("Nora (vet)" and "Ivo (judo)"). A corrupted card that holds a dozen strangers' e-mails is reported as a chain, not merged. A one-word name ("Nina") with nothing shared stays apart. Pairs found by name alone are always questions for you.
- **Old names are kept.** A merged card keeps the other names in its note (`Also saved as: Tom cell`), so search still finds them.
- **Local only.** Python standard library and `osascript`. Nothing goes over the network.

## Install

Requirements: macOS, [Claude Code](https://claude.com/claude-code), `python3` 3.10 or later (standard library only).

As a plugin (recommended):

```
/plugin marketplace add JCPetrelli/rubrica
/plugin install rubrica@rubrica
```

Or from a clone:

```bash
git clone https://github.com/JCPetrelli/rubrica.git && cd rubrica
just install          # or: ln -sfn "$(pwd)/skills/rubrica" ~/.claude/skills/rubrica
```

Then ask Claude Code: *"clean up my contacts"*, *"merge my duplicate contacts"* or *"who do I e-mail who isn't in my contacts?"*.

Permissions macOS asks for:
- **Automation → Contacts** for your terminal, the first time a command reads or writes Contacts.
- **Full Disk Access** for your terminal, only for the Mail rung: it reads Mail's index at `~/Library/Mail/V*/MailData/Envelope Index`.

## Use it without Claude

Every step is a plain command. Run them in a folder of your choice: the files hold personal data.

```bash
export PYTHONPATH=/path/to/rubrica
python3 -m rubrica backup                          # all cards -> rubrica-backups/*.vcf
python3 -m rubrica export                          # -> contacts.json (read-only)
python3 -m rubrica inventory
python3 -m rubrica scan linked --plan p-linked.json
python3 -m rubrica apply p-linked.json             # dry run: prints what would change
python3 -m rubrica apply p-linked.json --yes       # writes p-linked.undo.vcf and p-linked.log.json
python3 -m rubrica pick p-names.json --merge "Dad" "Dad Tim" "Dad Work"
python3 -m rubrica mail                            # suggests which addresses are yours
python3 -m rubrica mail --me you@example.org old@isp.example --years 10
python3 -m rubrica add-plan mail-candidates.json --plan p-add.json   # after you edited the list
python3 -m rubrica whatsapp --out wa.json
```

Re-export after every applied plan: merges delete cards, and a plan must point at cards that still exist.

## How a merge works

The surviving card is the one with the most complete real name ("Marco Neri" beats "Marco (cello)" and `marco@…`). Every phone, e-mail, URL, address, birthday and photo of the other cards is copied onto it, skipping values it already has in another format. A different company or a note goes into the note. Then the other cards are deleted.

## Undo

- One plan: double-click `plan.undo.vcf` (or File → Import in Contacts) to restore the cards as they were before that plan. Cards that a merge kept will appear twice: delete the merged version.
- Everything: import the `.vcf` from `backup`, after deleting the current cards, or restore a Contacts archive (File → Export → Contacts Archive) you made before starting.

## Limits

- macOS only. The scans and tests run anywhere, but reading and writing Contacts needs `osascript`.
- Contacts scripting does not say which account (iCloud, Google, Exchange) a card lives in. Merging across accounts works, but a server-managed account may bring deleted cards back.
- WhatsApp support reads the macOS desktop app's databases (`group.net.whatsapp.WhatsApp.shared`). WhatsApp changes their format now and then.

## License

MIT. See [LICENSE](LICENSE).
