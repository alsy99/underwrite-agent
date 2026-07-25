"""Credit memo builder — deterministic Jinja templates with citations."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from packages.schemas.case import CaseFile, VarianceFinding

_TEMPLATE_DIR = Path(__file__).parent / "templates"


def _env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(_TEMPLATE_DIR)),
        autoescape=select_autoescape(enabled_extensions=()),
        trim_blocks=True,
        lstrip_blocks=True,
    )


def context_hash(payload: dict[str, Any]) -> str:
    blob = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(blob.encode()).hexdigest()[:16]


def build_memo_context(
    *,
    case_id: str,
    vertical: str,
    tenant_id: str,
    metadata: dict[str, Any],
    case_file: CaseFile,
    spread: dict[str, Any] | None = None,
    variances: list[VarianceFinding] | None = None,
) -> dict[str, Any]:
    return {
        "case_id": case_id,
        "vertical": vertical,
        "tenant_id": tenant_id,
        "metadata": metadata,
        "executive_summary": case_file.executive_summary,
        "recommended_action": case_file.recommended_action.value,
        "findings": [f.model_dump(mode="json") for f in case_file.findings],
        "contradictions": [c.model_dump(mode="json") for c in case_file.contradictions],
        "policy_findings": [p.model_dump(mode="json") for p in case_file.policy_findings],
        "entity_profiles": [p.model_dump(mode="json") for p in case_file.entity_profiles],
        "open_questions": list(case_file.open_questions),
        "spread": spread or {},
        "variances": [v.model_dump(mode="json") for v in (variances or case_file.spreads_summary)],
    }


def render_memo(vertical: str, context: dict[str, Any]) -> str:
    env = _env()
    template_name = f"{vertical}.md.j2"
    if not (_TEMPLATE_DIR / template_name).exists():
        template_name = "default.md.j2"
    tpl = env.get_template(template_name)
    return tpl.render(**context)
