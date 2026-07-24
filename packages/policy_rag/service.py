import uuid
from datetime import date

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.audit.logger import AuditLogger
from packages.db.models import PolicyChunkRecord, PolicyDocumentRecord
from packages.documents.chunk import chunk_text
from packages.documents.parse import extract_text_from_bytes
from packages.documents.pii import redact_pii
from packages.llm.client import LLMClient
from packages.llm.embeddings import get_embedding_service
from packages.schemas.case import PolicyFinding
from packages.storage.minio_client import StorageClient


class PolicyFindingList(BaseModel):
    findings: list[PolicyFinding] = Field(default_factory=list)


class PolicyRAGService:
    PROMPT_VERSION = "policy_rag_v1"

    def __init__(self, session: AsyncSession):
        self.session = session
        self.storage = StorageClient()
        self.embeddings = get_embedding_service()
        self.llm = LLMClient()

    async def ingest_policy(
        self,
        tenant_id: str,
        title: str,
        filename: str,
        data: bytes,
        policy_version: str | None = None,
        effective_date: str | None = None,
    ) -> PolicyDocumentRecord:
        storage_key = self.storage.upload(tenant_id, filename, data, prefix="policies")
        text, _ = extract_text_from_bytes(filename, data)
        redacted = redact_pii(text)
        version = policy_version or date.today().isoformat()
        eff = effective_date or version

        policy = PolicyDocumentRecord(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            title=title,
            policy_version=version,
            effective_date=eff,
            storage_key=storage_key,
        )
        self.session.add(policy)
        await self.session.flush()

        chunks = chunk_text(redacted, chunk_size=600, overlap=80)
        texts = [c[0] for c in chunks if c[0].strip()]
        vectors = await self.embeddings.embed(texts) if texts else []

        for idx, (content, _) in enumerate(chunks):
            if not content.strip():
                continue
            self.session.add(
                PolicyChunkRecord(
                    id=str(uuid.uuid4()),
                    policy_document_id=policy.id,
                    tenant_id=tenant_id,
                    chunk_index=idx,
                    content=content,
                    embedding=vectors[idx] if idx < len(vectors) else None,
                )
            )
        await self.session.flush()
        return policy

    async def list_policies(self, tenant_id: str) -> list[PolicyDocumentRecord]:
        result = await self.session.execute(
            select(PolicyDocumentRecord)
            .where(PolicyDocumentRecord.tenant_id == tenant_id)
            .order_by(PolicyDocumentRecord.created_at.desc())
        )
        return list(result.scalars().all())

    async def retrieve(self, tenant_id: str, query: str, top_k: int = 5) -> list[PolicyChunkRecord]:
        result = await self.session.execute(
            select(PolicyChunkRecord).where(PolicyChunkRecord.tenant_id == tenant_id)
        )
        chunks = list(result.scalars().all())
        if not chunks:
            return []
        query_vec = (await self.embeddings.embed([query]))[0]
        scored = []
        for ch in chunks:
            if ch.embedding:
                score = _cosine(query_vec, ch.embedding)
                scored.append((score, ch))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [c for _, c in scored[:top_k]]

    async def evaluate_case(
        self,
        tenant_id: str,
        case_id: str,
        context: str,
        vertical: str,
    ) -> list[PolicyFinding]:
        audit = AuditLogger(self.session, case_id)
        query = f"underwriting policy compliance {vertical} income revenue fraud"
        chunks = await self.retrieve(tenant_id, query, top_k=6)
        if not chunks:
            from pathlib import Path

            seed_map = {
                "cre_acquisition": "cre_policy_seed.md",
                "specialty_mortgage_bank_statement": "specialty_mortgage_policy_seed.md",
            }
            seed_name = seed_map.get(vertical, "sba_policy_seed.md")
            seed = (
                Path(__file__).resolve().parents[2]
                / "data"
                / "fixtures"
                / "policies"
                / seed_name
            )
            if seed.exists():
                await self.ingest_policy(
                    tenant_id,
                    f"{vertical} Policy Seed",
                    seed.name,
                    seed.read_bytes(),
                    policy_version="seed",
                )
                chunks = await self.retrieve(tenant_id, query, top_k=6)

        excerpts = "\n---\n".join(
            f"[policy_chunk {c.id}]\n{c.content[:1200]}" for c in chunks
        )
        system = (
            "You are a bank policy compliance engine. Given policy excerpts and a loan case, "
            'output JSON: {"findings":[{"rule_ref":"...","status":"pass|fail|review",'
            '"excerpt":"...","source_policy_doc_id":"...","confidence":0.0-1.0}]}'
        )
        user = f"Case context:\n{context[:12000]}\n\nPolicy excerpts:\n{excerpts}"

        raw = await self.llm.complete_json(system, user, prompt_version=self.PROMPT_VERSION)
        findings: list[PolicyFinding] = []
        for item in raw.get("findings", []):
            try:
                if not item.get("source_policy_doc_id") and chunks:
                    item["source_policy_doc_id"] = chunks[0].policy_document_id
                findings.append(PolicyFinding.model_validate(item))
            except Exception:
                continue

        await audit.log(
            actor="policy_rag",
            action="policy_match",
            inputs={"tenant_id": tenant_id, "chunks_retrieved": len(chunks)},
            outputs={"findings": [f.model_dump() for f in findings]},
            prompt_version=self.PROMPT_VERSION,
        )
        return findings


def _cosine(a: list[float], b: list[float]) -> float:
    import math

    dot = sum(x * y for x, y in zip(a, b, strict=False))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)
