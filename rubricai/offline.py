"""Apply a plan to an exported contacts.json instead of Contacts.app.

Mirrors apply.js closely enough to preview a plan, to walk through the demo and to test
plan semantics without a Mac. apply.js stays the authority for the real address book.
"""
import copy
import uuid

from .normalize import email_key, is_redundant_alias, phone_key

_KEY = {"phones": phone_key, "emails": email_key,
        "urls": lambda v: (v or "").lower().rstrip("/") or None}
_PROP = {"firstName": "first", "middleName": "middle", "lastName": "last",
         "nickname": "nickname", "organization": "organization", "jobTitle": "job", "note": "note"}


def _display(c):
    if c.get("company"):
        return c.get("organization", "")
    return " ".join(p for p in (c.get("first"), c.get("middle"), c.get("last")) if p)


def _add(c, field, items):
    have = {_KEY[field](v["value"]) for v in c[field]}
    added = []
    for it in items:
        k = _KEY[field](it["value"])
        if k and k not in have:
            c[field].append({"label": it.get("label", ""), "value": it["value"]})
            have.add(k)
            added.append(it["value"])
    return added


def _merge(book, op):
    keep = book[op["keep"]]
    aliases, notes = [], []
    for oid in op["others"]:
        o = book.pop(oid)
        for f in ("phones", "emails", "urls"):
            _add(keep, f, o[f])
        have = {a["formatted"].lower() for a in keep["addresses"]}
        keep["addresses"] += [a for a in o["addresses"] if a["formatted"].lower() not in have]
        for f in ("organization", "job", "nickname"):
            if o.get(f) and not keep.get(f):
                keep[f] = o[f]
            elif o.get(f) and o[f].lower() != keep[f].lower():
                notes.append(f"{f.capitalize()}: {o[f]}")
        if o.get("birthday") and not keep.get("birthday"):
            keep["birthday"] = o["birthday"]
        if o.get("note") and o["note"].lower() not in (keep.get("note") or "").lower():
            notes.append(o["note"])
        name = o.get("name") or ""
        if op.get("aliases", True) and name and "@" not in name and not is_redundant_alias(name, keep["name"]):
            aliases.append(name)
    if aliases:
        notes.append("Also saved as: " + ", ".join(dict.fromkeys(aliases)))
    if notes:
        keep["note"] = "\n".join(filter(None, [keep.get("note") or "", *notes]))


def apply_plan(contacts, plan):
    """Return a new contacts list with the plan applied."""
    book = {c["id"]: copy.deepcopy(c) for c in contacts}
    for op in plan["ops"]:
        kind = op["op"]
        if kind == "delete":
            book.pop(op["id"], None)
        elif kind == "merge":
            _merge(book, op)
        elif kind == "set":
            c = book[op["id"]]
            for prop, value in op["fields"].items():
                c[_PROP[prop]] = value
            c["name"] = _display(c)
        elif kind == "remove_values":
            c = book[op["id"]]
            for f in ("phones", "emails", "urls"):
                for v in op.get(f, []):
                    for i, item in enumerate(c[f]):
                        if item["value"] == v:
                            del c[f][i]
                            break
            for v in op.get("addresses", []):
                norm = " ".join(v.lower().replace(",", " ").split())
                for i, a in enumerate(c["addresses"]):
                    if " ".join(a["formatted"].lower().replace(",", " ").split()) == norm:
                        del c["addresses"][i]
                        break
        elif kind == "add":
            for f in ("phones", "emails", "urls"):
                _add(book[op["id"]], f, op.get(f, []))
        elif kind == "create":
            c = dict(id=f"NEW-{uuid.uuid4().hex[:12]}", first=op.get("firstName", ""), middle="",
                     last=op.get("lastName", ""), nickname="", company=bool(op.get("company")),
                     organization=op.get("organization", ""), job="", note=op.get("note", ""),
                     birthday=None, modified=None, phones=[], emails=[], urls=[], addresses=[])
            _add(c, "phones", op.get("phones", []))
            _add(c, "emails", op.get("emails", []))
            c["name"] = _display(c)
            book[c["id"]] = c
    return list(book.values())
