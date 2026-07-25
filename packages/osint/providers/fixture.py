"""Deterministic fixture corpus loader for OSINT demos."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from packages.config import get_settings
from packages.osint.corpus import find_best_key, names_match, normalize_key
from packages.osint.providers.base import ProviderResult, ok_result


def _fixture_root() -> Path:
    settings = get_settings()
    root = Path(settings.osint_fixture_dir)
    if not root.is_absolute():
        candidates = [
            Path.cwd() / root,
            Path(__file__).resolve().parents[3] / root,
        ]
        for c in candidates:
            if c.is_dir():
                return c
        return candidates[0]
    return root


@lru_cache(maxsize=16)
def _load_json(name: str) -> dict[str, Any]:
    path = _fixture_root() / name
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, dict) else {}


def clear_fixture_cache() -> None:
    _load_json.cache_clear()


def _lookup(corpus: dict[str, Any], entity: str) -> tuple[str | None, Any]:
    key = find_best_key(entity, list(corpus.keys()))
    if key is None:
        return None, None
    return key, corpus[key]


def _employer_match(employer: str, stated: str, corpus: dict[str, Any]) -> bool:
    """True when employer and stated employer refer to same entity."""
    if names_match(employer, stated):
        return True
    emp_key = find_best_key(employer, list(corpus.keys()))
    stated_key = find_best_key(stated, list(corpus.keys()))
    if emp_key and stated_key and emp_key == stated_key:
        return True
    if emp_key:
        row = corpus[emp_key]
        mismatches = {normalize_key(m) for m in row.get("mismatches_with", [])}
        if stated_key and stated_key in mismatches:
            return False
        aliases = row.get("stated_aliases", [])
        if any(names_match(stated, a) for a in aliases):
            return True
    if stated_key:
        other = corpus[stated_key]
        mismatches = {normalize_key(m) for m in other.get("mismatches_with", [])}
        if emp_key and emp_key in mismatches:
            return False
    return False


class FixtureProvider:
    source = "fixture_corpus"

    def lookup_registry(self, entity_name: str, ein: str = "") -> ProviderResult:
        corpus = _load_json("registry.json")
        key, row = _lookup(corpus, entity_name)
        if row is None:
            return ok_result(
                self.source,
                "fixture",
                {
                    "entity_name": entity_name,
                    "status": "not_found",
                    "ein": ein or None,
                    "note": "No registry match in fixture corpus",
                },
            )
        data = {**row, "ein": ein or None, "matched_key": key}
        return ok_result(self.source, "fixture", data)

    def verify_employer(
        self, employer: str, stated_employer: str = "", profile_url: str = ""
    ) -> ProviderResult:
        corpus = _load_json("employers.json")
        stated = stated_employer or employer
        key, row = _lookup(corpus, employer)
        match = _employer_match(employer, stated, corpus)

        if row is None:
            return ok_result(
                self.source,
                "fixture",
                {
                    "employer": employer,
                    "stated_employer": stated,
                    "profile_url": profile_url or "",
                    "match": match,
                    "confidence": 0.55 if match else 0.15,
                    "note": "Employer not in fixture corpus — name heuristic only",
                },
            )

        return ok_result(
            self.source,
            "fixture",
            {
                "employer": row.get("employer", employer),
                "stated_employer": stated,
                "profile_url": profile_url or row.get("profile_url", ""),
                "match": match,
                "confidence": 0.9 if match else 0.2,
                "web_presence": row.get("web_presence"),
                "industry": row.get("industry"),
                "employee_count_band": row.get("employee_count_band"),
                "matched_key": key,
            },
        )

    def web_presence(self, entity_name: str, domain: str = "") -> ProviderResult:
        corpus = _load_json("web.json")
        key, row = _lookup(corpus, entity_name)
        if row is None and domain:
            for k, v in corpus.items():
                if domain.lower() in str(v.get("domain", "")).lower():
                    key, row = k, v
                    break
        if row is None:
            return ok_result(
                self.source,
                "fixture",
                {
                    "entity_name": entity_name,
                    "domain": domain or None,
                    "site_live": False,
                    "note": "No web presence record in fixture corpus",
                },
            )
        return ok_result(self.source, "fixture", {**row, "matched_key": key})

    def check_sanctions(self, name: str) -> ProviderResult:
        corpus = _load_json("sanctions.json")
        hits = corpus.get("hits", {}) if isinstance(corpus.get("hits"), dict) else {}
        clear_list = corpus.get("clear_entities", [])
        clear = {normalize_key(x) for x in clear_list}
        key = find_best_key(name, list(hits.keys()), threshold=0.7)
        if key and key in hits:
            hit = hits[key]
            status = "hit" if hit.get("match_type") == "exact" else "possible_match"
            return ok_result(
                self.source,
                "fixture",
                {"name": name, "status": status, "match": hit},
            )
        if normalize_key(name) in clear or find_best_key(name, list(clear), threshold=0.7):
            return ok_result(
                self.source,
                "fixture",
                {"name": name, "status": "clear", "match": None},
            )
        return ok_result(
            self.source,
            "fixture",
            {
                "name": name,
                "status": "clear",
                "match": None,
                "note": "No sanctions match in fixture corpus",
            },
        )

    def adverse_media(self, entity_name: str) -> ProviderResult:
        corpus = _load_json("adverse_media.json")
        key, row = _lookup(corpus, entity_name)
        articles = list((row or {}).get("articles", [])) if row else []
        return ok_result(
            self.source,
            "fixture",
            {
                "entity_name": entity_name,
                "article_count": len(articles),
                "articles": articles,
                "matched_key": key,
            },
        )

    def sec_filings(self, entity_name: str) -> ProviderResult:
        corpus = _load_json("sec.json")
        key, row = _lookup(corpus, entity_name)
        if row is None:
            return ok_result(
                self.source,
                "fixture",
                {
                    "entity_name": entity_name,
                    "found": False,
                    "note": "No SEC fixture record",
                },
            )
        return ok_result(
            self.source,
            "fixture",
            {**row, "entity_name": entity_name, "matched_key": key},
        )

    def address_signals(self, address: str) -> ProviderResult:
        corpus = _load_json("addresses.json")
        key = find_best_key(address, list(corpus.keys()), threshold=0.4)
        if key is None:
            lower = address.lower()
            signals: list[str] = []
            if "ups" in lower:
                signals.append("virtual_office_ups_store")
            if "registered agent" in lower or "c/o" in lower:
                signals.append("registered_agent_address")
            if "p.o. box" in lower or "po box" in lower:
                signals.append("po_box")
            risk = "high" if signals else "low"
            return ok_result(
                self.source,
                "fixture",
                {
                    "address": address,
                    "signals": signals,
                    "risk_level": risk,
                    "virtual_office": "virtual_office_ups_store" in signals,
                },
            )
        return ok_result(self.source, "fixture", {**corpus[key], "matched_key": key})
