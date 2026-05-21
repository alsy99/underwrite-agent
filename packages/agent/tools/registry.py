import json
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.config import get_settings
from packages.cross_check.engine import CrossCheckEngine
from packages.db.models import ChunkRecord
from packages.llm.embeddings import get_embedding_service
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
        self._geo_cache: dict[str, dict] = {}

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
        """Stub — fixture responses for demo."""
        fixtures = {
            "Sunrise Bakery LLC": {
                "status": "active",
                "registered_state": "OR",
                "incorporation_date": "2012-04-01",
                "registered_agent": "Northwest Registered Agent",
                "ein_match": True,
            },
            "Acme Consulting LLC": {
                "status": "active",
                "registered_state": "DE",
                "incorporation_date": "2019-03-12",
                "registered_agent": "Corporation Service Company",
                "ein_match": True,
            },
            "Beta Industries Inc": {
                "status": "active",
                "registered_state": "CA",
                "incorporation_date": "2015-08-01",
                "registered_agent": "CT Corporation",
                "ein_match": True,
            },
        }
        for name, data in fixtures.items():
            if name.lower() in entity_name.lower() or entity_name.lower() in name.lower():
                return {"entity_name": name, "source": "stub_registry", **data}
        return {
            "entity_name": entity_name,
            "source": "stub_registry",
            "status": "not_found",
            "note": "No registry match in stub dataset",
        }

    async def verify_employer_osint(
        self, employer: str, profile_url: str = ""
    ) -> dict:
        """Stub LinkedIn-style verification."""
        stated = self.metadata.get("stated_employer", employer)
        match = stated.lower() in employer.lower() or employer.lower() in stated.lower()
        if "Beta" in employer and "Acme" in stated:
            match = False
        return {
            "employer": employer,
            "stated_employer": stated,
            "profile_url": profile_url or "stub://linkedin",
            "match": match,
            "confidence": 0.85 if match else 0.2,
            "source": "stub_osint",
            "note": "MVP stub — production requires ToS-compliant provider",
        }

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
        }
        self._geo_cache[address] = result
        return result

    async def address_risk_signals(self, address: str, business_type: str = "") -> dict:
        geo = await self.geocode_address(address)
        lower = address.lower() + " " + geo.get("display_name", "").lower()
        signals = []
        if "ups" in lower or "ups store" in lower:
            signals.append("virtual_office_ups_store")
        if "registered agent" in lower or "c/o" in lower:
            signals.append("registered_agent_address")
        if "suite" in lower and business_type in ("retail", "manufacturing"):
            signals.append("suite_mismatch_heavy_industry")
        risk = "high" if signals else "low"
        return {
            "address": address,
            "risk_level": risk,
            "signals": signals,
            "geocode": geo,
        }

    async def query_policy_rag(self, context: str) -> list[dict]:
        findings = await self.policy_rag.evaluate_case(
            self.tenant_id, self.case_id, context, self.vertical.value
        )
        return [f.model_dump() for f in findings]

    async def execute(self, tool: str, args: dict[str, Any], document_bundle: str) -> dict:
        if tool == "search_documents":
            return {"results": await self.search_documents(args.get("query", ""))}
        if tool == "cross_check_narratives":
            return {"contradictions": await self.cross_check_narratives(document_bundle)}
        if tool == "lookup_business_registry":
            return await self.lookup_business_registry(
                args.get("entity_name", ""), args.get("ein", "")
            )
        if tool == "verify_employer_osint":
            return await self.verify_employer_osint(
                args.get("employer", ""), args.get("profile_url", "")
            )
        if tool == "geocode_address":
            return await self.geocode_address(args.get("address", ""))
        if tool == "address_risk_signals":
            return await self.address_risk_signals(
                args.get("address", ""), args.get("business_type", "")
            )
        if tool == "query_policy_rag":
            return {"findings": await self.query_policy_rag(document_bundle)}
        return {"error": f"unknown tool {tool}"}
