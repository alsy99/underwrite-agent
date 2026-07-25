"""Spreading parse + variance tests."""

from pathlib import Path

from packages.spreading import compute_variances, parse_tabular, stated_from_metadata

ROOT = Path(__file__).resolve().parents[1]


def test_parse_sba_clean_csv():
    data = (ROOT / "data/fixtures/spreads/sba_clean.csv").read_bytes()
    out = parse_tabular("sba_clean.csv", data)
    assert out["gross_revenue"] == 450000
    assert out["stated_income"] == 95000


def test_variance_flags_revenue_mismatch():
    spread = parse_tabular(
        "x.csv",
        (ROOT / "data/fixtures/spreads/sba_mismatch.csv").read_bytes(),
    )
    stated = {"gross_revenue": 450000, "stated_income": 95000}
    findings = compute_variances(spread, stated, "sba_7a")
    assert any(f.metric == "gross_revenue" for f in findings)
    assert any(f.severity in ("medium", "high") for f in findings)


def test_no_variance_when_aligned():
    spread = {"gross_revenue": 450000}
    stated = {"gross_revenue": 450000}
    assert compute_variances(spread, stated, "sba_7a") == []


def test_stated_from_metadata():
    meta = stated_from_metadata({"annual_revenue": "100000", "monthly_income": 5000})
    assert meta["gross_revenue"] == 100000
    assert meta["stated_income"] == 5000


def test_memo_render_includes_action():
    from packages.memo import build_memo_context, render_memo
    from packages.schemas.case import CaseFile, RecommendedAction

    cf = CaseFile(
        executive_summary="Test summary for underwriter.",
        recommended_action=RecommendedAction.REVIEW,
    )
    ctx = build_memo_context(
        case_id="c1",
        vertical="sba_7a",
        tenant_id="default",
        metadata={"business_name": "Acme"},
        case_file=cf,
    )
    body = render_memo("sba_7a", ctx)
    assert "Acme" in body
    assert "review" in body
    assert "Advisory" in body


def test_webhook_signature_roundtrip():
    from packages.los import sign_payload, verify_signature

    body = b'{"event":"case.completed"}'
    sig = sign_payload("secret", body)
    assert verify_signature("secret", body, sig)
    assert not verify_signature("wrong", body, sig)
