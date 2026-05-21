from packages.schemas.case import LoanVertical
from packages.verticals.base import VerticalPack
from packages.verticals.cre import CRE_PACK
from packages.verticals.sba import SBA_PACK
from packages.verticals.specialty_mortgage import SPECIALTY_MORTGAGE_PACK

_PACKS: dict[LoanVertical, VerticalPack] = {
    LoanVertical.SBA_7A: SBA_PACK,
    LoanVertical.CRE_ACQUISITION: CRE_PACK,
    LoanVertical.SPECIALTY_MORTGAGE: SPECIALTY_MORTGAGE_PACK,
}


def get_vertical_pack(vertical: LoanVertical) -> VerticalPack:
    return _PACKS[vertical]
