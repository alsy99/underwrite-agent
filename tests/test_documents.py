from packages.documents.classify import classify_document
from packages.documents.pii import redact_pii


def test_classify_form_1919():
    text = "SBA Form 1919 Borrower Information Form annual gross revenues"
    assert classify_document("application.pdf", text) == "form_1919"


def test_classify_employment_letter():
    text = "Employment verification letter confirms full-time employment"
    assert classify_document("voe.txt", text) == "employment_letter"


def test_redact_ssn():
    text = "SSN 123-45-6789 and EIN 12-3456789"
    redacted = redact_pii(text)
    assert "123-45-6789" not in redacted
    assert "[REDACTED" in redacted
