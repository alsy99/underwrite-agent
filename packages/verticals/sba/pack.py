from packages.verticals.base import VerticalPack

SBA_PACK = VerticalPack(
    name="SBA 7(a)",
    required_doc_types=[
        "form_1919",
        "form_4506c",
        "profit_loss",
        "debt_schedule",
        "bank_statement",
    ],
    cross_check_pairs=[
        ("form_1919 revenue and business name", "profit_loss revenue"),
        ("form_1919 employer/business", "employment_letter employer"),
        ("application stated income", "bank_statement deposits"),
        ("debt_schedule liabilities", "form_1919 affiliated entities"),
        ("tax_return revenue", "profit_loss revenue"),
    ],
    policy_seed_path="data/fixtures/policies/sba_policy_seed.md",
)
