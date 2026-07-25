"""Key-aware OSINT routing: live when available, else fixture corpus."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from packages.config import get_settings
from packages.osint.providers.adverse_media import AdverseMediaProvider
from packages.osint.providers.base import ProviderResult
from packages.osint.providers.employer import EmployerProvider
from packages.osint.providers.fixture import FixtureProvider
from packages.osint.providers.ofac import OfacProvider
from packages.osint.providers.opencorporates import OpenCorporatesProvider
from packages.osint.providers.sec_edgar import SecEdgarProvider
from packages.osint.providers.web_presence import WebPresenceProvider


class OsintRouter:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.fixture = FixtureProvider()
        self.opencorporates = OpenCorporatesProvider()
        self.sec = SecEdgarProvider()
        self.ofac = OfacProvider()
        self.web = WebPresenceProvider()
        self.media = AdverseMediaProvider()
        self.employer = EmployerProvider()

    @property
    def mode(self) -> str:
        return (self.settings.osint_mode or "auto").lower()

    def _prefer_live(self) -> bool:
        return self.mode in ("auto", "live")

    def _force_fixture(self) -> bool:
        return self.mode == "fixture"

    async def _with_fallback(
        self,
        live_factory: Callable[[], Awaitable[ProviderResult]],
        fixture_fn: Callable[[], ProviderResult],
        live_ready: bool,
    ) -> ProviderResult:
        if self._force_fixture() or not self._prefer_live() or not live_ready:
            return fixture_fn()
        result = await live_factory()
        if result.get("ok"):
            return result
        if self.mode == "live":
            return result
        # auto: fall back to fixture
        fb = fixture_fn()
        if isinstance(fb, dict):
            fb = {**fb, "live_error": result.get("error")}
        return fb

    async def lookup_registry(self, entity_name: str, ein: str = "") -> ProviderResult:
        return await self._with_fallback(
            lambda: self.opencorporates.lookup_registry(entity_name, ein),
            lambda: self.fixture.lookup_registry(entity_name, ein),
            self.opencorporates.available(),
        )

    async def verify_employer(
        self, employer: str, stated_employer: str = "", profile_url: str = ""
    ) -> ProviderResult:
        # Fixture preferred for deterministic demo mismatches; live only if OSINT_MODE=live
        if self.mode != "live":
            return self.fixture.verify_employer(employer, stated_employer, profile_url)
        return await self.employer.verify_employer(employer, stated_employer, profile_url)

    async def web_presence(self, entity_name: str, domain: str = "") -> ProviderResult:
        return await self._with_fallback(
            lambda: self.web.web_presence(entity_name, domain),
            lambda: self.fixture.web_presence(entity_name, domain),
            self.web.available() and bool(domain),
        )

    async def check_sanctions(self, name: str) -> ProviderResult:
        live_ready = bool(self.settings.ofac_sdn_path)
        return await self._with_fallback(
            lambda: self.ofac.check_sanctions(name),
            lambda: self.fixture.check_sanctions(name),
            live_ready,
        )

    async def adverse_media(self, entity_name: str) -> ProviderResult:
        return await self._with_fallback(
            lambda: self.media.adverse_media(entity_name),
            lambda: self.fixture.adverse_media(entity_name),
            self.media.available(),
        )

    async def sec_filings(self, entity_name: str) -> ProviderResult:
        return await self._with_fallback(
            lambda: self.sec.sec_filings(entity_name),
            lambda: self.fixture.sec_filings(entity_name),
            self.sec.available() and self.mode == "live",
        )

    async def address_signals(self, address: str) -> ProviderResult:
        # Address heuristics always use fixture corpus + text rules (deterministic)
        return self.fixture.address_signals(address)

    def unwrap(self, result: ProviderResult) -> dict[str, Any]:
        """Flatten provider result for tool responses."""
        data = dict(result.get("data") or {})
        data["source"] = result.get("source")
        data["mode"] = result.get("mode")
        if result.get("live_error"):
            data["live_error"] = result["live_error"]
        if not result.get("ok") and result.get("error"):
            data["error"] = result["error"]
            data.setdefault("status", "error")
        return data
