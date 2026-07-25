from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.config import get_settings
from packages.cross_check.engine import CrossCheckEngine
from packages.db.models import ChunkRecord
from packages.llm.embeddings import get_embedding_service
from packages.osint.profile import ProfileAnalyzer
from packages.osint.providers.router import OsintRouter
from packages.policy_rag.service import PolicyRAGService
from packages.schemas.case import LoanVertical


class ToolRegistry:
    def __init__(
        self,
        session: AsyncSession,
        case_id: str,
        tenant_id: str,
        vertical: LoanVertical,
        metadata: dict[str, Any],
    ):
        self.session = session
        self.case_id = case_id
        self.tenant_id = tenant_id
        self.vertical = vertical
        self.metadata = metadata
        self.policy_rag = PolicyRAGService(session)
        self.embeddings = get_embedding_service()
        self.settings = get_settings()
        self.osint = OsintRouter()
        self.profiler = ProfileAnalyzer()
        self._geo_cache: dict[str, dict] = {}
        self._tool_results: list[dict[str, Any]] = []

    def record_tool_result(self, tool: str, args: dict, result: dict) -> None:
        self._tool_results.append({"tool": tool, "args": args, "result": result})

    async def search_documents(self, query: str, top_k: int = 5) -> list[dict]:
        result = await self.session.execute(
            select(ChunkRecord).where(ChunkRecord.case_id == self.case_id)
        )
        chunks = list(result.scalars().all())
        if not chunks:
            return []
        qvec = (await self.embeddings.embed([query]))[0]
        scored = []
        for ch in chunks:
            if ch.embedding:
                import math

                dot = sum(a * b for a, b in zip(qvec, ch.embedding, strict=False))
                na = math.sqrt(sum(a * a for a in qvec))
                nb = math.sqrt(sum(b * b for b in ch.embedding))
                score = dot / (na * nb) if na and nb else 0
                scored.append((score, ch))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [
            {
                "chunk_id": c.id,
                "document_id": c.document_id,
                "page": c.page,
                "content": c.content[:500],
                "score": round(s, 3),
            }
            for s, c in scored[:top_k]
        ]

    async def cross_check_narratives(self, document_bundle: str) -> list[dict]:
        engine = CrossCheckEngine(self.session, self.case_id, self.vertical)
        results = await engine.run(document_bundle)
        return [r.model_dump() for r in results]

    async def lookup_business_registry(self, entity_name: str, ein: str = "") -> dict:
        raw = await self.osint.lookup_registry(entity_name, ein)
        return self.osint.unwrap(raw)

    async def verify_employer_osint(
        self, employer: str, profile_url: str = ""
    ) -> dict:
        stated = self.metadata.get("stated_employer") or self.metadata.get("employer") or employer
        raw = await self.osint.verify_employer(employer, stated, profile_url)
        return self.osint.unwrap(raw)

    async def verify_web_presence(self, entity_name: str = "", domain: str = "") -> dict:
        name = entity_name or self.metadata.get("business_name") or ""
        dom = domain or self.metadata.get("domain") or ""
        raw = await self.osint.web_presence(name, dom)
        return self.osint.unwrap(raw)

    async def check_sanctions(self, name: str = "") -> dict:
        target = name or self.metadata.get("business_name") or self.metadata.get("applicant_name") or ""
        raw = await self.osint.check_sanctions(target)
        return self.osint.unwrap(raw)

    async def search_adverse_media(self, entity_name: str = "") -> dict:
        name = entity_name or self.metadata.get("business_name") or ""
        raw = await self.osint.adverse_media(name)
        return self.osint.unwrap(raw)

    async def lookup_sec_filings(self, entity_name: str = "") -> dict:
        name = entity_name or self.metadata.get("business_name") or ""
        raw = await self.osint.sec_filings(name)
        return self.osint.unwrap(raw)

    async def geocode_address(self, address: str) -> dict:
        if address in self._geo_cache:
            return self._geo_cache[address]
        url = "https://nominatim.openstreetmap.org/search"
        params = {"q": address, "format": "json", "limit": 1}
        headers = {"User-Agent": self.settings.geocoding_user_agent}
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(url, params=params, headers=headers)
                if resp.status_code == 200 and resp.json():
                    hit = resp.json()[0]
                    result = {
                        "address": address,
                        "lat": hit.get("lat"),
                        "lon": hit.get("lon"),
                        "display_name": hit.get("display_name"),
                        "source": "nominatim",
                        "mode": "live",
                    }
                    self._geo_cache[address] = result
                    return result
        except Exception:
            pass
        result = {
            "address": address,
            "lat": None,
            "lon": None,
            "display_name": address,
            "source": "fallback",
            "mode": "fallback",
        }
        self._geo_cache[address] = result
        return result

    async def address_risk_signals(self, address: str, business_type: str = "") -> dict:
        raw = await self.osint.address_signals(address)
        data = self.osint.unwrap(raw)
        geo = await self.geocode_address(address)
        lower = address.lower() + " " + str(geo.get("display_name", "")).lower()
        signals = list(data.get("signals") or [])
        if "ups" in lower and "virtual_office_ups_store" not in signals:
            signals.append("virtual_office_ups_store")
        if ("registered agent" in lower or "c/o" in lower) and "registered_agent_address" not in signals:
            signals.append("registered_agent_address")
        if "suite" in lower and business_type in ("retail", "manufacturing"):
            if "suite_mismatch_heavy_industry" not in signals:
                signals.append("suite_mismatch_heavy_industry")
        risk = data.get("risk_level") or ("high" if signals else "low")
        if signals and risk == "low":
            risk = "high" if any(
                s in signals
                for s in (
                    "virtual_office_ups_store",
                    "registered_agent_address",
                    "mail_drop",
                    "po_box",
                )
            ) else "medium"
        return {
            "address": address,
            "risk_level": risk,
            "signals": signals,
            "geocode": geo,
            "virtual_office": bool(data.get("virtual_office"))
            or "virtual_office_ups_store" in signals,
            "source": data.get("source"),
            "mode": data.get("mode"),
            "notes": data.get("notes"),
        }

    async def build_entity_profile(self, tool_results: list[dict] | None = None) -> dict:
        results = tool_results if tool_results is not None else self._tool_results
        profiles = self.profiler.build_profiles(self.metadata, results)
        return {
            "profiles": [p.model_dump(mode="json") for p in profiles],
            "count": len(profiles),
            "source": "profile_analyzer",
            "mode": self.osint.mode,
        }

    async def query_policy_rag(self, context: str) -> list[dict]:
        findings = await self.policy_rag.evaluate_case(
            self.tenant_id, self.case_id, context, self.vertical.value
        )
        return [f.model_dump() for f in findings]

    async def execute(self, tool: str, args: dict[str, Any], document_bundle: str) -> dict:
        if tool == "search_documents":
            out = {"results": await self.search_documents(args.get("query", ""))}
        elif tool == "cross_check_narratives":
            out = {"contradictions": await self.cross_check_narratives(document_bundle)}
        elif tool == "lookup_business_registry":
            out = await self.lookup_business_registry(
                args.get("entity_name", ""), args.get("ein", "")
            )
        elif tool == "verify_employer_osint":
            out = await self.verify_employer_osint(
                args.get("employer", ""), args.get("profile_url", "")
            )
        elif tool == "verify_web_presence":
            out = await self.verify_web_presence(
                args.get("entity_name", ""), args.get("domain", "")
            )
        elif tool == "check_sanctions":
            out = await self.check_sanctions(args.get("name", ""))
        elif tool == "search_adverse_media":
            out = await self.search_adverse_media(args.get("entity_name", ""))
        elif tool == "lookup_sec_filings":
            out = await self.lookup_sec_filings(args.get("entity_name", ""))
        elif tool == "geocode_address":
            out = await self.geocode_address(args.get("address", ""))
        elif tool == "address_risk_signals":
            out = await self.address_risk_signals(
                args.get("address", ""), args.get("business_type", "")
            )
        elif tool == "build_entity_profile":
            out = await self.build_entity_profile()
        elif tool == "query_policy_rag":
            out = {"findings": await self.query_policy_rag(document_bundle)}
        else:
            out = {"error": f"unknown tool {tool}"}
        if tool != "build_entity_profile" and "error" not in out:
            self.record_tool_result(tool, args, out)
        return out
