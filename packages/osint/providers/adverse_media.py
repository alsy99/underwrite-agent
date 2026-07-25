"""Adverse media via NewsAPI (optional key)."""

from __future__ import annotations

import httpx

from packages.config import get_settings
from packages.osint.providers.base import ProviderResult, err_result, ok_result

_NEGATIVE = (
    "fraud",
    "lawsuit",
    "indictment",
    "sanction",
    "investigation",
    "complaint",
    "bankruptcy",
    "scam",
    "fine",
    "penalty",
)


class AdverseMediaProvider:
    source = "newsapi"

    def available(self) -> bool:
        return bool(get_settings().news_api_key)

    async def adverse_media(self, entity_name: str) -> ProviderResult:
        settings = get_settings()
        if not settings.news_api_key:
            return err_result(self.source, "live", "NEWS_API_KEY not set")
        params = {
            "q": f'"{entity_name}"',
            "language": "en",
            "sortBy": "publishedAt",
            "pageSize": 10,
            "apiKey": settings.news_api_key,
        }
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    "https://newsapi.org/v2/everything", params=params
                )
                if resp.status_code != 200:
                    return err_result(
                        self.source, "live", f"HTTP {resp.status_code}: {resp.text[:200]}"
                    )
                articles_raw = resp.json().get("articles") or []
                articles = []
                for a in articles_raw:
                    title = a.get("title") or ""
                    desc = a.get("description") or ""
                    blob = f"{title} {desc}".lower()
                    severity = "low"
                    if any(w in blob for w in _NEGATIVE):
                        severity = "medium"
                    if any(
                        w in blob
                        for w in ("fraud", "indictment", "sanction", "money laundering")
                    ):
                        severity = "high"
                    if severity == "low":
                        continue
                    articles.append(
                        {
                            "title": title,
                            "source": (a.get("source") or {}).get("name") or "newsapi",
                            "published": (a.get("publishedAt") or "")[:10],
                            "severity": severity,
                            "url": a.get("url"),
                            "summary": desc[:300],
                        }
                    )
                return ok_result(
                    self.source,
                    "live",
                    {
                        "entity_name": entity_name,
                        "article_count": len(articles),
                        "articles": articles,
                    },
                )
        except Exception as exc:
            return err_result(self.source, "live", str(exc))
