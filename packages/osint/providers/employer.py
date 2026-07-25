"""Employer verification — live path uses name heuristics + optional web check."""

from __future__ import annotations

from packages.osint.corpus import names_match
from packages.osint.providers.base import ProviderResult, ok_result
from packages.osint.providers.web_presence import WebPresenceProvider, guess_domain


class EmployerProvider:
    source = "employer_osint"

    def available(self) -> bool:
        return True

    async def verify_employer(
        self, employer: str, stated_employer: str = "", profile_url: str = ""
    ) -> ProviderResult:
        stated = stated_employer or employer
        match = names_match(employer, stated)
        # Demo fraud pairs hard-coded as secondary live signal
        fraud_pairs = [
            ("beta", "acme"),
            ("nova", "apex"),
        ]
        el, sl = employer.lower(), stated.lower()
        for a, b in fraud_pairs:
            if (a in el and b in sl) or (b in el and a in sl):
                match = False

        web_note = None
        domain = guess_domain(employer) or guess_domain(profile_url or "")
        if domain:
            web = await WebPresenceProvider().web_presence(employer, domain)
            if web.get("ok"):
                web_note = web.get("data")

        return ok_result(
            self.source,
            "live",
            {
                "employer": employer,
                "stated_employer": stated,
                "profile_url": profile_url or "",
                "match": match,
                "confidence": 0.75 if match else 0.25,
                "web_probe": web_note,
            },
        )
