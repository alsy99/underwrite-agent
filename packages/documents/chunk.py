def chunk_text(text: str, chunk_size: int = 800, overlap: int = 100) -> list[tuple[str, int | None]]:
    if not text.strip():
        return []
    chunks: list[tuple[str, int | None]] = []
    page = None
    segments = text.split("--- Page ")
    if len(segments) > 1:
        for seg in segments[1:]:
            lines = seg.split("\n", 1)
            try:
                page_num = int(lines[0].strip().split()[0])
                body = lines[1] if len(lines) > 1 else ""
            except (ValueError, IndexError):
                page_num = None
                body = seg
            for c in _split_body(body, chunk_size, overlap):
                chunks.append((c, page_num))
        return chunks
    for c in _split_body(text, chunk_size, overlap):
        chunks.append((c, page))
    return chunks


def _split_body(text: str, chunk_size: int, overlap: int) -> list[str]:
    text = text.strip()
    if len(text) <= chunk_size:
        return [text] if text else []
    result = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        result.append(text[start:end])
        start = end - overlap
    return result
