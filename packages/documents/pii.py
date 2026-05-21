import re

SSN_PATTERN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
EIN_PATTERN = re.compile(r"\b\d{2}-\d{7}\b")
ACCOUNT_PATTERN = re.compile(r"\b\d{8,17}\b")


def redact_pii(text: str) -> str:
    text = SSN_PATTERN.sub("[REDACTED-SSN]", text)
    text = EIN_PATTERN.sub("[REDACTED-EIN]", text)
    text = ACCOUNT_PATTERN.sub("[REDACTED-ACCT]", text)
    return text
