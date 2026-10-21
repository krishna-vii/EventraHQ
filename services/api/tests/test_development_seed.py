"""Development seeding safeguards; provider responses here are explicit doubles."""
import importlib.util
import json
from pathlib import Path
import sys
from uuid import uuid4

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))
spec = importlib.util.spec_from_file_location("seed_development", ROOT / "scripts/seed_development.py")
seed = importlib.util.module_from_spec(spec)
spec.loader.exec_module(seed)


@pytest.mark.parametrize("url,environment", [
    ("https://kqcevtlhhyxkjnxsjjcz.supabase.co", "production"),
    ("https://otherprojectabcdefgh.supabase.co", "local"),
    ("https://kqcevtlhhyxkjnxsjjcz.supabase.co.evil.example", "local"),
    ("http://kqcevtlhhyxkjnxsjjcz.supabase.co", "local"),
])
def test_seed_refuses_unapproved_environment_and_project(url, environment):
    with pytest.raises(ValueError):
        seed.guard_target(url, environment)


def test_dataset_is_labeled_deterministic_and_contains_no_credentials_or_reviews():
    first, second = seed.dataset(), seed.dataset()
    assert len(first["fixtures"]) == 120
    assert len(first["accounts"]) == 13
    assert first["fixtures"] == second["fixtures"]
    assert len({row["id"] for row in first["fixtures"]}) == 120
    assert len({row["city"] for row in first["fixtures"]}) == 5
    assert len({row["category"] for row in first["fixtures"]}) == 4
    assert all(row["name"].startswith("[SAMPLE]") for row in first["fixtures"])
    assert all(row["email"].endswith("@eventrahq.test") for row in first["accounts"])
    assert "password" not in json.dumps(first)
    assert seed.COUNTS["payments"] == seed.COUNTS["reviews"] == 0


def test_sql_payload_never_includes_passwords():
    state = seed.dataset()
    for account in state["accounts"]:
        account.update(id=str(uuid4()), password="private-test-value", login_verified=True)
    payload = seed.sql_manifest(state)
    assert "private-test-value" not in json.dumps(payload)
    assert "password" not in json.dumps(payload)
    assert all(set(account) == {"id", "email", "kind"} for account in payload["accounts"])


def test_private_state_save_is_atomic_and_preserves_generated_password(tmp_path):
    path = tmp_path / "mock-logins.json"
    seed.save_private(path, {"password": "private-test-value", "database_seeded": False})
    seed.save_private(path, {"password": "private-test-value", "database_seeded": True})
    assert json.loads(path.read_text())["database_seeded"] is True
    assert not list(tmp_path.glob("*.tmp"))


def test_existing_unrelated_account_is_never_adopted_or_reset(tmp_path):
    account = {"email": "customer01@eventrahq.test", "password": "private-test-value"}
    calls = []
    def handler(request):
        calls.append(request.method)
        return httpx.Response(200, json={"users": [{"id": str(uuid4()), "email": account["email"], "app_metadata": {}}]})
    with httpx.Client(base_url="https://project.supabase.co", transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ValueError, match="unrelated"):
            seed.provision_accounts(client, client, {"accounts": [account]}, tmp_path / "state.json")
    assert calls == ["GET"]


def test_auth_admin_provisioning_confirms_only_test_account_then_verifies_password(tmp_path):
    ident = str(uuid4())
    account = {"email": "customer01@eventrahq.test", "password": "private-test-value", "display_name": "[TEST] Customer"}
    seen = []
    def handler(request):
        seen.append((request.method, request.url.path))
        if request.url.path.endswith("admin/users"):
            if request.method == "GET":
                return httpx.Response(200, json={"users": []})
            body = json.loads(request.content)
            assert body["email_confirm"] is True
            assert body["password"] == account["password"]
            assert body["app_metadata"]["eventra_seed_id"] == seed.SEED_ID
            assert "role" not in body["user_metadata"]
            return httpx.Response(200, json={"id": ident})
        if request.url.path.endswith("token"):
            return httpx.Response(200, json={"access_token": "verified-provider-token"})
        assert request.headers["authorization"] == "Bearer verified-provider-token"
        return httpx.Response(200, json={"id": ident, "email": account["email"], "app_metadata": {"eventra_seed_id": seed.SEED_ID}})
    state = {"accounts": [account]}
    with httpx.Client(base_url="https://project.supabase.co", transport=httpx.MockTransport(handler)) as client:
        seed.provision_accounts(client, client, state, tmp_path / "state.json")
    assert account["login_verified"] is True and account["id"] == ident
    assert [method for method, _ in seen] == ["GET", "POST", "POST", "GET"]


def test_provider_error_never_prints_response_secrets():
    with httpx.Client(base_url="https://project.supabase.co", transport=httpx.MockTransport(
        lambda _: httpx.Response(403, json={"secret": "never-log-this"}))) as client:
        with pytest.raises(ValueError) as failure:
            seed.request_json(client, "GET", "/auth/v1/admin/users")
    assert "never-log-this" not in str(failure.value)


def test_login_verification_rejects_wrong_identity():
    account = {"id": str(uuid4()), "email": "customer01@eventrahq.test", "password": "private-test-value"}
    def handler(request):
        return httpx.Response(200, json={"access_token": "token"} if request.method == "POST" else
                              {"id": str(uuid4()), "email": account["email"], "app_metadata": {"eventra_seed_id": seed.SEED_ID}})
    with httpx.Client(base_url="https://project.supabase.co", transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ValueError, match="identity"):
            seed.verify_account(client, account, seed.SEED_ID)
