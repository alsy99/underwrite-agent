"""Normalize org / employer strings scraped from free text."""

from __future__ import annotations

import re

_ORG_SUFFIX = r"(?:LLC|L\.?L\.?C\.?|Inc\.?|Incorporated|Corp\.?|Corporation|Ltd\.?|LP|LLP|Co\.?)"
_ROLE_STOP = re.compile(
    r"\s+(?:as|since|from|with|for|at|and|who|whose|which|located|is|was|has|currently)\b.*$",
    re.IGNORECASE,
)
_ORG_CAPTURE = re.compile(
    rf"([A-Z][A-Za-z0-9 &.,'\-]*?\b{_ORG_SUFFIX}\b)",
    re.IGNORECASE,
)
_EMPLOYED_BY = re.compile(
    rf"(?:employed\s+(?:full[- ]time\s+)?by|works\s+at)\s+"
    rf"([A-Z][A-Za-z0-9 &.,'\-]*?\b{_ORG_SUFFIX}\b)",
    re.IGNORECASE,
)
_EMPLOYER_LABEL = re.compile(
    rf"(?:stated\s+)?employer(?:\s*\([^)]*\))?\s*[:\-]\s*"
    rf"([^\n\r]+)",
    re.IGNORECASE,
)
_TRAILING_JUNK = re.compile(r"[\s,;:.\-]+$")
_MAX_ORG_LEN = 80


def clean_org_name(raw: str | None) -> str:
    """Strip role / tenure tails so 'Beta Industries Inc as Senior…' → 'Beta Industries Inc'."""
    if not raw:
        return ""
    text = re.sub(r"\s+", " ", str(raw)).strip()
    text = _ROLE_STOP.sub("", text)
    text = _TRAILING_JUNK.sub("", text)

    # Prefer longest org-suffix match inside the string
    matches = list(_ORG_CAPTURE.finditer(text))
    if matches:
        text = matches[0].group(1).strip()
    text = _TRAILING_JUNK.sub("", text)

    if len(text) > _MAX_ORG_LEN:
        # Hard cut at last space before limit
        cut = text[:_MAX_ORG_LEN].rsplit(" ", 1)[0]
        text = cut or text[:_MAX_ORG_LEN]

    # Reject obvious non-names
    low = text.lower()
    if len(text) < 3:
        return ""
    if low in {"employer", "n/a", "none", "unknown", "tbd"}:
        return ""
    if low.startswith(("as ", "since ", "senior ", "manager ")):
        return ""
    return text


def extract_employer_from_letter(bundle: str) -> str:
    m = _EMPLOYED_BY.search(bundle or "")
    return clean_org_name(m.group(1) if m else "")


def extract_employer_from_label(bundle: str) -> str:
    m = _EMPLOYER_LABEL.search(bundle or "")
    if not m:
        return ""
    # Take first org on the line; drop trailing commentary after suffix.
    line = m.group(1).strip()
    cleaned = clean_org_name(line)
    if cleaned and len(cleaned) >= 3:
        return cleaned
    return ""


def employers_conflict(a: str, b: str) -> bool:
    """True when two employer strings refer to different orgs (not substring noise)."""
    ca, cb = clean_org_name(a), clean_org_name(b)
    if not ca or not cb:
        return False
    la, lb = ca.lower(), cb.lower()
    if la == lb:
        return False
    if la in lb or lb in la:
        # Avoid "A" ⊂ "Beta…" — require substantial overlap
        shorter, longer = (la, lb) if len(la) <= len(lb) else (lb, la)
        if len(shorter) < 5:
            return True
        return False
    return True


def clean_metadata_entities(metadata: dict) -> dict:
    """Return copy with org-like fields cleaned for display / downstream use."""
    out = dict(metadata or {})
    for key in (
        "employer",
        "stated_employer",
        "employer_from_letter",
        "business_name",
        "entity_name",
    ):
        if key in out and out[key]:
            cleaned = clean_org_name(str(out[key]))
            if cleaned:
                out[key] = cleaned
    return out
