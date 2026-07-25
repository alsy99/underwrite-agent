"""Post-process case-file findings for memo / underwriter readability."""

from __future__ import annotations

import re
from collections import defaultdict

from packages.schemas.case import (
    Contradiction,
    Finding,
    PolicyFinding,
    RecommendedAction,
)

_SEVERITY_RANK = {"high": 0, "medium": 1, "low": 2, "info": 3}
_MAX_FINDINGS = 12
_MAX_OPEN_QUESTIONS = 6
_POLICY_PASTE_HINTS = (
    "must match",
    "are treated as",
    "policy requires",
    "underwriting guideline",
    "this policy",
)


def severity_rank(severity: str) -> int:
    return _SEVERITY_RANK.get((severity or "").lower(), 9)


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def _finding_dedupe_key(f: Finding) -> tuple[str, str]:
    title = _norm(f.title)
    title = re.sub(r"^policy\s+", "policy ", title)
    desc = _norm(f.description)[:180]
    return (title, desc)


def _impact_score(f: Finding) -> int:
    """Lower = higher impact within same severity."""
    title = (f.title or "").lower()
    desc = (f.description or "").lower()
    score = 50
    if "contradiction" in title:
        score -= 20
    if title.startswith("policy") or "policy" in title:
        score -= 15
    if "employer" in title or "employer" in desc:
        score -= 10
    if "sanctions" in title or "ofac" in desc:
        score -= 12
    if "revenue" in desc or "deposit" in desc or "income" in desc:
        score -= 8
    if "osint" in title:
        score -= 5
    score += min(len(f.description or "") // 80, 5)
    return score


def dedupe_findings(findings: list[Finding]) -> list[Finding]:
    """Keep one finding per (title, description); prefer higher severity / impact."""
    best: dict[tuple[str, str], Finding] = {}
    for f in findings:
        key = _finding_dedupe_key(f)
        prev = best.get(key)
        if prev is None:
            best[key] = f
            continue
        if severity_rank(f.severity) < severity_rank(prev.severity):
            best[key] = f
        elif severity_rank(f.severity) == severity_rank(prev.severity):
            if _impact_score(f) < _impact_score(prev):
                best[key] = f
    return list(best.values())


def merge_similar_findings(findings: list[Finding]) -> list[Finding]:
    """Merge findings that share the same title (e.g. repeated Policy RULE)."""
    groups: dict[str, list[Finding]] = defaultdict(list)
    for f in findings:
        groups[_norm(f.title)].append(f)

    merged: list[Finding] = []
    for _title, group in groups.items():
        if len(group) == 1:
            merged.append(group[0])
            continue
        group_sorted = sorted(
            group, key=lambda x: (severity_rank(x.severity), _impact_score(x))
        )
        primary = group_sorted[0]
        extras: list[str] = []
        seen_desc = {_norm(primary.description)}
        for other in group_sorted[1:]:
            d = _norm(other.description)
            if d in seen_desc:
                continue
            seen_desc.add(d)
            extras.append(other.description.strip())
        if extras:
            extra_txt = "; ".join(extras[:2])
            desc = f"{primary.description.rstrip('.')} (also: {extra_txt})"
            primary = primary.model_copy(update={"description": desc[:500]})
        merged.append(primary)
    return merged


def rank_findings(findings: list[Finding], *, limit: int = _MAX_FINDINGS) -> list[Finding]:
    ordered = sorted(
        findings,
        key=lambda f: (severity_rank(f.severity), _impact_score(f), f.id),
    )
    out: list[Finding] = []
    for i, f in enumerate(ordered[:limit], start=1):
        out.append(f.model_copy(update={"id": f"finding_{i}"}))
    return out


def polish_findings(findings: list[Finding]) -> list[Finding]:
    return rank_findings(merge_similar_findings(dedupe_findings(findings)))


def _looks_like_policy_paste(excerpt: str) -> bool:
    text = excerpt or ""
    if len(text) > 220:
        return True
    low = text.lower()
    return any(h in low for h in _POLICY_PASTE_HINTS) and len(text) > 120


def policy_finding_description(
    p: PolicyFinding, contradictions: list[Contradiction]
) -> str:
    """Specific failure statement instead of raw policy text dump."""
    status = (p.status or "review").upper()
    excerpt = (p.excerpt or "").strip()

    related: Contradiction | None = None
    for c in contradictions:
        blob = f"{c.claim_a} {c.claim_b} {c.quoted_evidence}".lower()
        rule = (p.rule_ref or "").lower()
        excerpt_l = excerpt.lower()
        if "employer" in rule or "emp" in rule or "employer" in excerpt_l:
            if "employer" in blob:
                related = c
                break
        if any(k in rule or k in excerpt_l for k in ("income", "revenue", "deposit")):
            if any(k in blob for k in ("income", "revenue", "deposit")):
                related = c
                break
    if related is None:
        for c in contradictions:
            if c.severity == "high":
                related = c
                break

    if related:
        return f"{status}: evidence conflict — {related.claim_a} vs {related.claim_b}."

    if excerpt and not _looks_like_policy_paste(excerpt):
        return f"{status}: {excerpt}"

    return (
        f"{status} on {p.rule_ref}: documentation does not satisfy the cited control; "
        "see contradictions and source docs for magnitude."
    )


def _money_hint(text: str) -> str | None:
    m = re.search(r"\$[\d,]+(?:\.\d+)?(?:\s*[kKmMbB])?", text or "")
    return m.group(0) if m else None


def build_open_questions(
    *,
    contradictions: list[Contradiction],
    policy_findings: list[PolicyFinding],
    existing: list[str],
    action: RecommendedAction,
    metadata: dict | None = None,
) -> list[str]:
    meta = metadata or {}
    questions: list[str] = []

    stated = meta.get("stated_employer") or meta.get("employer")
    letter = meta.get("employer_from_letter")
    if stated and letter and _norm(str(stated)) != _norm(str(letter)):
        questions.append(
            f"Please provide a written explanation for the employer name discrepancy "
            f"between the application ({stated}) and the employment letter ({letter})."
        )

    for c in contradictions:
        blob = f"{c.claim_a} {c.claim_b} {c.quoted_evidence}"
        low = blob.lower()
        if "employer" in low and not any(
            "employer name discrepancy" in q.lower() for q in questions
        ):
            questions.append(
                "Please provide a written explanation for the employer name discrepancy "
                f"between the application ({c.claim_a}) and the employment letter ({c.claim_b})."
            )
        if any(k in low for k in ("deposit", "revenue", "income", "bank")):
            amt = _money_hint(blob)
            revenue = (
                meta.get("annual_revenue")
                or meta.get("gross_revenue")
                or meta.get("stated_revenue")
            )
            if revenue:
                rev = str(revenue)
                rev_txt = rev if rev.startswith("$") else f"${rev}"
                questions.append(
                    "Provide bank statements or other support reconciling the irregular "
                    f"large deposits against the stated {rev_txt} annual revenue."
                )
            elif amt:
                questions.append(
                    "Provide bank statements or other support reconciling the irregular "
                    f"large deposits (including {amt}) against stated income/revenue."
                )
            else:
                questions.append(
                    "Provide bank statements or other support reconciling irregular large "
                    "deposits against stated income/revenue."
                )

    for p in policy_findings:
        if p.status == "fail":
            questions.append(
                f"Remediate or explain failure of policy control {p.rule_ref} "
                "before credit committee."
            )

    for q in existing:
        qn = _norm(q)
        if any(qn == _norm(x) or qn in _norm(x) or _norm(x) in qn for x in questions):
            continue
        if qn.startswith("reconcile employer") and any(
            "employer" in _norm(x) for x in questions
        ):
            continue
        if qn.startswith("confirm employer and revenue"):
            continue
        questions.append(q)

    if action == RecommendedAction.DECLINE and not questions:
        questions = [
            "Escalate to senior underwriter before final adverse action.",
            "Request borrower letter of explanation for material contradictions.",
        ]
    if action == RecommendedAction.REVIEW and not questions:
        questions = [
            "Confirm employer and revenue documentation with primary sources.",
            "Validate business address is not a virtual office.",
        ]

    seen: set[str] = set()
    out: list[str] = []
    for q in questions:
        key = _norm(q)
        if key in seen:
            continue
        seen.add(key)
        out.append(q.strip())
        if len(out) >= _MAX_OPEN_QUESTIONS:
            break
    return out


def synthesize_executive_summary(
    *,
    vertical: str,
    action: RecommendedAction,
    findings: list[Finding],
    contradictions: list[Contradiction],
    policy_findings: list[PolicyFinding],
    entity_profiles: list,
    llm_text: str | None = None,
) -> str:
    """3–5 sentence professional prose; LLM text used only if already clean short prose."""
    cleaned_llm = _usable_llm_summary(llm_text)
    if cleaned_llm:
        return cleaned_llm

    action_word = action.value
    high = [f for f in findings if f.severity == "high"]
    medium = [f for f in findings if f.severity == "medium"]
    policy_fails = [p for p in policy_findings if p.status == "fail"]
    flagged = [
        p
        for p in entity_profiles
        if getattr(p, "status", None) in ("flagged", "mismatch")
    ]

    sentences: list[str] = [
        f"Investigation of this {vertical.replace('_', ' ')} package is complete with a "
        f"recommended action of {action_word}."
    ]

    if contradictions:
        top = contradictions[0]
        sentences.append(
            f"Material cross-document conflict identified: {top.claim_a} versus {top.claim_b}."
        )
    elif high:
        sentences.append(f"Primary concern: {high[0].description.rstrip('.')}.")

    if policy_fails:
        refs = ", ".join(p.rule_ref for p in policy_fails[:3])
        sentences.append(
            f"Policy review flagged {len(policy_fails)} control failure(s) ({refs})."
        )
    elif any(p.status == "review" for p in policy_findings):
        sentences.append(
            "One or more policy controls require underwriter review before decision."
        )

    if flagged:
        names = ", ".join(getattr(p, "entity_name", "?") for p in flagged[:3])
        sentences.append(
            f"OSINT profiling raised identity or risk concerns for: {names}."
        )

    risk_bits = []
    if high:
        risk_bits.append(f"{len(high)} high-severity finding(s)")
    if medium:
        risk_bits.append(f"{len(medium)} medium-severity finding(s)")
    if risk_bits:
        sentences.append(
            "Overall risk posture reflects "
            + " and ".join(risk_bits)
            + "; see ranked findings below."
        )
    else:
        sentences.append(
            "No high- or medium-severity findings were retained after consolidation."
        )

    return " ".join(sentences[:5])


def _usable_llm_summary(text: str | None) -> str | None:
    if not text:
        return None
    raw = text.strip()
    if raw.startswith("{") or raw.startswith("["):
        return None
    raw = re.sub(r"^#+\s*.*\n", "", raw).strip()
    if len(raw) < 40:
        return None
    sentences = re.split(r"(?<=[.!?])\s+", raw)
    sentences = [s.strip() for s in sentences if s.strip()]
    if len(sentences) > 6:
        raw = " ".join(sentences[:5])
    if len(raw) > 900:
        raw = " ".join(sentences[:4])
    if raw.count("\n-") >= 3 or raw.count("\n*") >= 3:
        return None
    return raw
