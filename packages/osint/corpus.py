"""Entity name normalization and fuzzy matching for OSINT corpus lookups."""

from __future__ import annotations

import re
import unicodedata

_SUFFIX_RE = re.compile(
    r"\b(llc|l\.l\.c\.|inc|inc\.|corp|corp\.|ltd|ltd\.|co|co\.|lp|l\.p\.|pllc)\b",
    re.IGNORECASE,
)
_NON_ALNUM = re.compile(r"[^a-z0-9\s]+")
_WS = re.compile(r"\s+")


def normalize_name(name: str) -> str:
    if not name:
        return ""
    text = unicodedata.normalize("NFKD", name)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = text.lower().strip()
    text = _NON_ALNUM.sub(" ", text)
    text = _SUFFIX_RE.sub(" ", text)
    text = _WS.sub(" ", text).strip()
    return text


def normalize_key(name: str) -> str:
    """Corpus key: keep legal suffix so LLC vs Inc stay distinct."""
    if not name:
        return ""
    text = unicodedata.normalize("NFKD", name)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = text.lower().strip()
    text = _NON_ALNUM.sub(" ", text)
    text = _WS.sub(" ", text).strip()
    return text


def token_set(name: str) -> set[str]:
    return set(normalize_name(name).split()) if name else set()


def similarity(a: str, b: str) -> float:
    """Jaccard similarity on normalized name tokens."""
    ta, tb = token_set(a), token_set(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def find_best_key(query: str, keys: list[str], threshold: float = 0.5) -> str | None:
    if not query:
        return None
    qkey = normalize_key(query)
    if qkey in keys:
        return qkey
    # Substring containment (fixture keys often shorter/longer)
    for k in keys:
        if qkey in k or k in qkey:
            return k
    best_k: str | None = None
    best_s = 0.0
    for k in keys:
        s = similarity(query, k)
        if s > best_s:
            best_s = s
            best_k = k
    if best_k is not None and best_s >= threshold:
        return best_k
    return None


def names_match(a: str, b: str, threshold: float = 0.6) -> bool:
    if not a or not b:
        return False
    na, nb = normalize_key(a), normalize_key(b)
    if na == nb or na in nb or nb in na:
        return True
    return similarity(a, b) >= threshold
