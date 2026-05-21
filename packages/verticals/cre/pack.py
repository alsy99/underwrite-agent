from packages.verticals.base import VerticalPack

CRE_PACK = VerticalPack(
    name="CRE Acquisition",
    required_doc_types=[
        "commercial_lease",
        "rent_roll",
        "appraisal",
        "operating_agreement",
    ],
    cross_check_pairs=[
        ("rent_roll NOI and occupancy", "commercial_lease terms"),
        ("appraisal value and cap rate", "rent_roll income"),
        ("lease guarantor entity", "operating_agreement members"),
        ("appraisal property address", "lease property address"),
    ],
    policy_seed_path="data/fixtures/policies/cre_policy_seed.md",
)
