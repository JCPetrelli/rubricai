"""Synthetic address books. Every person here is invented."""
import itertools

_ids = itertools.count(1)


def card(name="", first="", last="", phones=(), emails=(), note="", company=False,
         organization="", addresses=(), urls=(), nickname="", modified="2024-01-01T00:00:00Z",
         **extra):
    if name and not (first or last or company):
        first, _, last = name.partition(" ")
    return dict(id=f"ID{next(_ids)}", name=name, first=first, middle="", last=last,
                nickname=nickname, company=company, organization=organization, job="",
                note=note, birthday=None, modified=modified,
                phones=[{"label": "mobile", "value": p} for p in phones],
                emails=[{"label": "home", "value": e} for e in emails],
                urls=[{"label": "home", "value": u} for u in urls],
                addresses=[{"label": "home", "formatted": a} for a in addresses], **extra)


def names(groups):
    return [[c["name"] for c in g] for g in groups]
