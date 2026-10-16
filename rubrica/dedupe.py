"""Duplicate scans over an exported address book.

A contact is a dict as written by `rubrica export`:
  id, name, first, middle, last, nickname, company (bool), organization, job,
  phones/emails/urls [{label, value}], addresses [{label, formatted}], note,
  birthday, modified, has_image (only with --images).

Every scan returns plain data. Nothing here touches Contacts.app; apply.py does.
The scans form a ladder, from no judgement needed to a lot:
  exact copies -> same name -> linked by phone/e-mail -> name only (entity resolution).
"""
import collections
import itertools
import re

from .normalize import (DESCRIPTORS, email_key, is_email_name, name_tokens,
                        names_compatible, phone_key, strip_accents)

# A phone or e-mail shared by more cards than this is a switchboard, a family landline
# or a corrupted card. It must not glue cards together.
MAX_SHARED_KEY = 4


def _values(contact, field):
    return [v["value"] if isinstance(v, dict) else v for v in contact.get(field) or []]


def _addresses(contact):
    return [a["formatted"] if isinstance(a, dict) else a for a in contact.get("addresses") or []]


def _norm_text(text):
    return re.sub(r"[\s,.]+", " ", (text or "").lower()).strip()


def keys(contact):
    out = {("p", k) for k in map(phone_key, _values(contact, "phones")) if k}
    out |= {("e", k) for k in map(email_key, _values(contact, "emails")) if k}
    if is_email_name(contact.get("name")):
        out.add(("e", contact["name"].strip().lower()))
    return out


def primary_score(contact):
    """Which card survives a merge: a real name beats a nickname or an e-mail."""
    name = contact.get("name") or ""
    fields = sum(len(contact.get(f) or []) for f in ("phones", "emails", "addresses", "urls"))
    return (
        not is_email_name(name) and bool(name.strip()),
        bool(contact.get("first")) and bool(contact.get("last")),
        "(" not in name and not any(t in DESCRIPTORS for t in name_tokens(name)),
        bool(contact.get("has_image")),
        fields + bool(contact.get("note")) + bool(contact.get("birthday")),
        contact.get("modified") or "",
    )


def order_group(group):
    return sorted(group, key=primary_score, reverse=True)


# ------------------------------------------------------------ 1. exact copies

def _signature(c):
    return (
        (c.get("name") or "").strip().lower(),
        tuple(sorted(k for k in map(phone_key, _values(c, "phones")) if k)),
        tuple(sorted(k for k in map(email_key, _values(c, "emails")) if k)),
        tuple(sorted(_norm_text(a) for a in _addresses(c))),
        tuple(sorted(_values(c, "urls"))),
        *((c.get(f) or "").strip() for f in ("organization", "job", "nickname", "note", "birthday")),
    )


def exact_copies(contacts):
    """Cards identical in every exported field. Safe to delete all but one."""
    by_sig = collections.defaultdict(list)
    for c in contacts:
        by_sig[_signature(c)].append(c)
    return [order_group(g) for g in by_sig.values() if len(g) > 1]


# ------------------------------------------------------------ 2. same name

def same_name_groups(contacts):
    """Cards with the same display name. Returns (merge, ambiguous).

    A one-word name ('Nina') with no phone or e-mail in common is ambiguous:
    two different Ninas is the likelier story.
    """
    by_name = collections.defaultdict(list)
    for c in contacts:
        key = re.sub(r"\s+", " ", (c.get("name") or "").lower()).strip()
        if key and not is_email_name(key):
            by_name[key].append(c)
    merge, ambiguous = [], []
    for name, group in by_name.items():
        if len(group) < 2:
            continue
        shared = any(keys(a) & keys(b) for a, b in itertools.combinations(group, 2))
        (merge if shared or len(name.split()) >= 2 else ambiguous).append(order_group(group))
    return merge, ambiguous


# ------------------------------------------------------------ 3. linked by phone / e-mail

def linked_groups(contacts, max_shared=MAX_SHARED_KEY):
    """Different names joined by a phone or e-mail. Returns (merge, review, chains).

    merge   - every pair of names in the group is compatible ('Rob landi' ~ 'Roberto Landi')
    review  - [(a, b, key)] pairs sharing a key whose names do not fit (household landline?)
    chains  - groups that compatible links joined but that hold incompatible names:
              transitive closure went too far, so a human must split them.
    """
    by_key = collections.defaultdict(list)
    for c in contacts:
        for k in keys(c):
            by_key[k].append(c["id"])
    index = {c["id"]: c for c in contacts}
    parent = {c["id"]: c["id"] for c in contacts}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    review, seen = [], set()
    for k, ids in by_key.items():
        ids = sorted(set(ids))
        if not 1 < len(ids) <= max_shared:
            continue
        for a, b in itertools.combinations(ids, 2):
            if (a, b) in seen:
                continue
            seen.add((a, b))
            if names_compatible(index[a].get("name"), index[b].get("name")):
                parent[find(a)] = find(b)
            else:
                review.append((index[a], index[b], f"{k[0]}:{k[1]}"))
    groups = collections.defaultdict(list)
    for cid in parent:
        groups[find(cid)].append(index[cid])
    merge, chains = [], []
    for g in groups.values():
        if len(g) < 2:
            continue
        names = [c.get("name") for c in g if c.get("name") and not is_email_name(c.get("name"))]
        bad = any(not names_compatible(a, b) for a, b in itertools.combinations(names, 2))
        (chains if bad else merge).append(order_group(g))
    return merge, review, chains


