"""OFAC SDN screening — path override, downloaded cache, or fixture fallback."""

from __future__ import annotations

import csv
import io
import json
import time
from pathlib import Path

import httpx

from packages.config import get_settings
from packages.osint.corpus import find_best_key, normalize_key
from packages.osint.providers.base import ProviderResult, err_result, ok_result

_OFAC_SDN_URL = "https://www.treasury.gov/ofac/downloads/sdn.csv"
_CACHE_MAX_AGE_SEC = 7 * 24 * 3600  # refresh weekly


class OfacProvider:
    source = "ofac"

    def available(self) -> bool:
        """True when SDN data is already on disk (path or cache)."""
        settings = get_settings()
        if settings.ofac_sdn_path and Path(settings.ofac_sdn_path).exists():
            return True
        return self._cache_csv_path().exists()

    def can_download(self) -> bool:
        return bool(get_settings().osint_cache_dir)

    def _cache_dir(self) -> Path:
        settings = get_settings()
        root = Path(settings.osint_cache_dir)
        if not root.is_absolute():
            root = Path.cwd() / root
        root.mkdir(parents=True, exist_ok=True)
        return root

    def _cache_csv_path(self) -> Path:
        return self._cache_dir() / "sdn.csv"

    def _parse_names_from_text(self, text: str, *, json_mode: bool = False) -> list[str]:
        if json_mode:
            data = json.loads(text)
            if isinstance(data, list):
                return [str(x) for x in data]
            if isinstance(data, dict):
                names = data.get("names") or data.get("hits") or []
                if isinstance(names, dict):
                    return list(names.keys())
                return [str(x) for x in names]
            return []

        names: list[str] = []
        reader = csv.reader(io.StringIO(text))
        for i, row in enumerate(reader):
            if not row:
                continue
            # SDN CSV: ent_num, SDN_Name, SDN_Type, ...
            if i == 0 and row[0].lower().startswith("ent"):
                continue
            name = row[1].strip() if len(row) > 1 else row[0].strip()
            if name:
                names.append(name)
        return names

    def _load_from_path(self, path: Path) -> list[str]:
        if not path.exists():
            return []
        text = path.read_text(encoding="utf-8", errors="ignore")
        return self._parse_names_from_text(text, json_mode=path.suffix.lower() == ".json")

    def _cache_is_fresh(self, path: Path) -> bool:
        if not path.exists():
            return False
        age = time.time() - path.stat().st_mtime
        return age < _CACHE_MAX_AGE_SEC

    async def ensure_cache(self, force: bool = False) -> Path | None:
        """Download Treasury SDN CSV into OSINT_CACHE_DIR when missing/stale."""
        cache_path = self._cache_csv_path()
        if not force and self._cache_is_fresh(cache_path):
            return cache_path
        try:
            async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
                resp = await client.get(
                    _OFAC_SDN_URL,
                    headers={"User-Agent": get_settings().geocoding_user_agent},
                )
                if resp.status_code != 200 or not resp.text.strip():
                    return cache_path if cache_path.exists() else None
                cache_path.write_text(resp.text, encoding="utf-8")
                return cache_path
        except Exception:
            return cache_path if cache_path.exists() else None

    async def _load_names(self) -> tuple[list[str], str]:
        settings = get_settings()
        if settings.ofac_sdn_path:
            path = Path(settings.ofac_sdn_path)
            names = self._load_from_path(path)
            if names:
                return names, str(path)

        cache_path = await self.ensure_cache()
        if cache_path:
            names = self._load_from_path(cache_path)
            if names:
                return names, str(cache_path)

        return [], ""

    async def check_sanctions(self, name: str) -> ProviderResult:
        names, source_path = await self._load_names()
        if not names:
            return err_result(
                self.source,
                "live",
                "OFAC SDN unavailable — set OFAC_SDN_PATH or allow cache download",
            )
        normalized_map = {normalize_key(n): n for n in names}
        key = find_best_key(name, list(normalized_map.keys()), threshold=0.85)
        if key:
            original = normalized_map[key]
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
                    "sdn_source": source_path,
                    "sdn_count": len(names),
                },
            )
        return ok_result(
            self.source,
            "live",
            {
                "name": name,
                "status": "clear",
                "match": None,
                "sdn_source": source_path,
                "sdn_count": len(names),
            },
        )
