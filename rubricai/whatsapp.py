"""Find WhatsApp Desktop (macOS) contacts and chats missing from Apple Contacts.

WhatsApp keeps two SQLite stores in its group container:
  ContactsV2.sqlite  - the phone address book entries that are on WhatsApp (named)
  ChatStorage.sqlite - chats; ZSESSIONTYPE 0 = one-to-one
The databases are copied to a temporary folder before reading, so the running app's
files are never opened for writing.
"""
import datetime as dt
import os
import re
import shutil
import sqlite3
import tempfile

from .normalize import phone_key

CONTAINER = os.path.expanduser("~/Library/Group Containers/group.net.whatsapp.WhatsApp.shared")
APPLE_EPOCH = 978307200  # Core Data dates count from 2001-01-01


def snapshot(container=CONTAINER):
    if not os.path.isdir(container):
        raise SystemExit(f"WhatsApp Desktop data not found at {container}")
    tmp = tempfile.mkdtemp(prefix="rubricai-wa-")
    for name in os.listdir(container):
        if name.startswith(("ChatStorage.sqlite", "ContactsV2.sqlite")):
            shutil.copy2(os.path.join(container, name), tmp)
    return tmp


def missing(folder, known_phones):
    """Returns (address_book, chats): entries whose number is not in Apple Contacts."""
    known = {k for k in map(phone_key, known_phones) if k}
    cv = sqlite3.connect(os.path.join(folder, "ContactsV2.sqlite"))
    book = cv.execute("select ZFULLNAME, ZPHONENUMBER, ZWHATSAPPID, ZLID "
                      "from ZWAADDRESSBOOKCONTACT").fetchall()
    cv.close()
    by_jid = {}
    for row in book:
        for jid in row[2:]:
            if jid:
                by_jid[jid] = row
    address_book = [dict(name=n, phone=p) for n, p, *_ in book
                    if phone_key(p) and phone_key(p) not in known]

    cs = sqlite3.connect(os.path.join(folder, "ChatStorage.sqlite"))
    push = dict(cs.execute("select ZJID, ZPUSHNAME from ZWAPROFILEPUSHNAME").fetchall())
    counts = {pk: (n, mine or 0) for pk, n, mine in cs.execute(
        "select ZCHATSESSION, count(*), sum(ZISFROMME) from ZWAMESSAGE group by ZCHATSESSION")}
    chats = []
    for pk, jid, partner, last in cs.execute(
            "select Z_PK, ZCONTACTJID, ZPARTNERNAME, ZLASTMESSAGEDATE "
            "from ZWACHATSESSION where ZSESSIONTYPE = 0"):
        row = by_jid.get(jid)
        if row:
            continue  # in WhatsApp's address book: already covered above
        phone = "+" + jid.split("@")[0] if jid and jid.endswith("@s.whatsapp.net") else None
        shown = (partner or "").strip("\u202a\u202c\u200e ")
        shown = shown.replace("\u00a0", " ").replace("\u2011", "-")
        if not phone and re.fullmatch(r"\+[\d\s()-]{7,}", shown):
            phone = shown            # privacy (@lid) chats: WhatsApp shows the number as the name
        if not phone or not phone_key(phone) or phone_key(phone) in known:
            continue
        n, mine = counts.get(pk, (0, 0))
        chats.append(dict(phone=phone, shown_as=shown,
                          push_name=push.get(jid) or "", messages=n, from_me=mine,
                          last=dt.date.fromtimestamp(last + APPLE_EPOCH).isoformat() if last else None))
    cs.close()
    chats.sort(key=lambda c: (-c["from_me"], -c["messages"]))
    return address_book, chats
