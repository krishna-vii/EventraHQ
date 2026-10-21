"""Setup safeguards: no live service credentials or mutations."""
import base64
import importlib.util
import json
from pathlib import Path
from urllib.parse import urlsplit, unquote

import pytest
from app.settings import Settings, validate_publishable_key

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location("supabase_setup", ROOT / "scripts/supabase_setup.py")
setup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(setup)
REF = "abcdefghijklmnopqrst"
POOL = "aws-0-ap-south-1.pooler.supabase.com"


@pytest.mark.parametrize("url", ["https://evil.example", "http://abcdefghijklmnopqrst.supabase.co", "https://abcdefghijklmnopqrst.supabase.co.evil.example", "https://secret@abcdefghijklmnopqrst.supabase.co", "https://abcdefghijklmnopqrst.supabase.co/other", "https://abcdefghijklmnopqrst.supabase.co?key=secret"])
def test_project_origin_rejects_unsafe_targets(url):
    with pytest.raises(ValueError):
        setup.project_ref(url)


def test_project_binding_and_session_pooler():
    assert setup.project_ref(f"https://{REF}.supabase.co/") == REF
    url = f"postgresql://postgres.{REF}:secret@{POOL}:5432/postgres?sslmode=verify-full"
    setup.validate_database(url, REF, "postgres")
    with pytest.raises(ValueError):
        setup.validate_database(url, "xxxxxxxxxxxxxxxxxxxx", "postgres")
    for unsafe in [url.replace("verify-full", "require"), url.replace(":5432", ":6543"), url + "&options=evil", url.replace(POOL, "attacker.example")]:
        with pytest.raises(ValueError):
            setup.validate_database(unsafe, REF, "postgres")
    runtime = setup.runtime_url(url, "a:b@c#d/?%")
    setup.validate_database(runtime, REF, "eventra_app")
    assert unquote(urlsplit(runtime).password) == "a:b@c#d/?%"
    assert urlsplit(runtime).username == f"eventra_app.{REF}"


def test_privileged_keys_are_rejected():
    for role in ["anon", "service_role", "authenticated"]:
        payload = base64.urlsafe_b64encode(json.dumps({"role": role}).encode()).decode().rstrip("=")
        token = "header." + payload + ".signature"
        if role == "anon":
            validate_publishable_key(token)
        else:
            with pytest.raises(ValueError):
                validate_publishable_key(token)
    validate_publishable_key("sb_publishable_" + "x" * 30)
    for key in ["sb_secret_" + "x" * 30, "invalid", "header.W10.signature"]:
        with pytest.raises(ValueError):
            validate_publishable_key(key)


def test_env_update_preserves_unrelated_secrets_without_duplicates(tmp_path):
    path = tmp_path / ".env"
    path.write_text("# Keep this\nRAZORPAY_KEY_SECRET='leave-me'\nDATABASE_URL=old\nexport DATABASE_URL=older\n", encoding="utf-8")
    setup.save_env({"DATABASE_URL": "new-value", "SUPABASE_URL": f"https://{REF}.supabase.co"}, path)
    actual = path.read_text()
    assert "RAZORPAY_KEY_SECRET='leave-me'" in actual
    assert actual.count("DATABASE_URL=") == 1
    assert "# Keep this" in actual
    assert not list(tmp_path.glob("*.tmp"))
    with pytest.raises(ValueError):
        setup.save_env({"DATABASE_URL": "bad\nINJECT=value"}, path)
    assert path.read_text() == actual


def test_migrations_have_single_outer_transaction():
    files = sorted((ROOT / "supabase/migrations").glob("*.sql"))
    assert len(files) >= 3
    for path in files:
        body = setup.migration_body(path.read_text(encoding="utf-8"))
        assert body.strip(), path.name
        assert not body.lstrip().lower().startswith("begin;")
        assert not body.strip().lower().endswith("commit;")
    # Additive role/permission migrations can be a single short statement.
    assert setup.migration_body("begin; select 1; commit;").strip() == "select 1;"
    with pytest.raises(ValueError):
        setup.migration_body("select 1;")
    with pytest.raises(ValueError):
        setup.migration_body("begin; select 1;")


def test_unconfigured_doctor_does_not_connect(capsys, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Must not contact services when credentials are missing")
    monkeypatch.setattr(setup, "auth_check", forbidden)
    assert setup.doctor(Settings()) is False
    assert "NOT CONNECTED" in capsys.readouterr().out


def test_missing_certificate_is_rejected():
    with pytest.raises(ValueError, match="DATABASE_SSLROOTCERT"):
        Settings(database_sslrootcert="/missing/eventra-ca.crt")
