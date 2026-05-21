import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from packages.audit.logger import AuditLogger
from packages.db.models import ChunkRecord, DocumentRecord
from packages.documents.chunk import chunk_text
from packages.documents.classify import classify_document
from packages.documents.parse import extract_text_from_bytes
from packages.documents.pii import redact_pii
from packages.llm.embeddings import get_embedding_service
from packages.storage.minio_client import StorageClient


class DocumentPipeline:
    def __init__(self, session: AsyncSession, case_id: str, tenant_id: str):
        self.session = session
        self.case_id = case_id
        self.tenant_id = tenant_id
        self.storage = StorageClient()
        self.embeddings = get_embedding_service()
        self.audit = AuditLogger(session, case_id)

    async def ingest_file(self, filename: str, data: bytes) -> DocumentRecord:
        storage_key = self.storage.upload(self.tenant_id, filename, data)
        raw_text, page_count = extract_text_from_bytes(filename, data)
        doc_type = classify_document(filename, raw_text)
        redacted = redact_pii(raw_text)

        doc = DocumentRecord(
            id=str(uuid.uuid4()),
            case_id=self.case_id,
            tenant_id=self.tenant_id,
            filename=filename,
            doc_type=doc_type,
            storage_key=storage_key,
            page_count=page_count,
            raw_text=redacted,
        )
        self.session.add(doc)
        await self.session.flush()

        chunks = chunk_text(redacted)
        texts = [c[0] for c in chunks if c[0].strip()]
        vectors = await self.embeddings.embed(texts) if texts else []

        for idx, (content, page) in enumerate(chunks):
            if not content.strip():
                continue
            emb = vectors[idx] if idx < len(vectors) else None
            chunk = ChunkRecord(
                id=str(uuid.uuid4()),
                document_id=doc.id,
                case_id=self.case_id,
                chunk_index=idx,
                content=content,
                page=page,
                embedding=emb,
            )
            self.session.add(chunk)

        await self.audit.log(
            actor="system",
            action="document_ingested",
            inputs={"filename": filename, "doc_type": doc_type},
            outputs={"document_id": doc.id, "chunks": len(chunks), "pages": page_count},
            prompt_version="ingest_v1",
        )
        await self.session.flush()
        return doc

    async def get_case_text_bundle(self) -> str:
        from sqlalchemy import select

        result = await self.session.execute(
            select(DocumentRecord).where(DocumentRecord.case_id == self.case_id)
        )
        parts = []
        for doc in result.scalars().all():
            parts.append(
                f"[DOC id={doc.id} type={doc.doc_type} file={doc.filename}]\n{doc.raw_text or ''}"
            )
        return "\n\n".join(parts)
