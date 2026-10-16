import pytest

from rubricai.normalize import (display_name_from_header, is_redundant_alias,
                                   name_from_address, names_compatible, phone_key, title_case)


@pytest.mark.parametrize("a,b", [
    ("+49 176 1234 5678", "0176 12345678"),
    ("0039 333 123 4567", "333 1234567"),
    ("+39 (333) 123-4567", "+393331234567"),
])
def test_phone_key_matches_formats(a, b):
    assert phone_key(a) == phone_key(b)


@pytest.mark.parametrize("short", ["*101#", "22922", "", None, "112"])
def test_phone_key_ignores_short_codes(short):
    assert phone_key(short) is None


@pytest.mark.parametrize("a,b,ok", [
    ("Rob landi", "Roberto Landi", True),
    ("Tom casa", "Tommaso Ferri", True),
    ("Nora (vet)", "Ivo (judo)", False),
    ("anna@example.org", "Anna Rossi", True),
    ("Pepe", "Giuseppe Lorenzi", False),
    ("", "Anyone", True),
])
def test_names_compatible(a, b, ok):
    assert names_compatible(a, b) is ok


def test_redundant_alias():
    assert is_redundant_alias("Paola Benz", "Paola Benzoni")
    assert not is_redundant_alias("Tom casa", "Tommaso Ferri")


@pytest.mark.parametrize("raw,expected", [
    ("GIULIA MORETTI", "Giulia Moretti"),
    ("elena fabbri", "Elena Fabbri"),
    ("Paolo Di stefano", "Paolo Di Stefano"),
    ("Luca Rinaldi (VE)", "Luca Rinaldi (VE)"),
    ("Gateway nuovo SMS", "Gateway Nuovo SMS"),
    ("Napoli B&B", "Napoli B&B"),
    ("Greta McLeod", "Greta McLeod"),
    ("RObi Galli", "Robi Galli"),
    ("sara.conti", "Sara.conti"),
    ("Marta (blablacar.it Verona-milano)", "Marta (Blablacar.it Verona-Milano)"),
    ("anna d'angelo", "Anna D'Angelo"),
])
def test_title_case(raw, expected):
    assert title_case(raw) == expected


def test_title_case_acronym_needs_context():
    assert title_case("(JIRA)", context="Jin Park (JIRA)") == "(JIRA)"
    assert title_case("OMAR", context="OMAR") == "Omar"


def test_display_name_from_header():
    assert display_name_from_header("Rossi, Maria") == "Maria Rossi"
    assert display_name_from_header('"Studio Bianchi"') == "Studio Bianchi"
    assert display_name_from_header("maria@example.org") == ""


def test_name_from_address_is_conservative():
    assert name_from_address("mario.rossi@example.org") == ("Mario", "Rossi")
    assert name_from_address("anna_neri@example.org") == ("Anna", "Neri")
    assert name_from_address("mrossi87@example.org") is None
    assert name_from_address("info@example.org") is None
