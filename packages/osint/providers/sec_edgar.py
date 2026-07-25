"""SEC EDGAR company tickers / submissions lookup (free; User-Agent required)."""

from __future__ import annotations

import httpx

from packages.config import get_settings
from packages.osint.corpus import normalize_key
from packages.osint.providers.base import ProviderResult, err_result, ok_result


class SecEdgarProvider:
    source = "sec_edgar"

    def available(self) -> bool:
        return bool(get_settings().sec_edgar_user_agent)

    async def sec_filings(self, entity_name: str) -> ProviderResult:
        settings = get_settings()
        headers = {
            "User-Agent": settings.sec_edgar_user_agent,
            "Accept-Encoding": "gzip, deflate",
        }
        try:
            async with httpx.AsyncClient(timeout=20.0, headers=headers) as client:
                resp = await client.get("https://www.sec.gov/files/company_tickers.json")
                if resp.status_code != 200:
                    return err_result(
                        self.source, "live", f"ticker list HTTP {resp.status_code}"
                    )
                tickers = resp.json()
                target = normalize_key(entity_name)
                hit = None
                for row in tickers.values() if isinstance(tickers, dict) else []:
                    title = normalize_key(str(row.get("title", "")))
                    if target and (target in title or title in target):
                        hit = row
                        break
                if not hit:
                    return ok_result(
                        self.source,
                        "live",
                        {
                            "entity_name": entity_name,
                            "found": False,
                            "note": "No EDGAR ticker match (often private)",
                        },
                    )
                cik_int = int(hit.get("cik_str") or hit.get("cik") or 0)
                cik = f"{cik_int:010d}"
                sub = await client.get(
                    f"https://data.sec.gov/submissions/CIK{cik}.json"
                )
                recent_forms: list[str] = []
                if sub.status_code == 200:
                    forms = (
                        sub.json()
                        .get("filings", {})
                        .get("recent", {})
                        .get("form", [])
                    )
                    recent_forms = list(dict.fromkeys(forms[:8]))
                return ok_result(
                    self.source,
                    "live",
                    {
                        "entity_name": hit.get("title") or entity_name,
                        "found": True,
                        "cik": cik,
                        "ticker": hit.get("ticker"),
                        "recent_forms": recent_forms,
                    },
                )
        except Exception as exc:
            return err_result(self.source, "live", str(exc))
