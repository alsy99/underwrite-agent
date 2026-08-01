

def extract_text_from_bytes(filename: str, data: bytes) -> tuple[str, int]:
    lower = filename.lower()
    if lower.endswith(".pdf"):
        return _parse_pdf(data)
    if lower.endswith((".txt", ".md")):
        text = data.decode("utf-8", errors="replace")
        return text, max(1, text.count("\n") // 40 + 1)
    try:
        text = data.decode("utf-8", errors="replace")
        return text, 1
    except Exception:
        return "", 0


def _parse_pdf(data: bytes) -> tuple[str, int]:
    import fitz

    doc = fitz.open(stream=data, filetype="pdf")
    pages = []
    for i, page in enumerate(doc):
        pages.append(f"--- Page {i + 1} ---\n{page.get_text()}")
    doc.close()
    text = "\n\n".join(pages)
    return text, len(pages)
