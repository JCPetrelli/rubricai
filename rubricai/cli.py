"""rubricai command line. Run `python3 -m rubricai --help`.

Read commands: backup, export, inventory, scan, mail, whatsapp.
The only command that changes Contacts is `apply`, and only with --yes.
"""
import argparse
import collections
import datetime as dt
import json
import os
import subprocess
import sys

from . import dedupe, mail, offline, plan as planlib, whatsapp
from .normalize import is_email_name, name_tokens

JXA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "jxa")
STAMP = lambda: dt.datetime.now().strftime("%Y%m%d-%H%M%S")  # noqa: E731


def osascript(script, *args):
    res = subprocess.run(["osascript", "-l", "JavaScript", os.path.join(JXA, script), *args],
                         capture_output=True, text=True)
    if res.returncode:
        sys.exit(f"{script} failed: {res.stderr.strip()}\n"
                 "If this is the first run, allow the terminal to control Contacts "
                 "(System Settings > Privacy & Security > Automation).")
    return res.stdout.strip()


def load_contacts(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def label(c):
    return c.get("name") or "(no name)"


# ---------------------------------------------------------------- commands

def cmd_backup(a):
    os.makedirs(a.dir, exist_ok=True)
    out = os.path.join(a.dir, f"contacts-{STAMP()}.vcf")
    print(osascript("backup.js", out), "->", out)


def cmd_export(a):
    print(osascript("export.js", a.out, *(["images"] if a.images else [])), "->", a.out)


def cmd_inventory(a):
    cs = load_contacts(a.contacts)
    exact = dedupe.exact_copies(cs)
    print(f"cards                      {len(cs)}")
    print(f"exact copies (extra cards) {sum(len(g) - 1 for g in exact)} in {len(exact)} sets")
    print(f"named by an e-mail address {sum(is_email_name(c['name']) for c in cs)}")
    print(f"without a name             {sum(not c['name'].strip() for c in cs)}")
    print(f"without phone and e-mail   {sum(not c['phones'] and not c['emails'] for c in cs)}")


def _print_groups(groups, limit):
    for g in groups[:limit]:
        print("  " + label(g[0]) + "  <=  " + " | ".join(label(c) for c in g[1:]))
    if len(groups) > limit:
        print(f"  ... {len(groups) - limit} more (all in the plan file)")


def cmd_scan(a):
    cs = load_contacts(a.contacts)
    review, notes = [], []
    if a.kind == "exact":
        ops = planlib.exact_ops(cs)
        print(f"{len(ops)} exact copies to delete")
    elif a.kind == "same-name":
        merge, ambiguous = dedupe.same_name_groups(cs)
        ops = planlib.merge_ops(merge)
        review = [{"reason": "one-word name, nothing shared", "names": [label(c) for c in g],
                   "ids": [c["id"] for c in g]} for g in ambiguous]
        print(f"{len(merge)} same-name groups to merge; {len(ambiguous)} ambiguous (review)")
        _print_groups(merge, a.limit)
    elif a.kind == "linked":
        merge, pairs, chains = dedupe.linked_groups(cs)
        ops = planlib.merge_ops(merge)
        review = [{"reason": f"share {k}, names differ", "names": [label(x), label(y)],
                   "ids": [x["id"], y["id"]]} for x, y, k in pairs]
        review += [{"reason": "chain: linked cards with unrelated names", "names": [label(c) for c in g],
                    "ids": [c["id"] for c in g]} for g in chains]
        print(f"{len(merge)} linked groups to merge; {len(pairs)} pairs and {len(chains)} chains to review")
        _print_groups(merge, a.limit)
    elif a.kind == "name-only":
        ops = []
        review = [{"reason": why, "names": [label(x), label(y)], "ids": [x["id"], y["id"]]}
                  for x, y, why in dedupe.name_only_pairs(cs)]
        notes.append("Nothing here is applied automatically: move approved pairs into ops with `pick`.")
        print(f"{len(review)} name-only candidate pairs (review all)")
    elif a.kind == "in-card":
        ops = planlib.in_card_ops(cs)
        print(f"{len(ops)} cards with values stored twice or repeated note lines")
        for op in ops[:a.limit]:
            what = {k: v for k, v in op.items() if k in ("phones", "emails", "urls", "addresses")}
            print(f"  {op['_name']}: {what or 'note lines'}")
    elif a.kind == "title-case":
        ops = planlib.title_case_ops(cs, keep=a.keep)
        print(f"{len(ops)} cards to re-case")
        for op in ops[:a.limit]:
            print(f"  {op['_name']} -> {op['fields']}")
    for r in review[:a.limit]:
        print(f"  REVIEW {' | '.join(r['names'])}  ({r['reason']})")
    p = planlib.new(a.kind, ops, notes)
    p["review"] = review
    planlib.save(p, a.plan)
    print(f"plan: {a.plan}")


def cmd_pick(a):
    """Add user-approved merges to a plan. Each item is an exact card name or a card id."""
    cs = load_contacts(a.contacts)
    by_id = {c["id"]: c for c in cs}
    by_name = collections.defaultdict(list)
    for c in cs:
        by_name[c["name"]].append(c)
    p = planlib.load(a.plan) if os.path.exists(a.plan) else planlib.new("picked", [])
    for items in a.merge:
        group = []
        for item in items:
            found = [by_id[item]] if item in by_id else by_name.get(item, [])
            if len(found) != 1:
                sys.exit(f"'{item}' matches {len(found)} cards; use the card id from the plan or export")
            group.append(found[0])
        p["ops"] += planlib.merge_ops([group])
        print(f"merge: keep {label(group[0])!r} <= {[label(c) for c in group[1:]]}")
    planlib.save(p, a.plan)


def cmd_mail(a):
    db = a.db or mail.envelope_index()
    if not a.me:
        print("Addresses that send and receive a lot; pass the ones that are yours with --me:")
        for addr, sent, received in mail.likely_own_addresses(db):
            print(f"  sent {sent:6}  received {received:6}  {addr}")
        return
    cs = load_contacts(a.contacts)
    known = {e["value"].strip().lower() for c in cs for e in c["emails"]}
    until = dt.datetime.fromisoformat(a.until) if a.until else dt.datetime.now()
    since = dt.datetime.fromisoformat(a.since) if a.since else until - dt.timedelta(days=365 * a.years)
    msgs = mail.load(db, since, until)
    rows = mail.score(msgs, a.me, known, a.ignore)
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=1)
    print(f"{len(msgs)} messages {since:%Y-%m-%d}..{until:%Y-%m-%d}; {len(rows)} candidates -> {a.out}")
    for tier, desc in mail.TIERS.items():
        tr = [r for r in rows if r["tier"] == tier]
        print(f"\n{tier} ({desc}): {len(tr)}")
        for r in tr[:a.limit]:
            flag = " [automated?]" if r["automated"] else ""
            guess = " [name guessed]" if r["name_guessed"] else ""
            print(f"  s{r['sent']:<3} r{r['received']:<3} cc{r['cc_with']:<3} {r['last'][:4]}  "
                  f"{r['name'][:30]:30} {r['address']}{flag}{guess}")


