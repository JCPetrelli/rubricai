import json

import pytest

from rubrica import cli, plan
from tests.helpers import card


def test_title_case_ops_skip_email_names_and_keep_acronyms():
    cs = [card("GIULIA MORETTI"), card("Jin Park (JIRA)", first="Jin", last="Ryu (JIRA)"),
          card("x@example.org", first="x@example.org"),
          card("acme tools", company=True, organization="acme tools")]
    ops = {op["_name"]: op["fields"] for op in plan.title_case_ops(cs)}
    assert ops == {"GIULIA MORETTI": {"firstName": "Giulia", "lastName": "Moretti"},
                   "acme tools": {"organization": "Acme Tools"}}


def test_in_card_ops():
    cs = [card("Tom Lee", phones=["0176 12345678", "+49 176 12345678"], note="a\na")]
    ops = plan.in_card_ops(cs)
    assert ops[0]["op"] == "remove_values" and ops[0]["phones"] == ["0176 12345678"]
    assert ops[1]["fields"] == {"note": "a"}


def test_exact_ops_delete_all_but_one():
    cs = [card("Same Person"), card("Same Person"), card("Same Person")]
    assert len(plan.exact_ops(cs)) == 2


def write_contacts(tmp_path, cs):
    path = tmp_path / "contacts.json"
    path.write_text(json.dumps(cs))
    return str(path)


def test_pick_builds_merge_by_name(tmp_path):
    cs = [card("Dad Tim"), card("Dad Dad Work")]
    contacts = write_contacts(tmp_path, cs)
    out = str(tmp_path / "plan.json")
    cli.main(["pick", out, "--contacts", contacts, "--merge", "Dad Tim", "Dad Dad Work"])
    p = plan.load(out)
    assert p["ops"][0]["keep"] == cs[0]["id"] and p["ops"][0]["others"] == [cs[1]["id"]]


def test_pick_refuses_ambiguous_names(tmp_path):
    contacts = write_contacts(tmp_path, [card("Nina"), card("Nina"), card("Nina Neri")])
    with pytest.raises(SystemExit):
        cli.main(["pick", str(tmp_path / "p.json"), "--contacts", contacts, "--merge", "Nina Neri", "Nina"])


def test_apply_without_yes_is_a_dry_run(tmp_path, capsys, monkeypatch):
    out = tmp_path / "p.json"
    plan.save(plan.new("t", [{"op": "delete", "id": "X"}]), out)
    monkeypatch.setattr(cli, "osascript", lambda *a: pytest.fail("must not touch Contacts"))
    cli.main(["apply", str(out)])
    assert "dry run" in capsys.readouterr().out


def test_add_plan_adds_creates_and_skips(tmp_path):
    contacts = write_contacts(tmp_path, [card("Anna Rossi", emails=["old@example.org"]), card("Bo")])
    rows = tmp_path / "rows.json"
    rows.write_text(json.dumps([
        {"address": "anna@work.example", "name": "Anna Rossi"},
        {"address": "bo@example.org", "name": "Bo Lind"},
        {"address": "bo@work.example", "name": "Bo Lind"},
        {"address": "bo2@example.org", "name": "Bo"},
        {"address": "mr87@example.org", "name": ""},
        {"address": "info@acme.example", "name": "Acme Tools", "company": True},
        {"phone": "+44 7700 900123", "name": "Robin Hale"},
    ]))
    out = str(tmp_path / "plan.json")
    cli.main(["add-plan", str(rows), "--contacts", contacts, "--plan", out])
    ops = plan.load(out)["ops"]
    assert [o["op"] for o in ops] == ["add", "create", "create", "create", "create"]
    assert [e["value"] for e in ops[1]["emails"]] == ["bo@example.org", "bo@work.example"]
    assert ops[2]["firstName"] == "Bo" and ops[2]["lastName"] == ""   # one-word name: no attach
    assert ops[3]["company"] and ops[3]["organization"] == "Acme Tools" and ops[3]["firstName"] == ""
    assert ops[4]["phones"][0]["value"] == "+44 7700 900123"


def test_pick_accepts_ids(tmp_path):
    cs = [card("Nina"), card("Nina")]
    contacts = write_contacts(tmp_path, cs)
    out = str(tmp_path / "p.json")
    cli.main(["pick", out, "--contacts", contacts, "--merge", cs[0]["id"], cs[1]["id"]])
    assert plan.load(out)["ops"][0]["others"] == [cs[1]["id"]]


def test_offline_apply_merges_like_apply_js():
    from rubrica import offline
    a = card("Tommaso Ferri", phones=["+49 176 5550606"])
    b = card("Tom cell", phones=["0176 5550606", "+39 320 5550707"], note="Climbing")
    c = card("Paola Benz", phones=["+39 347 0000001"])
    p = {"ops": [{"op": "merge", "keep": a["id"], "others": [b["id"]], "aliases": True},
                 {"op": "set", "id": c["id"], "fields": {"lastName": "Benzoni"}},
                 {"op": "create", "firstName": "Kim", "lastName": "Lee",
                  "emails": [{"label": "home", "value": "kim@example.org"}]}]}
    after = {x["name"]: x for x in offline.apply_plan([a, b, c], p)}
    assert set(after) == {"Tommaso Ferri", "Paola Benzoni", "Kim Lee"}
    t = after["Tommaso Ferri"]
    assert [x["value"] for x in t["phones"]] == ["+49 176 5550606", "+39 320 5550707"]
    assert t["note"] == "Climbing\nAlso saved as: Tom cell"


def test_offline_creates_never_collide_across_runs():
    from rubrica import offline
    create = {"ops": [{"op": "create", "firstName": "A", "lastName": "One"}]}
    first = offline.apply_plan([], create)
    second = offline.apply_plan(first, {"ops": [{"op": "create", "firstName": "B", "lastName": "Two"}]})
    assert len(second) == 2
