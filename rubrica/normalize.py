"""Matching keys and name helpers shared by every scan.

Everything here is pure: no Contacts.app, no files. That keeps the rules testable.
"""
import re
import unicodedata

# Words people add to a contact name to say *which number* it is, not who it is.
# "Dad Tim" / "Dad Work", "Tom casa" / "Tom cell", "Ines New Num".
DESCRIPTORS = {
    "casa", "home", "cell", "cellulare", "mobile", "handy", "ufficio", "lavoro", "work",
    "office", "buero", "nuovo", "new", "neu", "vecchio", "old", "alt", "num", "numero",
    "number", "fisso", "landline", "tim", "vodafone", "wind", "iliad", "tre", "fastweb",
    "o2", "telekom", "orange", "whatsapp", "wa", "skype", "bis", "2", "ii", "altro", "other",
}
PARTICLES = {"di", "da", "de", "del", "della", "van", "von", "der", "den", "la", "le", "lo", "e"}

_PHONE_KEY_DIGITS = 9


def strip_accents(text):
    return "".join(c for c in unicodedata.normalize("NFD", text or "")
                   if unicodedata.category(c) != "Mn")


def phone_key(value):
    """Last 9 digits: the same number written as 0176…, +49 176… or 0049176… matches.

    Returns None for short codes (USSD, 3-digit services) that must never link cards.
    """
    digits = re.sub(r"\D", "", value or "")
    if len(digits) < 8:
        return None
    return digits[-_PHONE_KEY_DIGITS:]


def email_key(value):
    value = (value or "").strip().lower()
    return value if "@" in value else None


def is_email_name(name):
    return "@" in (name or "")


def name_tokens(name, drop_descriptors=False):
    text = strip_accents(name).lower()
    tokens = [t for t in re.split(r"[^a-z0-9]+", text) if t]
    if drop_descriptors:
        tokens = [t for t in tokens if t not in DESCRIPTORS]
    return tokens


def names_compatible(a, b):
    """Could these two display names belong to the same person?

    True when one is empty or an e-mail address, when they share a token, or when a
    token of one is a prefix (3+ letters) of a token of the other: Tom/Tommaso,
    Rob/Roberto. A shared phone number alone is not enough evidence: households
    share landlines, so "Nora" and "Ivo" on one number stay apart.
    """
    if not a or not b or is_email_name(a) or is_email_name(b):
        return True
    ta = set(name_tokens(a)) - DESCRIPTORS - PARTICLES
    tb = set(name_tokens(b)) - DESCRIPTORS - PARTICLES
    if not ta or not tb or ta & tb:
        return True
    return any(len(x) >= 3 and len(y) >= 3 and (x.startswith(y) or y.startswith(x))
               for x in ta for y in tb)


def is_redundant_alias(alias, primary):
    """'Paola Benz' adds nothing to 'Paola Benzoni'; 'Tom casa' does add context."""
    pt = name_tokens(primary)
    return all(any(p.startswith(t) for p in pt) for t in name_tokens(alias))


def display_name_from_header(name):
    """Mail display names: 'Rossi, Maria' -> 'Maria Rossi'; strip quotes."""
    name = (name or "").strip().strip("\"'").strip()
    if "@" in name:
        return ""
    if name.count(",") == 1:
        last, first = (p.strip() for p in name.split(","))
        if last and first and " " not in last:
            name = f"{first} {last}"
    return name


def name_from_address(address):
    """'mario.rossi@x.it' -> ('Mario', 'Rossi'); anything less clear -> None.

    Only first.last / first_last local parts qualify; never guess from 'mrossi87'.
    """
    local = (address or "").split("@")[0]
    parts = re.split(r"[._]", local)
    if len(parts) != 2 or not all(re.fullmatch(r"[a-zA-Z]{2,}", p) for p in parts):
        return None
    return parts[0].capitalize(), parts[1].capitalize()


# ---------------------------------------------------------------- Title Case

_SEP = r"-'’(/"
_WORD_PART = re.compile(rf"(^|[{_SEP}])([^\W\d_])([^{_SEP}]*)")


def _title_word(word, keep, shouting):
    if word in keep:
        return word
    core = re.sub(r"[^\w&]", "", word)
    if core and core.isupper() and (len(core) <= 3 or len(core) <= 4 and not shouting):
        return word                                          # VE, SMS, B&B, AVIS, (JIRA)
    if "@" in word or re.search(r"\.\w+\.", word) or re.match(r"(www\.|https?:)", word, re.I):
        return word                                          # e-mails and URLs
    if not re.search(r"[^\W\d_]", word):
        return word
    candidate = _WORD_PART.sub(lambda m: m.group(1) + m.group(2).upper() + m.group(3).lower(), word)
    letters = [c for c in word if c.isalpha()]
    if all(c.isupper() for c in letters) or re.match(r"^[A-ZÀ-Þ]{2,}[a-zß-ÿ]", word):
        return candidate                                     # SHOUTING, or RObi
    if all(not c.isupper() or candidate[i].isupper() for i, c in enumerate(word)):
        return candidate                                     # only lower-case to fix
    return word                                              # McLeod, iPhone: deliberate


def title_case(text, keep=(), context=None):
    """Title Case a name field without flattening acronyms or deliberate mixed case.

    context: the whole display name. A field like '(JIRA)' is only treated as shouting
    when the whole name is in capitals.
    """
    if not text:
        return text
    keep = set(keep)
    letters = [c for c in (context or text) if c.isalpha()]
    shouting = bool(letters) and all(c.isupper() for c in letters)
    return " ".join(_title_word(w, keep, shouting) for w in text.split(" "))
