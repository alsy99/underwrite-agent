"""Domain RDAP + basic HTTP reachability for web presence."""

from __future__ import annotations

import re

import httpx

from packages.osint.providers.base import ProviderResult, err_result, ok_result

_DOMAIN_RE = re.compile(
    r"\b([a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)+)\b",
    re.IGNORECASE,
)


def guess_domain(entity_name: str, domain: str = "") -> str | None:
    if domain:
        return domain.strip().lower().lstrip("http://").lstrip("https://").split("/")[0]
    # Only use explicit domain-looking tokens in name
    m = _DOMAIN_RE.search(entity_name or "")
    if m and "." in m.group(1):
        return m.group(1).lower()
    return None


class WebPresenceProvider:
    source = "rdap_http"

    def available(self) -> bool:
        return True

    async def web_presence(self, entity_name: str, domain: str = "") -> ProviderResult:
        host = guess_domain(entity_name, domain)
        if not host:
            return err_result(
                self.source,
                "live",
                "No domain available for RDAP/HTTP probe",
            )
        rdap: dict = {}
        site_live = False
        https = False
        try:
            async with httpx.AsyncClient(timeout=12.0, follow_redirects=True) as client:
                try:
                    r = await client.get(f"https://rdap.org/domain/{host}")
                    if r.status_code == 200:
                        payload = r.json()
                        rdap = {
                            "ldhName": payload.get("ldhName"),
                            "status": payload.get("status") or [],
                            "registrar": next(
                                (
                                    e.get("vcardArray", [None, [["fn", {}, "text", ""]]])[1][0][3]
                                    for e in (payload.get("entities") or [])
                                    if "registrar" in (e.get("roles") or [])
                                ),
                                None,
                            ),
                        }
                except Exception:
                    rdap = {}
                for scheme in ("https", "http"):
                    try:
                        resp = await client.get(f"{scheme}://{host}", headers={"User-Agent": "underwrite-agent/0.1"})
                        if resp.status_code < 500:
                            site_live = True
                            https = scheme == "https"
                            break
                    except Exception:
                        continue
        except Exception as exc:
            return err_result(self.source, "live", str(exc))

        return ok_result(
            self.source,
            "live",
            {
                "entity_name": entity_name,
                "domain": host,
                "site_live": site_live,
                "https": https,
                "rdap_status": rdap.get("status") or [],
                "registrar": rdap.get("registrar"),
                "created": None,
            },
        )
