"""OFAC SDN cache / parse unit tests (no network)."""

import os
from pathlib import Path

import pytest

os.environ.setdefault("OSINT_MODE", "fixture")


@pytest.mark.asyncio
async def test_ofac_parse_and_screen_from_path(tmp_path, monkeypatch):
    sdn = tmp_path / "sdn.csv"
    sdn.write_text(
        "ent_num,SDN_Name,SDN_Type,Program,Title,Call_Sign,Vess_type,Tonnage,Gross_Registered_Tonnage,Vess_flag,Vess_owner,Remarks\n"
        '12345,"BLOCKED TRADER SYNDICATE",entity,DEMO,,,,,,,\n'
        '12346,"SOME OTHER PERSON",individual,DEMO,,,,,,,\n',
        encoding="utf-8",
    )
    monkeypatch.setenv("OFAC_SDN_PATH", str(sdn))
    monkeypatch.setenv("OSINT_MODE", "live")
    from packages.config import get_settings
    from packages.osint.providers.ofac import OfacProvider

    get_settings.cache_clear()
    provider = OfacProvider()
    assert provider.available() is True
    hit = await provider.check_sanctions("Blocked Trader Syndicate")
    assert hit["ok"] is True
    assert hit["data"]["status"] == "hit"
    clear = await provider.check_sanctions("Acme Consulting LLC")
    assert clear["data"]["status"] == "clear"
    get_settings.cache_clear()


def test_ofac_available_false_without_files(tmp_path, monkeypatch):
    monkeypatch.setenv("OFAC_SDN_PATH", "")
    monkeypatch.setenv("OSINT_CACHE_DIR", str(tmp_path / "empty_cache"))
    from packages.config import get_settings
    from packages.osint.providers.ofac import OfacProvider

    get_settings.cache_clear()
    provider = OfacProvider()
    # Force cache path under tmp
    assert provider.available() is False
    get_settings.cache_clear()