def cmd_add_plan(a):
    """Build add/create ops from a reviewed list of people (mail or WhatsApp output).

    Each row needs a name (or company: true + organization) and an address and/or phone.
    A row whose name matches exactly one card with two or more name words is added to that
    card; everything else becomes a new card. Rows without a name are skipped: ask the user.
    """
    rows = json.load(open(a.rows, encoding="utf-8"))
    cs = load_contacts(a.contacts)
    by_name = collections.defaultdict(list)
    for c in cs:
        if c["name"]:
            by_name[" ".join(name_tokens(c["name"]))].append(c)
    ops, created, skipped = [], {}, []
    for r in rows:
        is_company = bool(r.get("company"))
        name = (r.get("name") or "").strip()
        org = r.get("organization") or (name if is_company else "")
        work = bool(org)
        emails = [{"label": "work" if work else "home", "value": r["address"]}] if r.get("address") else []
        phones = [{"label": "mobile", "value": r["phone"]}] if r.get("phone") else []
        if not (name or org) or not (emails or phones):
            skipped.append(r.get("address") or r.get("phone") or "?")
            continue
        key = " ".join(name_tokens(org if is_company else name))
        match = by_name.get(key, [])
        if len(key.split()) >= 2 and len(match) == 1:
            ops.append({"op": "add", "id": match[0]["id"], "_name": match[0]["name"],
                        "emails": emails, "phones": phones})
        elif key in created:
            created[key]["emails"] += emails
            created[key]["phones"] += phones
        else:
            first, _, last = ("", "", "") if is_company else name.partition(" ")
            op = {"op": "create", "firstName": first, "lastName": last, "organization": org,
                  "company": is_company, "emails": emails, "phones": phones, "note": r.get("note", "")}
            created[key] = op
            ops.append(op)
    planlib.save(planlib.new("add", ops), a.plan)
    print(f"{sum(o['op'] == 'add' for o in ops)} cards get new values, "
          f"{sum(o['op'] == 'create' for o in ops)} new cards -> {a.plan}")
    if skipped:
        print(f"skipped {len(skipped)} rows without a name: {', '.join(skipped[:10])}")


