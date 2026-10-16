"""Build the demo data used in the README: an invented address book, a tiny Apple Mail
index and a tiny WhatsApp Desktop store. Every person here is made up.

    python3 examples/make_demo.py        # writes examples/demo/
"""
import datetime as dt
import json
import os
import sqlite3

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "demo")
ME = "you@example.org"
cards = []


def card(name, first=None, last=None, phones=(), emails=(), note="", company=False,
         organization="", addresses=(), modified="2024-01-01T00:00:00Z"):
    if first is None and not company:
        first, _, last = name.partition(" ")
    cards.append(dict(
        id=f"DEMO-{len(cards) + 1:02d}", name=name, first=first or "", middle="", last=last or "",
        nickname="", company=company, organization=organization, job="", note=note,
        birthday=None, modified=modified,
        phones=[{"label": "mobile", "value": p} for p in phones],
        emails=[{"label": "home", "value": e} for e in emails], urls=[],
        addresses=[{"label": "home", "formatted": a} for a in addresses]))


def address_book():
    # exact copies: the same card imported three times
    for _ in range(3):
        card("Laura Bianchi", phones=["+39 347 555 0101"], emails=["laura.bianchi@example.org"])
    # same name, different details
    card("Marco Neri", phones=["+39 333 555 0202"])
    card("Marco Neri", emails=["marco.neri@example.org"], note="Choir, tenor")
    # one-word name, nothing shared: probably two people
    card("Nina", phones=["+39 340 555 0303"])
    card("Nina", phones=["+49 151 555 0404"])
    # linked by a phone number, names compatible
    card("Roberto Landi", phones=["+39 348 555 0505"], emails=["roberto.landi@example.org"])
    card("Rob landi", phones=["348 555 0505"])
    card("Tommaso Ferri", phones=["+49 176 555 0606"], emails=["tommaso@example.org"])
    card("Tom cell", phones=["0176 555 0606", "+39 320 555 0707"])
    card("Tom casa", phones=["+39 0423 555 0808", "+39 320 555 0707"])
    # one landline, two people
    card("Nora (vet)", phones=["+39 0423 555 0909"])
    card("Ivo (judo)", phones=["+39 0423 555 0909"])
    # a corrupted company card holding strangers' e-mails
    card("Acme Tools", company=True, organization="Acme Tools", first="", last="",
         emails=["sales@acme.example", "omar@example.org", "gloria@example.org"])
    card("omar@example.org", first="omar@example.org", last="", emails=["omar@example.org"])
    card("Omar Lanza", phones=["+39 335 555 1010"], emails=["omar@example.org"])
    card("Gloria Sala", emails=["gloria@example.org"])
    # same person, nothing shared but the name
    card("Dad Tim", phones=["+39 335 555 1111"])
    card("Dad Dad Work", phones=["+39 320 555 1212"])
    card("Gio Casa", phones=["+39 0423 555 1313"])
    card("Gio", phones=["+39 338 555 1414"])
    card("Gabri Gallo", phones=["+39 346 555 1515"])
    card("Gabriella Gallo", emails=["gabriella.gallo@example.org"])
    card("Adriàn Ruiz", phones=["+34 600 555 1616"])
    card("Adrián Ruiz", emails=["adrian.ruiz@example.org"])
    card("ann_bell@example.org", first="ann_bell@example.org", last="", emails=["ann_bell@example.org"])
    card("Ann Bell", phones=["+44 7700 900 171"])
    card("Paolo 2", phones=["+39 333 555 1818"])
    card("Paolo Rinaldi", phones=["+39 333 555 1919"])
    # values stored twice inside one card
    card("Mira Novak", phones=["0176 55520202", "+49 176 55520202"],
         emails=["Mira.Novak@example.org", "mira.novak@example.org"],
         addresses=["Via Roma 1, 31011 Asolo", "Via Roma 1 31011 Asolo"])
    card("Ines Kraus", phones=["+49 30 555 2121"], note="Piano teacher\nPiano teacher\nTuesdays")
    # capitalisation
    card("GIULIA MORETTI", phones=["+39 349 555 2222"])
    card("elena fabbri", emails=["elena.fabbri@example.org"])
    card("Luca Rinaldi (VE)", phones=["+39 041 555 2323"])
    card("Paolo Di stefano", phones=["+39 339 555 2424"])
    card("Greta McLeod", emails=["greta@example.org"])
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "contacts.json"), "w", encoding="utf-8") as f:
        json.dump(cards, f, ensure_ascii=False, indent=1)


