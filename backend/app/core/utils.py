import re
import unicodedata


def slugify(value: str) -> str:
    """
    Normalises a string into a filesystem-safe slug while PRESERVING non-Latin
    scripts (Hangul, Kana, Cyrillic, Arabic, etc.). Earlier versions stripped
    everything outside ASCII, which made Korean / Japanese / Chinese titles all
    collapse to the same digits-only slug and caused folder collisions.

    Steps:
      - NFC normalisation (composed form — what filesystems and most tools expect).
      - Strip control characters and Latin diacritics ARE NOT removed; they are
        preserved as composed characters (é stays é).
      - Drop punctuation and symbols outside the Unicode "word" class.
      - Collapse whitespace and hyphens into single hyphens.
      - Lowercase only ASCII letters (CJK has no case concept; doing .lower()
        on a Korean string is a no-op).
    """
    value = str(value)
    # Normalise to composed form so a single char is a single codepoint
    value = unicodedata.normalize("NFC", value)
    # Drop control chars (category starts with "C")
    value = "".join(c for c in value if not unicodedata.category(c).startswith("C"))
    # Keep Unicode word chars (letters from any script + digits + underscore),
    # whitespace, and hyphens. Drop everything else (punctuation, symbols).
    value = re.sub(r"[^\w\s-]", "", value, flags=re.UNICODE).strip()
    # Lowercase: only affects Latin / Cyrillic / Greek; CJK ignores it.
    value = value.lower()
    # Collapse runs of whitespace or hyphens into single hyphens
    value = re.sub(r"[-\s]+", "-", value)
    # Trim leading / trailing hyphens that may result from collapse
    value = value.strip("-_")
    # Empty fallback: titles consisting entirely of punctuation / emoji
    return value or "untitled"
