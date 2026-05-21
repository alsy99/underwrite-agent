from pydantic import BaseModel, Field


class VerticalPack(BaseModel):
    name: str
    required_doc_types: list[str]
    cross_check_pairs: list[tuple[str, str]] = Field(default_factory=list)
    policy_seed_path: str | None = None
