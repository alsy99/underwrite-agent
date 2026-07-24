from packages.verticals.base import VerticalPack

SPECIALTY_MORTGAGE_PACK = VerticalPack(
    name="Specialty Mortgage (Bank Statement)",
    required_doc_types=[
        "bank_statement",
        "employment_letter",
        "application",
    ],
    cross_check_pairs=[
        ("application stated income", "bank_statement deposit patterns"),
        ("employment_letter employer and role", "application employer"),
        ("letter of explanation deposits", "bank_statement large deposits"),
    ],
    policy_seed_path="data/fixtures/policies/specialty_mortgage_policy_seed.md",
)
