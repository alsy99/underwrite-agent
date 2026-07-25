"""Fuse OSINT tool results into EntityProfile objects + risk signals."""

from __future__ import annotations

from typing import Any

from packages.schemas.case import EntityProfile, OsintSignal


def _tool_map(tool_results: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in tool_results:
        tool = row.get("tool")
        if not tool:
            continue
        result = row.get("result") if isinstance(row.get("result"), dict) else {}
        out[tool] = result
    return out


class ProfileAnalyzer:
    def build_profiles(
        self,
        metadata: dict[str, Any],
        tool_results: list[dict[str, Any]],
    ) -> list[EntityProfile]:
        by_tool = _tool_map(tool_results)
        profiles: list[EntityProfile] = []

        business = (
            metadata.get("business_name")
            or metadata.get("entity_name")
            or ""
        ).strip()
        employer = (
            metadata.get("employer")
            or metadata.get("stated_employer")
            or ""
        ).strip()
        principal = (
            metadata.get("applicant_name")
            or metadata.get("principal_name")
            or ""
        ).strip()
        address = (metadata.get("address") or "").strip()

        if business:
            profiles.append(self._business_profile(business, metadata, by_tool))
        if employer and employer.lower() != business.lower():
            profiles.append(self._employer_profile(employer, metadata, by_tool))
        elif employer and not business:
            profiles.append(self._employer_profile(employer, metadata, by_tool))
        if principal:
            profiles.append(self._principal_profile(principal, metadata, by_tool))
        if address:
            profiles.append(self._address_profile(address, by_tool))

        return profiles

    def _business_profile(
        self, name: str, metadata: dict[str, Any], by_tool: dict[str, dict]
    ) -> EntityProfile:
        signals: list[OsintSignal] = []
        sources: list[str] = []
        registry = by_tool.get("lookup_business_registry")
        web = by_tool.get("verify_web_presence")
        sanctions = by_tool.get("check_sanctions")
        media = by_tool.get("search_adverse_media")
        sec = by_tool.get("lookup_sec_filings")

        identity = 0.2
        risk = 0.0

        if registry:
            sources.append(str(registry.get("source") or "registry"))
            status = (registry.get("status") or "").lower()
            if status == "not_found":
                signals.append(
                    OsintSignal(
                        source="registry",
                        signal_type="entity_not_found",
                        severity="medium",
                        summary=f"No registry match for {name}",
                        evidence=registry,
                        confidence=0.7,
                    )
                )
                risk += 0.25
            elif status in ("inactive", "dissolved", "revoked"):
                signals.append(
                    OsintSignal(
                        source="registry",
                        signal_type="inactive_entity",
                        severity="high",
                        summary=f"Registry status is {status}",
                        evidence=registry,
                        confidence=0.9,
                    )
                )
                risk += 0.45
                identity += 0.3
            elif status == "active":
                identity += 0.45
            if registry.get("ein_match") is False and metadata.get("ein"):
                signals.append(
                    OsintSignal(
                        source="registry",
                        signal_type="ein_mismatch",
                        severity="high",
                        summary="EIN does not match registry record",
                        evidence={"ein": metadata.get("ein")},
                        confidence=0.8,
                    )
                )
                risk += 0.3

        if web:
            sources.append(str(web.get("source") or "web"))
            if web.get("site_live"):
                identity += 0.15
            else:
                signals.append(
                    OsintSignal(
                        source="web",
                        signal_type="site_down",
                        severity="medium",
                        summary="No live website detected",
                        evidence=web,
                        confidence=0.6,
                    )
                )
                risk += 0.15

        if sanctions:
            sources.append(str(sanctions.get("source") or "sanctions"))
            st = sanctions.get("status")
            if st == "hit":
                signals.append(
                    OsintSignal(
                        source="sanctions",
                        signal_type="sanctions_hit",
                        severity="high",
                        summary="Sanctions list hit",
                        evidence=sanctions,
                        confidence=0.95,
                    )
                )
                risk += 0.6
            elif st == "possible_match":
                signals.append(
                    OsintSignal(
                        source="sanctions",
                        signal_type="sanctions_possible",
                        severity="medium",
                        summary="Possible sanctions name match — manual review",
                        evidence=sanctions,
                        confidence=0.6,
                    )
                )
                risk += 0.3

        articles = []
        if media:
            sources.append(str(media.get("source") or "adverse_media"))
            articles = list(media.get("articles") or [])
            for art in articles:
                sev = art.get("severity") or "medium"
                signals.append(
                    OsintSignal(
                        source="adverse_media",
                        signal_type="adverse_media",
                        severity=sev,
                        summary=art.get("title") or "Adverse media",
                        evidence=art,
                        confidence=0.55,
                    )
                )
                risk += 0.35 if sev == "high" else 0.15

        if sec:
            sources.append(str(sec.get("source") or "sec"))

        status = self._status(identity, risk, signals)
        return EntityProfile(
            entity_name=name,
            entity_type="business",
            identity_confidence=round(min(identity, 1.0), 3),
            risk_score=round(min(risk, 1.0), 3),
            status=status,
            registry=registry,
            web_presence=web,
            sanctions=sanctions,
            adverse_media=articles,
            principals=[{"name": p} for p in (metadata.get("principals") or [])]
            if metadata.get("principals")
            else ([{"name": metadata["applicant_name"]}] if metadata.get("applicant_name") else []),
            signals=signals,
            sources_used=sorted(set(sources)),
        )

    def _employer_profile(
        self, name: str, metadata: dict[str, Any], by_tool: dict[str, dict]
    ) -> EntityProfile:
        signals: list[OsintSignal] = []
        sources: list[str] = []
        verify = by_tool.get("verify_employer_osint")
        identity = 0.3
        risk = 0.0
        if verify:
            sources.append(str(verify.get("source") or "employer_osint"))
            if verify.get("match"):
                identity += 0.5
            else:
                signals.append(
                    OsintSignal(
                        source="employer_osint",
                        signal_type="employer_mismatch",
                        severity="high",
                        summary=(
                            f"Stated employer ({verify.get('stated_employer')}) "
                            f"does not match verification target ({verify.get('employer')})"
                        ),
                        evidence=verify,
                        confidence=float(verify.get("confidence") or 0.2),
                    )
                )
                risk += 0.5
        status = self._status(identity, risk, signals)
        return EntityProfile(
            entity_name=name,
            entity_type="employer",
            identity_confidence=round(min(identity, 1.0), 3),
            risk_score=round(min(risk, 1.0), 3),
            status=status,
            signals=signals,
            sources_used=sorted(set(sources)),
        )

    def _principal_profile(
        self, name: str, metadata: dict[str, Any], by_tool: dict[str, dict]
    ) -> EntityProfile:
        signals: list[OsintSignal] = []
        sources: list[str] = []
        # Prefer principal-specific sanctions if tool ran with that name; else scan results
        sanctions = by_tool.get("check_sanctions")
        identity = 0.4
        risk = 0.0
        if sanctions and normalize_contains(sanctions.get("name"), name):
            sources.append(str(sanctions.get("source") or "sanctions"))
            if sanctions.get("status") in ("hit", "possible_match"):
                sev = "high" if sanctions.get("status") == "hit" else "medium"
                signals.append(
                    OsintSignal(
                        source="sanctions",
                        signal_type="principal_sanctions",
                        severity=sev,
                        summary=f"Sanctions signal for principal {name}",
                        evidence=sanctions,
                        confidence=0.8,
                    )
                )
                risk += 0.55 if sev == "high" else 0.3
            else:
                identity += 0.2
        status = self._status(identity, risk, signals)
        return EntityProfile(
            entity_name=name,
            entity_type="principal",
            identity_confidence=round(min(identity, 1.0), 3),
            risk_score=round(min(risk, 1.0), 3),
            status=status,
            sanctions=sanctions if sanctions and normalize_contains(sanctions.get("name"), name) else None,
            signals=signals,
            sources_used=sorted(set(sources)),
        )

    def _address_profile(self, address: str, by_tool: dict[str, dict]) -> EntityProfile:
        signals: list[OsintSignal] = []
        sources: list[str] = []
        risk_row = by_tool.get("address_risk_signals")
        geo = by_tool.get("geocode_address")
        identity = 0.3
        risk = 0.0
        addr_data = None
        if geo:
            sources.append(str(geo.get("source") or "geocode"))
            if geo.get("lat") is not None:
                identity += 0.3
            addr_data = {"geocode": geo}
        if risk_row:
            sources.append(str(risk_row.get("source") or "address_risk"))
            addr_data = {**(addr_data or {}), **risk_row}
            for sig in risk_row.get("signals") or []:
                signals.append(
                    OsintSignal(
                        source="address_risk",
                        signal_type=str(sig),
                        severity="high" if risk_row.get("risk_level") == "high" else "medium",
                        summary=f"Address signal: {sig}",
                        evidence=risk_row,
                        confidence=0.75,
                    )
                )
            if risk_row.get("risk_level") == "high":
                risk += 0.4
            elif risk_row.get("signals"):
                risk += 0.15
        status = self._status(identity, risk, signals)
        return EntityProfile(
            entity_name=address,
            entity_type="address",
            identity_confidence=round(min(identity, 1.0), 3),
            risk_score=round(min(risk, 1.0), 3),
            status=status,
            address=addr_data,
            signals=signals,
            sources_used=sorted(set(sources)),
        )

    @staticmethod
    def _status(identity: float, risk: float, signals: list[OsintSignal]) -> str:
        if any(s.severity == "high" and s.signal_type.endswith("hit") for s in signals):
            return "flagged"
        if any(s.signal_type in ("employer_mismatch", "ein_mismatch") for s in signals):
            return "mismatch"
        if any(s.severity == "high" for s in signals) or risk >= 0.45:
            return "flagged"
        if identity >= 0.65 and risk < 0.2:
            return "corroborated"
        if identity >= 0.35:
            return "partial"
        return "unverified"


def normalize_contains(a: Any, b: str) -> bool:
    if not a or not b:
        return False
    return str(b).lower() in str(a).lower() or str(a).lower() in str(b).lower()