# ------------------------------------------------------------ 4. name only

def _first_last(c):
    first = "".join(name_tokens(c.get("first")))
    last = "".join(name_tokens(c.get("last")))
    return first, last


def name_only_pairs(contacts):
    """Entity resolution without a shared key. Returns [(a, b, reason)] to review.

    - an e-mail-named card whose address spells a person's name
    - same name once descriptor words are removed ('Dad Tim' / 'Dad Work')
    - same surname, first name a nickname prefix ('Gabri' / 'Gabriella')
    - same first + last after accents ('Adriàn' / 'Adrián')
    """
    people = [c for c in contacts if not c.get("company")]
    named = [c for c in people if c.get("name") and not is_email_name(c["name"])]
    pairs = {}

    def add(a, b, why):
        if a["id"] == b["id"] or keys(a) & keys(b):
            return                                # linked_groups already covers shared keys
        k = tuple(sorted((a["id"], b["id"])))
        pairs.setdefault(k, (a, b, why))

    for e in (c for c in people if is_email_name(c.get("name"))):
        flat = re.sub(r"[^a-z]", "", strip_accents(e["name"].split("@")[0]).lower())
        for c in named:
            first, last = _first_last(c)
            if len(last) >= 3 and last in flat and (first in flat or flat.startswith(first[:1] + last)):
                add(c, e, "e-mail address spells the name")

    # A card whose name carries descriptor words ('Dad Tim', 'Gio Casa') or a repeated
    # word ('Dad Dad Work') is matched against cards whose core name contains its core.
    core = {c["id"]: set(name_tokens(c["name"], drop_descriptors=True)) for c in named}
    decorated = [c for c in named
                 if len(name_tokens(c["name"])) > len(set(name_tokens(c["name"])) - DESCRIPTORS)]
    for a in decorated:
        if not core[a["id"]]:
            continue
        for b in named:
            if b is a or (b.get("name") or "").lower() == a["name"].lower():
                continue
            ca, cb = core[a["id"]], core[b["id"]]
            if not cb:
                continue
            if len(ca) == 1 and len(cb) == 1:
                ok = ca == cb                                   # 'Gio Casa' ~ 'Vale'
            elif len(ca) == 1 or len(cb) == 1:
                ok = (ca <= cb or cb <= ca) and b in decorated  # 'Dad Tim' ~ 'Dad Dad Work'
            else:
                ok = ca <= cb or cb <= ca                       # 'Mario Rossi Ufficio' ~ 'Mario Rossi'
            if ok:
                add(a, b, "same name apart from descriptor words")

    by_last = collections.defaultdict(list)
    for c in named:
        first, last = _first_last(c)
        if first and len(last) >= 4:
            by_last[last].append((c, first))
    for last, group in by_last.items():
        for (a, fa), (b, fb) in itertools.combinations(group, 2):
            if fa == fb:
                add(a, b, "same first and last name")
            elif min(len(fa), len(fb)) >= 3 and (fa.startswith(fb) or fb.startswith(fa)):
                add(a, b, "first name is a short form of the other")
    return [pairs[k] for k in sorted(pairs)]


# ------------------------------------------------------------ inside one card

def in_card_duplicates(contact):
    """Values stored twice on one card, as {field: [values to remove]}.

    Of two spellings of one phone number the international one (+39…) stays.
    """
    out = {}
    rules = {
        "phones": (phone_key, lambda v: (v.strip().startswith("+"), len(v))),
        "emails": (email_key, lambda v: v == v.lower()),
        "urls": (lambda v: re.sub(r"^(https?://)?(www\.)?", "", v.lower()).rstrip("/"), len),
        "addresses": (_norm_text, len),
    }
    for field, (key, score) in rules.items():
        values = _addresses(contact) if field == "addresses" else _values(contact, field)
        best = {}
        for v in values:
            k = key(v)
            if k and (k not in best or score(v) > score(best[k])):
                best[k] = v
        drop, kept = [], set()
        for v in values:
            k = key(v)
            if k and (best[k] != v or v in kept):
                drop.append(v)
            elif k:
                kept.add(v)
        if drop:
            out[field] = drop
    return out


def repeated_note_lines(note):
    lines = [line.strip() for line in (note or "").splitlines() if line.strip()]
    unique = list(dict.fromkeys(lines))
    return unique if len(unique) < len(lines) else None
