"""OpenCorporates company search (optional API key)."""

from __future__ import annotations

import httpx

from packages.config import get_settings
from packages.osint.providers.base import ProviderResult, err_result, ok_result


class OpenCorporatesProvider:
    source = "opencorporates"

    def available(self) -> bool:
        return bool(get_settings().opencorporates_api_key)

    async def lookup_registry(self, entity_name: str, ein: str = "") -> ProviderResult:
        settings = get_settings()
        if not settings.opencorporates_api_key:
            return err_result(self.source, "live", "OPENCORPORATES_API_KEY not set")
        params = {
            "q": entity_name,
            "api_token": settings.opencorporates_api_key,
            "per_page": 1,
        }
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    "https://api.opencorporates.com/v0.4/companies/search",
                    params=params,
                )
                if resp.status_code != 200:
                    return err_result(
                        self.source, "live", f"HTTP {resp.status_code}: {resp.text[:200]}"
                    )
                payload = resp.json()
                companies = (
                    payload.get("results", {}).get("companies")
                    or payload.get("companies")
                    or []
                )
                if not companies:
                    return ok_result(
                        self.source,
                        "live",
                        {
                            "entity_name": entity_name,
                            "status": "not_found",
                            "ein": ein or None,
                            "note": "No OpenCorporates match",
                        },
                    )
                company = companies[0].get("company") or companies[0]
                return ok_result(
                    self.source,
                    "live",
                    {
                        "entity_name": company.get("name") or entity_name,
                        "status": (company.get("current_status") or "unknown").lower(),
                        "registered_state": company.get("jurisdiction_code"),
                        "incorporation_date": company.get("incorporation_date"),
                        "registered_agent": company.get("agent_name"),
                        "company_number": company.get("company_number"),
                        "jurisdiction_code": company.get("jurisdiction_code"),
                        "opencorporates_url": company.get("opencorporates_url"),
                        "ein": ein or None,
                        "ein_match": None,
                        "officers": [],
                    },
                )
        except Exception as exc:
            return err_result(self.source, "live", str(exc))
