import datetime as dt
import sqlite3

from rubrica import mail

ME = "me@example.org"


def build_index(path, messages):
    """A tiny Envelope Index with the columns rubrica reads.

    messages: [(sender, [(type, address, name)], mailbox, flags)] where flags may set
    list_id_hash / unsubscribe_type / automated_conversation.
    """
    con = sqlite3.connect(path)
    con.executescript("""
        create table mailboxes (ROWID integer primary key, url text);
        create table addresses (ROWID integer primary key, address text, comment text);
        create table messages (ROWID integer primary key, global_message_id integer, sender integer,
            date_received integer, mailbox integer, deleted integer default 0,
            list_id_hash integer, unsubscribe_type integer, automated_conversation integer);
        create table recipients (ROWID integer primary key, message integer, address integer,
            type integer, position integer);
        insert into mailboxes values (1, 'imap://x/INBOX'), (2, 'imap://x/Sent'), (3, 'imap://x/Junk');
    """)
    addr_ids = {}

    def addr(a, name=""):
        if a not in addr_ids:
            addr_ids[a] = len(addr_ids) + 1
            con.execute("insert into addresses values (?,?,?)", (addr_ids[a], a, name))
        return addr_ids[a]

    when = int(dt.datetime(2024, 5, 1).timestamp())
    for i, (sender, rcpts, box, flags) in enumerate(messages, 1):
        con.execute("insert into messages values (?,?,?,?,?,0,?,?,?)",
                    (i, 1000 + i, addr(*sender), when + i, box, flags.get("list", 0),
                     flags.get("unsub", 0), flags.get("auto", 0)))
        for pos, (rtype, a, name) in enumerate(rcpts):
            con.execute("insert into recipients (message, address, type, position) values (?,?,?,?)",
                        (i, addr(a, name), rtype, pos))
    con.commit()
    con.close()


def run(tmp_path, messages, known=()):
    db = str(tmp_path / "Envelope Index")
    build_index(db, messages)
    msgs = mail.load(db, dt.datetime(2020, 1, 1), dt.datetime(2030, 1, 1))
    return {r["address"]: r for r in mail.score(msgs, [ME], set(known))}


def test_tiers(tmp_path):
    rows = run(tmp_path, [
        ((ME,), [(0, "anna@example.org", "Anna Rossi")], 2, {}),
        (("anna@example.org", "Anna Rossi"), [(0, ME, "")], 1, {}),
        ((ME,), [(0, "once@example.org", "")], 2, {}),
        (("fan@example.org", "Fan"), [(0, ME, "")], 1, {}),
        (("fan@example.org", "Fan"), [(0, ME, ""), (1, "cc.person@example.org", "Cc Person")], 1, {}),
    ])
    assert rows["anna@example.org"]["tier"] == "A"
    assert rows["anna@example.org"]["name"] == "Anna Rossi"
    assert rows["once@example.org"]["tier"] == "B"
    assert rows["fan@example.org"]["tier"] == "C"
    assert "cc.person@example.org" not in rows          # one Cc is not enough for tier D


def test_bulk_junk_relays_and_known_are_skipped(tmp_path):
    rows = run(tmp_path, [
        (("news@shop.example", "Shop"), [(0, ME, "")], 1, {"list": 1}),
        (("news@shop.example", "Shop"), [(0, ME, "")], 1, {"unsub": 1}),
        (("spam@bad.example", ""), [(0, ME, "")], 3, {}),
        (("spam@bad.example", ""), [(0, ME, "")], 3, {}),
        ((ME,), [(0, "x1-123@sale.craigslist.org", "")], 2, {}),
        ((ME,), [(0, "known@example.org", "Known")], 2, {}),
        ((ME,), [(0, "known@example.org", "Known")], 2, {}),
    ], known={"known@example.org"})
    assert rows == {}


def test_name_guessed_only_from_clear_addresses(tmp_path):
    rows = run(tmp_path, [
        ((ME,), [(0, "mario.bianchi@example.org", "")], 2, {}),
        ((ME,), [(0, "mb1987@example.org", "")], 2, {}),
    ])
    assert rows["mario.bianchi@example.org"]["name"] == "Mario Bianchi"
    assert rows["mario.bianchi@example.org"]["name_guessed"] is True
    assert rows["mb1987@example.org"]["name"] == ""


def test_likely_own_addresses(tmp_path):
    db = str(tmp_path / "Envelope Index")
    msgs = [((ME,), [(0, f"p{i}@example.org", "")], 2, {}) for i in range(6)]
    msgs += [((f"p{i}@example.org",), [(0, ME, "")], 1, {}) for i in range(6)]
    build_index(db, msgs)
    assert mail.likely_own_addresses(db)[0][0] == ME


def test_relay_domains():
    for a in ["x7-123@sale.craigslist.org", "anbieter-1@mail.ebay-kleinanzeigen.de",
              "a1@marketplace.amazon.de", "1-2@property.booking.com"]:
        assert mail.RELAY_DOMAINS.search(a), a
    assert not mail.RELAY_DOMAINS.search("anna@example.org")
