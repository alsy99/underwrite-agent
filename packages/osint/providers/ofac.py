"""OFAC SDN screening — local file override or fixture-backed live check."""

from __future__ import annotations

import json
from pathlib import Path

import httpx

from packages.config import get_settings
from packages.osint.corpus import find_best_key, normalize_key
from packages.osint.providers.base import ProviderResult, err_result, ok_result

# Small public sample endpoint is unreliable; prefer local path or in-memory names.
_OFAC_FALLBACK_URL = (
    "https://www.treasury.gov/ofac/downloads/sdn.csv"
)


class OfacProvider:
    source = "ofac"

    def available(self) -> bool:
        settings = get_settings()
        return bool(settings.ofac_sdn_path) or True  # can attempt download

    def _load_local_names(self) -> list[str]:
        settings = get_settings()
        if not settings.ofac_sdn_path:
            return []
        path = Path(settings.ofac_sdn_path)
        if not path.exists():
            return []
        text = path.read_text(encoding="utf-8", errors="ignore")
        if path.suffix.lower() == ".json":
            data = json.loads(text)
            if isinstance(data, list):
                return [str(x) for x in data]
            if isinstance(data, dict):
                names = data.get("names") or data.get("hits") or []
                if isinstance(names, dict):
                    return list(names.keys())
                return [str(x) for x in names]
        # CSV: first column often SDN name
        names = []
        for line in text.splitlines()[1:]:
            if not line.strip():
                continue
            # SDN CSV uses quoted fields; take first field roughly
            if line.startswith('"'):
                end = line.find('"', 1)
                names.append(line[1:end] if end > 1 else line.split(",")[0])
            else:
                names.append(line.split(",")[0])
        return names

    async def check_sanctions(self, name: str) -> ProviderResult:
        names = self._load_local_names()
        if not names:
            # Without a local SDN dump, signal caller to use fixture
            return err_result(
                self.source,
                "live",
                "OFAC_SDN_PATH not configured — use fixture sanctions corpus",
            )
        key = find_best_key(name, [normalize_key(n) for n in names], threshold=0.85)
        if key:
            # recover original casing roughly
            original = next((n for n in names if normalize_key(n) == key), name)
            return ok_result(
                self.source,
                "live",
                {
                    "name": name,
                    "status": "hit",
                    "match": {
                        "name": original,
                        "list": "SDN",
                        "match_type": "fuzzy",
                        "severity": "high",
                    },
                },
            )
        return ok_result(
            self.source,
            "live",
            {"name": name, "status": "clear", "match": None},
        )

    async def refresh_sdn_hint(self) -> ProviderResult:
        """Optional connectivity probe — does not parse full CSV in MVP."""
        try:
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
                resp = await client.head(_OFAC_FALLBACK_URL)
                return ok_result(
                    self.source,
                    "live",
                    {"reachable": resp.status_code < 500, "status_code": resp.status_code},
                )
        except Exception as exc:
            return err_result(self.source, "live", str(exc))
