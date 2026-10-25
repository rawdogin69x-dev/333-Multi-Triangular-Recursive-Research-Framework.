"""Step 1 of admission: is the claim anchored in its source? Deterministic and free.

A claim the Distiller cannot back with a verbatim quote is vikalpa: words with no
real object behind them. Numbers in a thesis must also appear in its quotes (the
"casting out nines" cross-check).
"""

from __future__ import annotations

import re
import unicodedata

MIN_QUOTE_CHARS = 20

_QUOTE_MAP = str.maketrans({
    "‘": "'", "’": "'", "‚": "'", "‛": "'",
    "“": '"', "”": '"', "„": '"', "‟": '"',
    "–": "-", "—": "-", "−": "-", " ": " ",
})
_NUMBER = re.compile(r"(?<![\w.])[-+]?\d[\d,]*(?:\.\d+)?%?")


def _normalise_with_map(text: str) -> tuple[str, list[int]]:
    """Normalise for matching and keep, for each output char, its index in the input.

    NFKC (ligatures, full-width forms), straight quotes and dashes, line-break
    hyphenation joined ("extrac-\\ntion" -> "extraction"), whitespace collapsed, casefolded.
    """
    out: list[str] = []
    idx: list[int] = []
    i, n = 0, len(text)
    pending_space = False
    while i < n:
        ch = text[i]
        if ch == "-" and i + 1 < n and text[i + 1] == "\n" and out and out[-1].isalpha():
            i += 2
            while i < n and text[i] in " \t":
                i += 1
            continue
        piece = unicodedata.normalize("NFKC", ch).translate(_QUOTE_MAP).casefold()
        if piece.isspace() or piece == "":
            pending_space = bool(out)
            i += 1
            continue
        if pending_space:
            out.append(" ")
            idx.append(i)
            pending_space = False
        for p in piece:
            out.append(p)
            idx.append(i)
        i += 1
    return "".join(out), idx


def normalise(text: str) -> str:
    return _normalise_with_map(text)[0]


def find_quote(quote: str, raw: str) -> int | None:
    """Offset of `quote` in `raw` (after normalisation), or None if it is not there.

    Quotes shorter than MIN_QUOTE_CHARS are refused: too easy to match by accident.
    """
    q = normalise(quote).strip(" \"'")
    if len(q) < MIN_QUOTE_CHARS:
        return None
    hay, index = _normalise_with_map(raw)
    pos = hay.find(q)
    return None if pos < 0 else index[pos]


def _canon_number(tok: str) -> str:
    tok = tok.replace(",", "").lstrip("+")
    if "." in tok.rstrip("%"):
        head, _, tail = tok.partition(".")
        pct = tail.endswith("%")
        tail = tail.rstrip("%").rstrip("0")
        tok = head + ("." + tail if tail else "") + ("%" if pct else "")
    return tok


def numbers_in(text: str) -> set[str]:
    return {_canon_number(m.group()) for m in _NUMBER.finditer(normalise(text))}


def unsupported_numbers(thesis: str, quotes: list[str]) -> set[str]:
    """Numbers stated in the thesis that appear in none of its quotes."""
    seen: set[str] = set()
    for q in quotes:
        seen |= numbers_in(q)
    return numbers_in(thesis) - seen
