import sqlite3

from rubricai import whatsapp


def build(folder):
    cv = sqlite3.connect(folder / "ContactsV2.sqlite")
    cv.executescript("""
        create table ZWAADDRESSBOOKCONTACT (ZFULLNAME text, ZPHONENUMBER text, ZWHATSAPPID text, ZLID text);
        insert into ZWAADDRESSBOOKCONTACT values
          ('Saved Sam', '+491701111111', '491701111111@s.whatsapp.net', '111@lid'),
          ('Phone Only Pia', '+393332222222', '393332222222@s.whatsapp.net', '222@lid');
    """)
    cv.close()
    cs = sqlite3.connect(folder / "ChatStorage.sqlite")
    cs.executescript("""
        create table ZWACHATSESSION (Z_PK integer, ZCONTACTJID text, ZPARTNERNAME text,
                                     ZLASTMESSAGEDATE real, ZSESSIONTYPE integer);
        create table ZWAPROFILEPUSHNAME (ZJID text, ZPUSHNAME text);
        create table ZWAMESSAGE (ZCHATSESSION integer, ZISFROMME integer);
        insert into ZWACHATSESSION values
          (1, '491701111111@s.whatsapp.net', 'Saved Sam', 800000000, 0),
          (2, '447700900123@s.whatsapp.net', '+44 7700 900123', 800000000, 0),
          (3, '999@lid', '+48' || char(160) || '600' || char(160) || '000' || char(160) || '111', 800000000, 0),
          (4, 'group@g.us', 'Book club', 800000000, 1);
        insert into ZWAPROFILEPUSHNAME values ('447700900123@s.whatsapp.net', 'Robin');
        insert into ZWAMESSAGE values (2, 1), (2, 0), (3, 0);
    """)
    cs.close()


def test_missing(tmp_path):
    build(tmp_path)
    book, chats = whatsapp.missing(str(tmp_path), known_phones=["0170 1111111"])
    assert [b["name"] for b in book] == ["Phone Only Pia"]
    phones = {c["phone"]: c for c in chats}
    assert phones["+447700900123"]["push_name"] == "Robin"
    assert phones["+447700900123"]["from_me"] == 1
    assert "+48 600 000 111" in phones                  # @lid chat: number taken from the title
    assert all("491701111111" not in p for p in phones)  # saved contact is not reported
