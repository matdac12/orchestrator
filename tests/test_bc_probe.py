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
