"""Find people you correspond with in Apple Mail who are missing from Contacts.

Reads Mail's own index (~/Library/Mail/V*/MailData/Envelope Index), read-only.
It needs Full Disk Access for the terminal. No message bodies are read: senders,
To/Cc recipients, dates and Mail's list/automation flags are enough.
"""
import collections
import datetime as dt
import glob
import os
import re
import sqlite3

from .normalize import display_name_from_header, email_key, name_from_address

# Addresses that are machines, not people.
AUTOMATED = re.compile(
    r"(no-?reply|donotreply|do-not-reply|notif|newsletter|news@|mailer|bounce|daemon|"
    r"postmaster|alert|updates?@|digest|marketing|promo|offers?@|deals|billing|invoice|"
    r"receipt|account|security|support|help@|service|team@|hello@|feedback|survey|"
    r"reply[+-]|calendar|automated|system|admin@|webmaster@|orders?@|shop@|store@|"
    r"booking|reservations?|tickets?@|press@|jobs@|careers|recruit|community|members?@|"
    r"subscriptions?|unsubscribe|info@|contact@|mail@|email@|notify|robot|bot@)", re.I)
# One-off relay addresses: a new address per conversation, useless as a contact.
RELAY_DOMAINS = re.compile(
    r"@([\w-]+\.)*(craigslist\.org|kleinanzeigen\.de|ebay-kleinanzeigen\.de|"
    r"marketplace\.amazon\.\w+|booking\.com|airbnb\.com|jobvite\.com|customer\.io|"
    r"hubspotemail\.net|zendesk\.com|freshdesk\.com|trello\.com|followupthen\.com|"
    r"ifttt\.com|kindle\.com)$", re.I)
TIERS = {
    "A": "two-way: you wrote and they wrote, or you wrote 2+ times",
    "B": "you wrote to them once",
    "C": "they wrote to you personally 2+ times",
    "D": "often on Cc with you",
}


def envelope_index():
    paths = sorted(glob.glob(os.path.expanduser("~/Library/Mail/V*/MailData/Envelope Index")))
    if not paths:
        raise SystemExit("Mail index not found. Is Apple Mail set up, and does this terminal "
                         "have Full Disk Access (System Settings > Privacy & Security)?")
    return paths[-1]


def _query(db, sql, params=()):
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        return con.execute(sql, params).fetchall()
    finally:
        con.close()


_BASE = """
from messages m
join mailboxes mb on mb.ROWID = m.mailbox
where m.deleted = 0 and m.date_received between ? and ?
  and mb.url not like '%Spam%' and mb.url not like '%Junk%' and mb.url not like '%Trash%'
"""


def load(db, since, until):
    """{message_key: {date, sender, sender_name, bulk, rcpt: [(type, address, name)]}}"""
    span = (int(since.timestamp()), int(until.timestamp()))
    msgs = {}
    for gid, date, sender, name, lst, unsub, auto in _query(db, f"""
        select m.global_message_id, m.date_received, lower(a.address), coalesce(a.comment, ''),
               coalesce(m.list_id_hash, 0) != 0, coalesce(m.unsubscribe_type, 0),
               coalesce(m.automated_conversation, 0)
        {_BASE.replace('where', 'join addresses a on a.ROWID = m.sender where')}""", span):
        msgs.setdefault(gid, dict(date=date, sender=sender, sender_name=name,
                                  bulk=bool(lst or unsub or auto), rcpt=[]))
    for gid, rtype, addr, name in _query(db, f"""
        select m.global_message_id, r.type, lower(a.address), coalesce(a.comment, '')
        {_BASE.replace('where', 'join recipients r on r.message = m.ROWID join addresses a on a.ROWID = r.address where')}""",
                                          span):
        if gid in msgs:
            msgs[gid]["rcpt"].append((rtype, addr, name))
    return msgs


def likely_own_addresses(db, limit=12):
    """Addresses that both send and receive a lot are almost always yours.

    Gmail keeps sent mail in All Mail, so the Sent mailbox alone misses it.
    Returns [(address, sent, received)] to show the user, who confirms with --me.
    """
    return _query(db, """
        with s as (select lower(a.address) a, count(*) n from messages m
                   join addresses a on a.ROWID = m.sender group by 1),
             r as (select lower(a.address) a, count(*) n from recipients r
                   join addresses a on a.ROWID = r.address group by 1)
        select s.a, s.n, r.n from s join r on r.a = s.a
        where s.n >= 5 and r.n >= 5 order by s.n desc limit ?""", (limit,))


def score(msgs, me, known_emails, ignore=()):
    """Rank every address that is not you and not already in Contacts."""
    me = {m.lower() for m in me}
    ignore = {i.lower() for i in ignore}
    stats = collections.defaultdict(lambda: dict(sent=0, received=0, cc_with=0, first=None,
                                                 last=None, names=collections.Counter()))

    def touch(addr, date, name):
        s = stats[addr]
        s["first"] = date if s["first"] is None else min(s["first"], date)
        s["last"] = date if s["last"] is None else max(s["last"], date)
        name = display_name_from_header(name)
        if name:
            s["names"][name] += 1

    for m in msgs.values():
        if m["sender"] in ignore:
            continue
        if m["sender"] in me:
            for _, addr, name in m["rcpt"]:
                if addr not in me:
                    stats[addr]["sent"] += 1
                    touch(addr, m["date"], name)
        elif not m["bulk"] and {a for _, a, _ in m["rcpt"]} & me:
            stats[m["sender"]]["received"] += 1
            touch(m["sender"], m["date"], m["sender_name"])
            for _, addr, name in m["rcpt"]:
                if addr not in me and addr != m["sender"]:
                    stats[addr]["cc_with"] += 1
                    touch(addr, m["date"], name)

    out = []
    for addr, s in stats.items():
        if not email_key(addr) or addr in known_emails or addr in me or addr in ignore:
            continue
        if RELAY_DOMAINS.search(addr):
            continue
        automated = bool(AUTOMATED.search(addr))
        if s["sent"] and s["received"] or s["sent"] >= 2:
            tier = "A"
        elif s["sent"] == 1:
            tier = "B"
        elif s["received"] >= 2 and not automated:
            tier = "C"
        elif s["cc_with"] >= 3 and not automated:
            tier = "D"
        else:
            continue
        name = s["names"].most_common(1)[0][0] if s["names"] else ""
        guessed = False
        if not name and name_from_address(addr):
            name, guessed = " ".join(name_from_address(addr)), True
        out.append(dict(address=addr, name=name, name_guessed=guessed, tier=tier,
                        automated=automated, sent=s["sent"], received=s["received"],
                        cc_with=s["cc_with"],
                        first=dt.date.fromtimestamp(s["first"]).isoformat(),
                        last=dt.date.fromtimestamp(s["last"]).isoformat()))
    out.sort(key=lambda r: (r["tier"], r["automated"], -(r["sent"] + r["received"] + r["cc_with"])))
    return out
