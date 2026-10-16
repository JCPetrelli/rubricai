from rubrica import dedupe
from tests.helpers import card, names


def test_exact_copies_keep_one_and_ignore_near_copies():
    a = card("Anna Rossi", phones=["+39 333 1111111"], modified="2020-01-01T00:00:00Z")
    b = card("Anna Rossi", phones=["+39 333 1111111"], modified="2024-01-01T00:00:00Z")
    c = card("Anna Rossi", phones=["+39 333 1111111"], note="met in Turin")
    groups = dedupe.exact_copies([a, b, c])
    assert len(groups) == 1 and len(groups[0]) == 2
    assert groups[0][0] is b                       # newest survives


def test_exact_copies_prefer_card_with_photo():
    a = card("Bo Lind", has_image=True, modified="2019-01-01T00:00:00Z")
    b = card("Bo Lind", has_image=False, modified="2024-01-01T00:00:00Z")
    assert dedupe.exact_copies([a, b])[0][0] is a


def test_same_name_one_word_without_shared_key_is_ambiguous():
    merge, ambiguous = dedupe.same_name_groups([
        card("Nina", phones=["+39 340 0000001"]), card("Nina", phones=["+39 340 0000002"]),
        card("Marco Neri", phones=["+39 340 0000003"]), card("Marco Neri", emails=["mn@example.org"]),
    ])
    assert names(merge) == [["Marco Neri", "Marco Neri"]]
    assert names(ambiguous) == [["Nina", "Nina"]]


def test_linked_merges_compatible_names_and_reviews_households():
    cs = [
        card("Roberto Landi", phones=["+39 347 1234567"]),
        card("Rob landi", phones=["347 1234567"]),
        card("Nora (vet)", phones=["0423 123456"]),
        card("Ivo (judo)", phones=["0423 123456"]),
    ]
    merge, review, chains = dedupe.linked_groups(cs)
    assert names(merge) == [["Roberto Landi", "Rob landi"]]
    assert [(a["name"], b["name"]) for a, b, _ in review] == [("Nora (vet)", "Ivo (judo)")]
    assert chains == []


def test_corrupted_card_with_many_strangers_goes_to_review():
    junk = card("Acme Inc.", company=True, emails=[f"p{i}@example.org" for i in range(6)])
    people = [card(f"Person {i}", emails=[f"p{i}@example.org"]) for i in range(6)]
    merge, review, chains = dedupe.linked_groups([junk, *people])
    assert merge == [] and len(review) == 6


def test_chain_through_an_email_named_card_is_flagged():
    # an e-mail-named card is compatible with any name, so it can bridge two strangers
    acme = card("Acme Inc.", company=True, emails=["omar@example.org"])
    bridge = card("omar@example.org", first="omar@example.org", emails=["omar@example.org"])
    omar = card("Omar Lanza", emails=["omar@example.org"])
    merge, review, chains = dedupe.linked_groups([acme, bridge, omar])
    assert merge == []
    assert sorted(c["name"] for c in chains[0]) == ["Acme Inc.", "Omar Lanza", "omar@example.org"]


def test_shared_key_used_by_many_cards_links_nothing():
    switchboard = "+49 30 1234 5678"
    cs = [card(f"Desk {n}", phones=[switchboard]) for n in "ABCDEF"]
    merge, review, chains = dedupe.linked_groups(cs)
    assert merge == [] and review == [] and chains == []


def test_primary_prefers_real_name_over_nickname_or_email():
    group = dedupe.order_group([card("Marco (cello)", first="Marco", last="(cello)"),
                                card("Marco Neri"), card("marco@example.org", first="marco@example.org")])
    assert group[0]["name"] == "Marco Neri"


def test_name_only_pairs():
    cs = [
        card("Dad Tim", phones=["+39 335 0000001"]),
        card("Dad Dad Work", phones=["+39 320 0000002"]),
        card("Gio Casa", phones=["0423 000003"]),
        card( "Gio", phones=["+39 338 0000004"]),
        card("Gabri Gallo", phones=["+39 346 0000005"]),
        card("Gabriella Gallo"),
        card("Adriàn Ruiz", phones=["0163 0000006"]),
        card("Adrián Ruiz", emails=["hr@example.org"]),
        card("ann_bell@example.org", first="ann_bell@example.org", emails=["ann_bell@example.org"]),
        card("Ann Bell", phones=["+44 7700 900007"]),
        card("Paolo 2", phones=["+39 333 0000008"]),
        card("Paolo Neri", phones=["+39 333 0000009"]),
    ]
    found = {frozenset((a["name"], b["name"])) for a, b, _ in dedupe.name_only_pairs(cs)}
    assert frozenset(("Dad Tim", "Dad Dad Work")) in found
    assert frozenset(("Gio Casa",  "Gio")) in found
    assert frozenset(("Gabri Gallo", "Gabriella Gallo")) in found
    assert frozenset(("Adriàn Ruiz", "Adrián Ruiz")) in found
    assert frozenset(("ann_bell@example.org", "Ann Bell")) in found
    assert frozenset(("Paolo 2", "Paolo Neri")) not in found


def test_in_card_duplicates_keep_international_format():
    c = card("Mira Novak", phones=["0176 12345678", "+49 176 12345678"],
             emails=["Mira@Example.org", "mira@example.org"],
             addresses=["Via Roma 1, Asolo", "Via Roma 1 Asolo", "Main St 2, Leeds"])
    drop = dedupe.in_card_duplicates(c)
    assert drop["phones"] == ["0176 12345678"]
    assert drop["emails"] == ["Mira@Example.org"]
    assert len(drop["addresses"]) == 1


def test_in_card_exact_repeat_is_removed_once():
    c = card("Rep", emails=["a@example.org", "a@example.org", "a@example.org"])
    assert dedupe.in_card_duplicates(c)["emails"] == ["a@example.org", "a@example.org"]


def test_repeated_note_lines():
    assert dedupe.repeated_note_lines("Host\nOrganizer\n\nHost") == ["Host", "Organizer"]
    assert dedupe.repeated_note_lines("one\ntwo") is None
