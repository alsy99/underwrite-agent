from pathlib import Path

DOC_TYPE_KEYWORDS: dict[str, list[str]] = {
    "form_1919": ["form 1919", "borrower information form", "sba form 1919"],
    "form_4506c": ["4506-c", "4506c", "tax transcript", "irs request"],
    "profit_loss": ["profit and loss", "p&l", "income statement", "statement of operations"],
    "debt_schedule": ["debt schedule", "schedule of liabilities", "business debt"],
    "bank_statement": ["bank statement", "account summary", "beginning balance"],
    "employment_letter": ["employment verification", "verification of employment", "voe"],
    "tax_return": ["form 1120", "form 1040", "tax return", "schedule c"],
    "commercial_lease": ["lease agreement", "lessor", "lessee", "rent roll"],
    "rent_roll": ["rent roll", "tenant roster", "unit mix"],
    "appraisal": ["appraisal report", "market value", "cap rate"],
    "operating_agreement": ["operating agreement", "llc agreement", "member"],
    "invoice": ["invoice", "merchant", "line items"],
    "application": ["loan application", "borrower application", "applicant"],
}


def classify_document(filename: str, text: str) -> str:
    combined = f"{filename.lower()} {text[:4000].lower()}"
    best_type = "unknown"
    best_score = 0
    for doc_type, keywords in DOC_TYPE_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in combined)
        if score > best_score:
            best_score = score
            best_type = doc_type
    if best_score == 0:
        ext = Path(filename).stem.lower()
        for doc_type in DOC_TYPE_KEYWORDS:
            if doc_type.replace("_", "") in ext.replace("_", ""):
                return doc_type
    return best_type
