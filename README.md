# Rubrica

[![tests](https://github.com/JCPetrelli/rubrica/actions/workflows/test.yml/badge.svg)](https://github.com/JCPetrelli/rubrica/actions/workflows/test.yml) [![license: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

A [Claude Code](https://claude.com/claude-code) skill that cleans up and completes the macOS Contacts address book (*rubrica* is Italian for address book). You talk, Claude runs the tools, and nothing changes until you approve a plan.

It was built while cleaning a real address book. 2,037 cards went down to 1,440. Along the way, about 250 people from 20 years of e-mail and WhatsApp were added, and 90 more addresses were attached to existing cards.

Every name, number and address in this README is invented. The outputs are real: they come from running the tool on the demo address book in [`examples/`](examples/).

- [What it does](#what-it-does)
- [A session with Claude](#a-session-with-claude)
- [The ladder, rung by rung](#the-ladder-rung-by-rung)
- [Finding the people who are missing](#finding-the-people-who-are-missing)
- [Safety](#safety)
- [Install](#install)
- [Use it without Claude](#use-it-without-claude)
- [Try it on the demo](#try-it-on-the-demo)
- [How matching works](#how-matching-works)
- [Undo](#undo)
- [Limits](#limits)

## What it does

| Rung | Finds | Example from the demo |
|---|---|---|
| 1. Exact copies | cards identical in every field | "Laura Bianchi" imported three times |
| 2. Same name | equal names with different details | two "Marco Neri" cards, one with the phone, one with the e-mail |
| 3. Linked | different names that share a phone or e-mail | "Rob landi" and "Roberto Landi" |
| 4. Name only | the same person with nothing but the name in common | "Dad Tim" and "Dad Dad Work"; "Gabri" and "Gabriella Gallo" |
| 5. Inside a card | one value stored twice on a card | `0176 55520202` next to `+49 176 55520202` |
| 6. Apple Mail | people you e-mail who are not in Contacts | Sabine Weber, 8 messages both ways |
| 7. WhatsApp Desktop | numbers you chat with that are not saved | "Yara (Swimming)" from your phone's address book |
| 8. Title Case | names in capitals or lower case | "GIULIA MORETTI" becomes "Giulia Moretti", "(VE)" stays |

## A session with Claude

You do not need to learn the commands. A session looks roughly like this (an illustration, shortened):

> You: clean up my contacts
>
> Claude: I backed up all 1,812 cards to `contacts-20261016.vcf` and exported them. 41 cards are exact copies of another card, in 38 sets. Shall I delete the copies? Each set keeps its most recently edited card.
>
> You: yes
>
> Claude: Done, 1,771 cards. Next, 64 groups of cards share a phone or e-mail and have compatible names, for example "Rob landi" and "Roberto Landi". Three pairs share a number but have unrelated names:
>
> | Cards | Shared | My guess |
> |---|---|---|
> | Nora (vet) / Ivo (judo) | landline +39 0423… | two people, one household |
> | Acme Tools / Omar Lanza / omar@example.org | omar@example.org | Acme's card holds other people's e-mails; Omar's two cards are one person |
>
> Merge the 64 groups, and Omar's two cards?
>
> You: yes, but keep Nora and Ivo apart

Claude asks before every change, shows what will disappear, and gives you the undo file afterwards.

## The ladder, rung by rung

The rungs go from no judgement needed (exact copies) to a lot (two cards that share only a name). Each rung writes a plan; nothing changes until it is applied. These are the real outputs on the 37-card demo.

### 1. Exact copies

```
$ rb scan exact --plan p1.json
2 exact copies to delete
```

"Laura Bianchi" was imported three times. Two copies go, one stays. A card that differs in any field, even only in the note, is not an exact copy and moves on to the next rungs.

### 2. Same name

```
$ rb scan same-name --plan p2.json
1 same-name groups to merge; 1 ambiguous (review)
  Marco Neri  <=  Marco Neri
  REVIEW Nina | Nina  (one-word name, nothing shared)
```

The two "Marco Neri" cards become one card with both the phone and the e-mail, and the note "Choir, tenor". The two "Nina" cards have different numbers and nothing else, so two people called Nina is the likelier story. Claude asks instead of merging.

### 3. Linked by a phone or e-mail

```
$ rb scan linked --plan p3.json
2 linked groups to merge; 3 pairs and 1 chains to review
  Roberto Landi  <=  Rob landi
  Tommaso Ferri  <=  Tom cell | Tom casa
  REVIEW Nora (vet) | Ivo (judo)  (share p:235550909, names differ)
  REVIEW Acme Tools | Omar Lanza  (share e:omar@example.org, names differ)
  REVIEW Acme Tools | Gloria Sala  (share e:gloria@example.org, names differ)
  REVIEW Omar Lanza | Acme Tools | omar@example.org  (chain: linked cards with unrelated names)
```

- "Tom cell" and "Tom casa" share numbers with "Tommaso Ferri", and "Tom" is a short form of "Tommaso". All three become one card.
- "Nora (vet)" and "Ivo (judo)" share a landline, but their names do not fit together. They stay apart unless you say otherwise.
- "Acme Tools" is a company card that somehow holds Omar's and Gloria's private e-mails. Following shared values blindly would glue Acme, Omar and Gloria into one person. Rubrica reports the chain instead. Here, you confirm that the card named `omar@example.org` is Omar:

```
$ rb pick p3.json --merge "Omar Lanza" omar@example.org
merge: keep 'Omar Lanza' <= ['omar@example.org']
```

The merged card keeps every number, and the other names go into the note so search still finds them (labels left out):

```json
{
 "name": "Tommaso Ferri",
 "phones": ["+49 176 555 0606", "+39 320 555 0707", "+39 0423 555 0808"],
 "emails": ["tommaso@example.org"],
 "note": "Also saved as: Tom cell, Tom casa"
}
```

The number `0176 555 0606` on "Tom cell" was not copied: it is the same number as `+49 176 555 0606`, written without the country code.

### 4. Name only

```
$ rb scan name-only --plan p4.json
5 name-only candidate pairs (review all)
  REVIEW Dad Tim | Dad Dad Work  (same name apart from descriptor words)
  REVIEW Gio Casa | Gio  (same name apart from descriptor words)
  REVIEW Gabri Gallo | Gabriella Gallo  (first name is a short form of the other)
  REVIEW Adriàn Ruiz | Adrián Ruiz  (same first and last name)
  REVIEW Ann Bell | ann_bell@example.org  (e-mail address spells the name)
```

These cards share nothing but the name, so every pair is a question for you. The scan recognises:

| Pattern | Example |
|---|---|
| words that describe a number, not a person: casa, cell, home, work, new, Tim, Vodafone… | "Dad Tim" and "Dad Dad Work"; "Gio Casa" and "Gio" |
| a short form of the first name, same surname | "Gabri Gallo" and "Gabriella Gallo" |
| the same name with different accents | "Adriàn Ruiz" and "Adrián Ruiz" |
| a card named by an e-mail address that spells a person's name | `ann_bell@example.org` and "Ann Bell" |

It does not pair "Paolo 2" with "Paolo Rinaldi". One first name is not enough.

### 5. Inside a card

```
$ rb scan in-card --plan p5.json
2 cards with values stored twice or repeated note lines
  Mira Novak: {'phones': ['0176 55520202'], 'emails': ['Mira.Novak@example.org'], 'addresses': ['Via Roma 1 31011 Asolo']}
  Ines Kraus: note lines
```

Of two spellings of one number, the international one (`+49 …`) stays. The lower-case e-mail stays. "Piano teacher / Piano teacher / Tuesdays" becomes "Piano teacher / Tuesdays".

### 8. Title Case (run last)

```
$ rb scan title-case --plan p8.json
5 cards to re-case
  Nora (vet) -> {'lastName': '(Vet)'}
  Ivo (judo) -> {'lastName': '(Judo)'}
  GIULIA MORETTI -> {'firstName': 'Giulia', 'lastName': 'Moretti'}
  elena fabbri -> {'firstName': 'Elena', 'lastName': 'Fabbri'}
  Paolo Di stefano -> {'lastName': 'Di Stefano'}
```

Left as they are: "Luca Rinaldi (VE)" (short abbreviations in capitals), "Greta McLeod" (deliberate mixed case), and cards named by an e-mail address. Pass `--keep WORD …` to protect more words. It runs last so that the people added in rungs 6 and 7 are covered too.

## Finding the people who are missing

### 6. Apple Mail

Rubrica reads Mail's own index, `~/Library/Mail/V*/MailData/Envelope Index`, read-only. It uses senders, To and Cc recipients, dates, and Mail's flags for mailing lists and automated mail. It never opens a message body.

First it asks which addresses are yours. Old ISP, university and work addresses count; if one is missing, it shows up as a "contact" and hides everyone you wrote to from it.

```
$ rb mail
Addresses that send and receive a lot; pass the ones that are yours with --me:
  sent     11  received     14  you@example.org
```

Then it ranks everyone who is not in Contacts:

```
$ rb mail --me you@example.org --years 3 --out mail.json
25 messages 2023-10-17..2026-10-16; 6 candidates -> mail.json

A (two-way: you wrote and they wrote, or you wrote 2+ times): 2
  s4   r4   cc0   2025  Sabine Weber                   s.weber@studio.example
  s3   r0   cc0   2025  Hausverwaltung Nord            hausverwaltung@flat.example

B (you wrote to them once): 1
  s1   r0   cc0   2025  Pietro Costa                   pietro.costa@example.org [name guessed]

C (they wrote to you personally 2+ times): 2
  s0   r3   cc0   2025  Club                           organiser@club.example
  s0   r2   cc0   2025  Kim Lee                        kim.lee@example.org

D (often on Cc with you): 1
  s0   r0   cc3   2025  Dora Fux                       dora.fux@example.org
```

What happened to the rest of the demo mailbox:
- The shop newsletter is gone: Mail flags it as a mailing list.
- The two `…@sale.craigslist.org` addresses are gone: classified-ad and booking sites create a new relay address for every conversation.
- Laura Bianchi is gone: she is already in Contacts.
- "Weber, Sabine" became "Sabine Weber".
- "Pietro Costa" is marked `[name guessed]`: the e-mail had no display name, so the name comes from `pietro.costa@`. An address like `pc1987@` gets no name at all.

You (or Claude, with you) keep the rows you want, mark companies, and turn the list into a plan:

```
$ rb add-plan mail.json --plan p6.json
0 cards get new values, 4 new cards -> p6.json
```

A row whose name matches exactly one existing card (with a first and a last name) adds the address to that card instead of creating a new one.

### 7. WhatsApp Desktop

```
$ rb whatsapp --folder examples/demo/whatsapp
WhatsApp address-book entries missing from Contacts: 1
  Yara (Swimming)                +491525552525

One-to-one chats with unsaved numbers: 2
  msgs=3    mine=1   last=2025-10-01  +393295552626      shown as '+39 329 555 2626' push name 'Foto Ottica Sole'
  msgs=1    mine=0   last=2025-10-13  +447700900272      shown as '+44 7700 900272' push name ''
```

- The first list comes from the address book on your phone, which WhatsApp copies to the Mac. These names are names you saved.
- The second list is chats with numbers saved nowhere. The push name is the name the other person gave themselves. A single unanswered message from an unknown country is usually spam.

The databases are copied to a temporary folder first. The running app's files are never opened for writing. Without `--folder`, it reads the desktop app's container in `~/Library/Group Containers/group.net.whatsapp.WhatsApp.shared`.

## Safety

- **A plan before every change.** Each scan writes a JSON plan. `rb apply plan.json` is a dry run that prints the counts; only `rb apply plan.json --yes` changes Contacts.
- **An undo file for every plan.** Before its first change to a card, `apply` appends the card's vCard to `plan.undo.vcf`, and it logs every op in `plan.log.json`.
- **A backup first.** `rb backup` writes every card, photos included, to one `.vcf`.
- **No guessing.** Shared landlines, chains through a corrupted card, one-word names and pairs found by name alone all become questions. The skill never invents a name and never assumes two people are related because they share a surname.
- **Old names are kept.** A merged card keeps the other names as `Also saved as: …` in its note.
- **Local only.** Python's standard library and `osascript`. Nothing goes over the network.

## Install

Requirements: macOS, [Claude Code](https://claude.com/claude-code), `python3` 3.10 or later (standard library only, nothing to install).

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

Then ask Claude Code something like:
- *"clean up my contacts"*
- *"merge my duplicate contacts"*
- *"which cards are named only by an e-mail address?"*
- *"who do I e-mail who isn't in my contacts?"*
- *"add the WhatsApp people I chat with to Contacts"*

Permissions macOS asks for:
- **Automation → Contacts** for your terminal, the first time a command reads or writes Contacts.
- **Full Disk Access** for your terminal, only for the Mail rung.

## Use it without Claude

Every step is a plain command. Run them in a folder of your choice: the files hold personal data. Below, `rb` stands for `PYTHONPATH=/path/to/rubrica python3 -m rubrica`.

| Command | What it does | Changes Contacts? |
|---|---|---|
| `rb backup [--dir D]` | every card, with photos, to one `.vcf` | no |
| `rb export [--out F] [--images]` | every card to JSON | no |
| `rb inventory` | counts: copies, e-mail-named cards, cards without a name or without any number | no |
| `rb scan KIND --plan P` | KIND is `exact`, `same-name`, `linked`, `name-only`, `in-card` or `title-case` | no |
| `rb pick P --merge KEEP OTHER… [--merge …]` | add approved merges to a plan, by exact name or card id | no |
| `rb mail [--me A…] [--ignore A…] [--years N \| --since D --until D]` | missing people from Apple Mail | no |
| `rb whatsapp [--out F]` | missing numbers from WhatsApp Desktop | no |
| `rb add-plan ROWS --plan P` | turn a list of `{name, address, phone, organization, company}` into add/create ops | no |
| `rb apply P` | dry run: what the plan would change | no |
| `rb apply P --offline contacts.json` | apply to an export instead, to preview the result | no |
| `rb apply P --yes` | apply to Contacts, with `P.undo.vcf` and `P.log.json` | yes |

Export again after every applied plan: merges delete cards, and a plan must point at cards that still exist.

A plan is plain JSON, so you can edit it before applying. Remove an op you disagree with, or change which card is kept:

```json
{"op": "merge", "keep": "C0FF…:ABPerson", "others": ["BEEF…:ABPerson"], "aliases": true,
 "_names": ["Roberto Landi", "Rob landi"]}
```

Other ops are `delete`, `remove_values`, `set` (for example `{"fields": {"firstName": "Dad", "lastName": ""}}` to rename a merged card), `add` and `create`. Keys starting with `_` are notes for you; `apply` ignores them.

## Try it on the demo

No Mac needed. The demo has 37 invented cards, a small Mail index and a small WhatsApp store:

```bash
python3 examples/make_demo.py      # writes examples/demo/
bash examples/walkthrough.sh       # runs all eight rungs offline -> examples/walkthrough.txt
```

The walkthrough takes the demo from 37 cards to 31 and ends with no copies and no e-mail-named cards left. [`examples/walkthrough.txt`](examples/walkthrough.txt) is the full output.

## How matching works

- **Phones** match on their last 9 digits, so `0176 5550606`, `+49 176 5550606` and `0049 1765550606` are one number. Numbers shorter than 8 digits (`*101#`, service codes) never link cards.
- **E-mails** match case-insensitively.
- **Two names fit together** when they share a word, or when a word of one starts the other with at least 3 letters (Tom / Tommaso, Rob / Roberto). Descriptor words like casa, cell, work and new are ignored.
- **A value shared by more than 4 cards** (a switchboard, a family landline used everywhere) links nothing.
- **The kept card** is the one with the most complete real name. A name in brackets, a descriptor word or an e-mail address ranks lower. After that: a photo, more fields, the most recent edit.
- **Merging** copies every phone, e-mail, URL, address, birthday and missing photo onto the kept card. It skips values the card already has in another format. A second company, a job title or a note goes into the note.

## Undo

- **One plan:** import `plan.undo.vcf` (double-click it, or File → Import in Contacts). This restores the cards as they were before the plan. After a merge it also brings back the old version of the kept card: delete the merged one first.
- **Everything:** import the `rb backup` file after deleting the current cards, or restore a Contacts archive (File → Export → Contacts Archive) made before you started.

## Limits

- macOS only for the parts that touch Contacts, Mail and WhatsApp. The scans, the demo and the tests run anywhere.
- Contacts scripting does not say which account (iCloud, Google, Exchange) a card lives in. Merging across accounts works, but a server-managed account may bring deleted cards back.
- WhatsApp support reads the macOS desktop app's databases. WhatsApp changes their format now and then.
- Phone matching on the last 9 digits can in theory join two different numbers from different countries that end the same way. Linked groups are always shown before merging.

## License

MIT. See [LICENSE](LICENSE).