def cmd_whatsapp(a):
    cs = load_contacts(a.contacts)
    folder = whatsapp.snapshot(a.folder) if a.folder else whatsapp.snapshot()
    book, chats = whatsapp.missing(folder, [p["value"] for c in cs for p in c["phones"]])
    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            json.dump({"address_book": book, "chats": chats}, f, ensure_ascii=False, indent=1)
        print(f"-> {a.out}")
    print(f"WhatsApp address-book entries missing from Contacts: {len(book)}")
    for b in book:
        print(f"  {b['name']:30} {b['phone']}")
    print(f"\nOne-to-one chats with unsaved numbers: {len(chats)}")
    for c in chats[:a.limit]:
        print(f"  msgs={c['messages']:<4} mine={c['from_me']:<3} last={c['last']}  "
              f"{c['phone']:18} shown as {c['shown_as']!r} push name {c['push_name']!r}")


def cmd_apply(a):
    p = planlib.load(a.plan)
    count, cards = planlib.summary(p)
    print(f"plan {a.plan}: {count}; removes {cards} cards")
    if a.offline:
        cs = load_contacts(a.offline)
        after = offline.apply_plan(cs, p)
        with open(a.offline, "w", encoding="utf-8") as f:
            json.dump(after, f, ensure_ascii=False, indent=1)
        print(f"offline: {len(cs)} -> {len(after)} cards in {a.offline}; Contacts.app untouched")
        return
    if not a.yes:
        print("dry run: nothing changed. Re-run with --yes after the user approved this plan.")
        return
    base = os.path.splitext(a.plan)[0]
    clean = dict(p, ops=[{k: v for k, v in op.items() if not k.startswith("_")} for op in p["ops"]])
    tmp = base + ".apply.json"
    planlib.save(clean, tmp)
    print(osascript("apply.js", tmp, base + ".undo.vcf", base + ".log.json"))


def main(argv=None):
    ap = argparse.ArgumentParser(prog="rubricai", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("backup", help="all cards to one .vcf")
    s.add_argument("--dir", default="rubricai-backups")
    s = sub.add_parser("export", help="all cards to JSON (read-only)")
    s.add_argument("--out", default="contacts.json")
    s.add_argument("--images", action="store_true", help="also record which cards have a photo (slower)")
    s = sub.add_parser("inventory", help="counts of likely problems")
    s.add_argument("--contacts", default="contacts.json")
    s = sub.add_parser("scan", help="build a plan for one kind of cleanup")
    s.add_argument("kind", choices=["exact", "same-name", "linked", "name-only", "in-card", "title-case"])
    s.add_argument("--contacts", default="contacts.json")
    s.add_argument("--plan", required=True)
    s.add_argument("--keep", nargs="*", default=[], help="title-case: words to leave as they are")
    s.add_argument("--limit", type=int, default=40)
    s = sub.add_parser("pick", help="add approved merges to a plan by card name")
    s.add_argument("plan")
    s.add_argument("--contacts", default="contacts.json")
    s.add_argument("--merge", nargs="+", action="append", required=True, metavar="NAME_OR_ID",
                   help="keeper first, then the cards to fold in (exact name or card id); repeatable")
    s = sub.add_parser("mail", help="people in Apple Mail missing from Contacts")
    s.add_argument("--contacts", default="contacts.json")
    s.add_argument("--me", nargs="*", default=[], help="your own addresses")
    s.add_argument("--ignore", nargs="*", default=[], help="addresses to skip (bots, aliases)")
    s.add_argument("--years", type=float, default=10)
    s.add_argument("--since")
    s.add_argument("--until")
    s.add_argument("--out", default="mail-candidates.json")
    s.add_argument("--db", help="path to an Envelope Index (default: the one Apple Mail uses)")
    s.add_argument("--limit", type=int, default=60)
    s = sub.add_parser("add-plan", help="turn a reviewed list of people into a plan")
    s.add_argument("rows", help="JSON list of {name, address?, phone?, organization?, company?, note?}")
    s.add_argument("--contacts", default="contacts.json")
    s.add_argument("--plan", required=True)
    s = sub.add_parser("whatsapp", help="WhatsApp Desktop numbers missing from Contacts")
    s.add_argument("--contacts", default="contacts.json")
    s.add_argument("--out", help="also write the lists as JSON")
    s.add_argument("--folder", help="WhatsApp data folder (default: the desktop app's container)")
    s.add_argument("--limit", type=int, default=60)
    s = sub.add_parser("apply", help="apply a reviewed plan (dry run without --yes)")
    s.add_argument("plan")
    s.add_argument("--yes", action="store_true")
    s.add_argument("--offline", metavar="CONTACTS_JSON",
                   help="apply to an exported JSON file instead of Contacts.app (preview, demo, tests)")
    a = ap.parse_args(argv)
    {"backup": cmd_backup, "export": cmd_export, "inventory": cmd_inventory, "scan": cmd_scan,
     "pick": cmd_pick, "mail": cmd_mail, "add-plan": cmd_add_plan, "whatsapp": cmd_whatsapp,
     "apply": cmd_apply}[a.cmd](a)
