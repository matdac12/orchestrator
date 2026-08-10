import sys
from pathlib import Path

import pytest

SKILL_DIR = Path(__file__).resolve().parents[1] / ".claude" / "skills" / "zafferano-bc"
sys.path.insert(0, str(SKILL_DIR))

import bc_probe  # noqa: E402


def test_choose_env_file_prefers_nearest_walking_up():
    present = {Path("/proj/sub/.env"), Path("/known/.env")}
    got = bc_probe.choose_env_file(
        Path("/proj/sub/deep"),
        [Path("/known/.env")],
        exists=lambda p: p in present,
    )
    assert got == Path("/proj/sub/.env")


def test_choose_env_file_falls_back_to_known_paths():
    present = {Path("/known/.env")}
    got = bc_probe.choose_env_file(
        Path("/elsewhere"),
        [Path("/known/.env")],
        exists=lambda p: p in present,
    )
    assert got == Path("/known/.env")


def test_choose_env_file_returns_none_when_nothing_exists():
    got = bc_probe.choose_env_file(
        Path("/elsewhere"), [Path("/known/.env")], exists=lambda p: False
    )
    assert got is None


def test_environ_wins_over_env_file():
    creds, missing = bc_probe.resolve_credentials(
        environ={"BC_TENANT_ID": "from-env", "BC_CLIENT_ID": "c", "BC_CLIENT_SECRET": "s"},
        env_values={"BC_TENANT_ID": "from-file"},
    )
    assert creds["BC_TENANT_ID"] == "from-env"
    assert missing == []


def test_defaults_applied_for_environment_and_company():
    creds, _ = bc_probe.resolve_credentials(
        environ={"BC_TENANT_ID": "t", "BC_CLIENT_ID": "c", "BC_CLIENT_SECRET": "s"},
        env_values={},
    )
    assert creds["BC_ENVIRONMENT"] == "IT-Prod"
    assert creds["BC_COMPANY"] == "Zafferano S.r.l."


def test_missing_keys_are_reported():
    _, missing = bc_probe.resolve_credentials(
        environ={"BC_TENANT_ID": "t"}, env_values={}
    )
    assert sorted(missing) == ["BC_CLIENT_ID", "BC_CLIENT_SECRET"]


def test_credential_error_message_never_leaks_the_secret():
    err = bc_probe.CredentialError(missing=["BC_CLIENT_ID"], source="/some/.env")
    rendered = str(err)
    assert "BC_CLIENT_ID" in rendered
    assert "/some/.env" in rendered


def test_filter_names_is_case_insensitive_substring():
    names = ["Articoli", "Price_ListLines", "Listini_prezzi_vendita_righe"]
    # case-insensitive: minuscolo trova il CamelCase
    assert bc_probe.filter_names(names, "listlines") == ["Price_ListLines"]
    # ed e' sottostringa esatta: "listi" non compare in "price_listlines"
    assert bc_probe.filter_names(names, "listi") == ["Listini_prezzi_vendita_righe"]


def test_filter_names_without_pattern_returns_all():
    names = ["A", "B"]
    assert bc_probe.filter_names(names, None) == ["A", "B"]


METADATA_FIXTURE = b"""<?xml version="1.0" encoding="utf-8"?>
<edmx:Edmx xmlns:edmx="http://docs.oasis-open.org/odata/ns/edmx" Version="4.0">
 <edmx:DataServices>
  <Schema xmlns="http://docs.oasis-open.org/odata/ns/edm" Namespace="NAV">
   <EntityType Name="Articoli">
    <Key><PropertyRef Name="No"/></Key>
    <Property Name="No" Type="Edm.String" Nullable="false"/>
    <Property Name="Unit_Price" Type="Edm.Decimal" Nullable="true"/>
   </EntityType>
   <EntityType Name="DB_Righe">
    <Property Name="Production_BOM_No" Type="Edm.String" Nullable="false"/>
   </EntityType>
  </Schema>
 </edmx:DataServices>
</edmx:Edmx>
"""


def test_parse_entity_fields_extracts_names_types_nullable():
    parsed = bc_probe.parse_entity_fields(METADATA_FIXTURE)
    assert set(parsed) == {"Articoli", "DB_Righe"}
    assert parsed["Articoli"][0] == {
        "name": "No",
        "type": "Edm.String",
        "nullable": False,
    }
    assert parsed["Articoli"][1]["type"] == "Edm.Decimal"
    assert parsed["Articoli"][1]["nullable"] is True


def test_render_table_aligns_and_keeps_header():
    out = bc_probe.render_table(
        [{"name": "No", "type": "Edm.String"}, {"name": "Unit_Price", "type": "Edm.Decimal"}],
        ["name", "type"],
    )
    lines = out.splitlines()
    assert lines[0].split() == ["name", "type"]
    assert "Unit_Price" in lines[-1]
    assert len(lines[1].strip()) > 0  # riga separatrice


def test_suggest_names_catches_a_typo_substring_search_would_miss():
    names = ["Articoli", "Articoli_Statistici", "Fornitori"]
    # 'Articolii' non e' sottostringa di niente: serve il match fuzzy
    assert bc_probe.filter_names(names, "Articolii") == []
    assert "Articoli" in bc_probe.suggest_names("Articolii", names)


def test_suggest_names_still_returns_substring_matches():
    names = ["Price_ListLines", "Listini_prezzi_vendita_righe"]
    assert bc_probe.suggest_names("listini", names) == [
        "Listini_prezzi_vendita_righe"
    ]


def test_render_table_handles_empty_rows():
    assert bc_probe.render_table([], ["name"]) == "(nessuna riga)"


def test_urls_are_built_root_and_company():
    creds = {
        "BC_TENANT_ID": "TEN",
        "BC_ENVIRONMENT": "IT-Prod",
        "BC_COMPANY": "Zafferano S.r.l.",
    }
    assert bc_probe.root_url(creds) == (
        "https://api.businesscentral.dynamics.com/v2.0/TEN/IT-Prod/ODataV4/"
    )
    assert bc_probe.company_url(creds).endswith("ODataV4/Company('Zafferano S.r.l.')/")