def mail_index():
    path = os.path.join(OUT, "Envelope Index")
    if os.path.exists(path):
        os.remove(path)
    con = sqlite3.connect(path)
    con.executescript("""
        create table mailboxes (ROWID integer primary key, url text);
        create table addresses (ROWID integer primary key, address text, comment text);
        create table messages (ROWID integer primary key, global_message_id integer, sender integer,
            date_received integer, mailbox integer, deleted integer default 0,
            list_id_hash integer, unsubscribe_type integer, automated_conversation integer);
        create table recipients (ROWID integer primary key, message integer, address integer,
            type integer, position integer);
        insert into mailboxes values (1, 'imap://demo/INBOX'), (2, 'imap://demo/Sent');
    """)
    ids = {}

    def addr(a, name=""):
        if a not in ids:
            ids[a] = len(ids) + 1
            con.execute("insert into addresses values (?,?,?)", (ids[a], a, name))
        return ids[a]

    t = int(dt.datetime(2025, 3, 1).timestamp())
    msgs = []
    for _ in range(4):   # two-way correspondence
        msgs += [((ME, ""), [(0, "s.weber@studio.example", "Weber, Sabine")], 2, {}),
                 (("s.weber@studio.example", "Weber, Sabine"), [(0, ME, "")], 1, {})]
    msgs += [((ME, ""), [(0, "hausverwaltung@flat.example", "Hausverwaltung Nord")], 2, {})] * 3
    msgs += [((ME, ""), [(0, "pietro.costa@example.org", "")], 2, {})]          # wrote once, no name
    msgs += [(("kim.lee@example.org", "Kim Lee"), [(0, ME, "")], 1, {})] * 2     # wrote to you twice
    msgs += [(("organiser@club.example", "Club"), [(0, ME, ""), (1, "dora.fux@example.org", "Dora Fux")], 1, {})] * 3
    msgs += [(("news@shop.example", "Shop News"), [(0, ME, "")], 1, {"list": 1})] * 5
    msgs += [((ME, ""), [(0, "x7k2-4412@sale.craigslist.org", "")], 2, {})] * 2
    msgs += [((ME, ""), [(0, "laura.bianchi@example.org", "Laura Bianchi")], 2, {})]  # already saved
    for i, (sender, rcpts, box, flags) in enumerate(msgs, 1):
        con.execute("insert into messages values (?,?,?,?,?,0,?,?,?)",
                    (i, 9000 + i, addr(*sender), t + i * 3600, box, flags.get("list", 0), 0, 0))
        for pos, (rtype, a, name) in enumerate(rcpts):
            con.execute("insert into recipients (message, address, type, position) values (?,?,?,?)",
                        (i, addr(a, name), rtype, pos))
    con.commit()
    con.close()


def whatsapp_store():
    folder = os.path.join(OUT, "whatsapp")
    os.makedirs(folder, exist_ok=True)
    for name in ("ContactsV2.sqlite", "ChatStorage.sqlite"):
        if os.path.exists(os.path.join(folder, name)):
            os.remove(os.path.join(folder, name))
    cv = sqlite3.connect(os.path.join(folder, "ContactsV2.sqlite"))
    cv.executescript("""
        create table ZWAADDRESSBOOKCONTACT (ZFULLNAME text, ZPHONENUMBER text, ZWHATSAPPID text, ZLID text);
        insert into ZWAADDRESSBOOKCONTACT values
          ('Roberto Landi', '+393485550505', '393485550505@s.whatsapp.net', '1@lid'),
          ('Yara (Swimming)', '+491525552525', '491525552525@s.whatsapp.net', '2@lid');
    """)
    cv.close()
    cs = sqlite3.connect(os.path.join(folder, "ChatStorage.sqlite"))
    cs.executescript("""
        create table ZWACHATSESSION (Z_PK integer, ZCONTACTJID text, ZPARTNERNAME text,
                                     ZLASTMESSAGEDATE real, ZSESSIONTYPE integer);
        create table ZWAPROFILEPUSHNAME (ZJID text, ZPUSHNAME text);
        create table ZWAMESSAGE (ZCHATSESSION integer, ZISFROMME integer);
        insert into ZWACHATSESSION values
          (1, '393485550505@s.whatsapp.net', 'Roberto Landi', 780000000, 0),
          (2, '393295552626@s.whatsapp.net', '+39 329 555 2626', 781000000, 0),
          (3, '447700900272@s.whatsapp.net', '+44 7700 900272', 782000000, 0);
        insert into ZWAPROFILEPUSHNAME values ('393295552626@s.whatsapp.net', 'Foto Ottica Sole');
        insert into ZWAMESSAGE values (2, 1), (2, 0), (2, 0), (3, 0);
    """)
    cs.close()


if __name__ == "__main__":
    address_book()
    mail_index()
    whatsapp_store()
    print(f"{len(cards)} demo cards, a mail index and a WhatsApp store -> {OUT}")
