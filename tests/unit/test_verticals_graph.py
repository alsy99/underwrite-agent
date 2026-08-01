"""Backend unit: vertical packs + graph stages (no DB)."""

import pytest

from apps.worker.agent_graph import GRAPH_STAGES
from packages.schemas.case import LoanVertical
from packages.verticals import get_vertical_pack


@pytest.mark.unit
@pytest.mark.parametrize(
    "vertical,needle",
    [
        (LoanVertical.SBA_7A, "form_1919"),
        (LoanVertical.CRE_ACQUISITION, "rent_roll"),
        (LoanVertical.SPECIALTY_MORTGAGE, "bank_statement"),
    ],
)
def test_vertical_pack_has_required_docs(vertical, needle):
    pack = get_vertical_pack(vertical)
    assert any(needle in t for t in pack.required_doc_types)


@pytest.mark.unit
def test_graph_stages_order():
    assert GRAPH_STAGES[0] == "intake"
    assert "cross_check" in GRAPH_STAGES
    assert GRAPH_STAGES[-1] == "finalize"
