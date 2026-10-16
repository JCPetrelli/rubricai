"""Turn scan results into a plan: a JSON list of ops that apply.js executes.

A plan is the review artefact. It is written to disk, shown to the user, edited if
needed, and only then applied. Builders never mutate anything.
"""
import datetime as dt
import json

from . import dedupe
from .normalize import title_case

FIELDS = {"first": "firstName", "middle": "middleName", "last": "lastName",
          "nickname": "nickname"}


def new(kind, ops, notes=None):
    return {"version": 1, "kind": kind, "created": dt.datetime.now().isoformat(timespec="seconds"),
            "notes": notes or [], "ops": ops}


def save(plan, path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(plan, f, ensure_ascii=False, indent=1)


def load(path):
    with open(path, encoding="utf-8") as f:
        plan = json.load(f)
    if plan.get("version") != 1 or not isinstance(plan.get("ops"), list):
        raise SystemExit(f"{path} is not a rubrica plan")
    return plan


def merge_ops(groups, aliases=True):
    """groups: lists of contacts, survivor first (dedupe.order_group did that)."""
    return [{"op": "merge", "keep": g[0]["id"], "others": [c["id"] for c in g[1:]],
             "aliases": aliases, "_names": [c["name"] for c in g]} for g in groups]


def exact_ops(contacts):
    return [{"op": "delete", "id": c["id"], "_name": c["name"]}
            for g in dedupe.exact_copies(contacts) for c in g[1:]]


def in_card_ops(contacts):
    ops = []
    for c in contacts:
        drop = dedupe.in_card_duplicates(c)
        if drop:
            ops.append({"op": "remove_values", "id": c["id"], "_name": c["name"], **drop})
        lines = dedupe.repeated_note_lines(c.get("note"))
        if lines:
            ops.append({"op": "set", "id": c["id"], "_name": c["name"],
                        "fields": {"note": "\n".join(lines)}})
    return ops


def title_case_ops(contacts, keep=()):
    ops = []
    for c in contacts:
        if dedupe.is_email_name(c.get("name")):
            continue
        fields = {}
        if c.get("company"):
            new_org = title_case(c.get("organization"), keep, c.get("name"))
            if new_org != c.get("organization"):
                fields["organization"] = new_org
        else:
            for src, prop in FIELDS.items():
                value = c.get(src)
                fixed = title_case(value, keep, c.get("name"))
                if value and fixed != value:
                    fields[prop] = fixed
        if fields:
            ops.append({"op": "set", "id": c["id"], "_name": c["name"], "fields": fields})
    return ops


def summary(plan):
    count = {}
    for op in plan["ops"]:
        count[op["op"]] = count.get(op["op"], 0) + 1
    cards = sum(len(op.get("others", [])) for op in plan["ops"] if op["op"] == "merge")
    cards += count.get("delete", 0)
    return count, cards
