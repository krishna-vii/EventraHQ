"""Explicit, resumable development seed. Privileged credentials are never saved."""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import secrets
import sys
import tempfile
from uuid import UUID, uuid5

import certifi
import httpx
import psycopg

from supabase_setup import ROOT, migration_body, project_ref, secret, validate_database

PROJECT = "kqcevtlhhyxkjnxsjjcz"
SEED_ID = str(uuid5(UUID("02f07400-c803-47eb-b9ac-9f23961e56eb"), PROJECT + ":development-v1"))
COUNTS = dict(accounts=13, fixture_artists=120, interactive_test_artists=8, availability_windows=80,
              events=60, conversations=60, messages=240, quotes=60, saved_artists=32,
              pending_bookings=8, payments=0, reviews=0)
STATE_FILE = ROOT / ".runtime" / "mock-logins.json"


def guard_target(url: str, environment: str) -> None:
    if environment != "local" or project_ref(url) != PROJECT:
        raise ValueError("Seeding is limited to APP_ENV=local and the approved EventraHQ development project.")


def dataset() -> dict:
    categories = ["Live band", "DJ", "Vocalist", "Instrumental"]
    cities = ["Mumbai", "Bengaluru", "Delhi", "Pune", "Jaipur"]
    genres = [["Indie", "Hindi"], ["House", "Bollywood"], ["Acoustic", "Sufi"], ["Jazz", "Violin"]]
    occasions = ["Wedding", "Corporate event", "Private party", "Festival"]
    accounts = [dict(email=f"{kind}{i:02}@eventrahq.test", kind=kind, display_name=f"[TEST] {kind.title()} {i:02}")
                for kind, count in [("customer", 4), ("artist", 8), ("admin", 1)] for i in range(1, count + 1)]
    fixtures = [dict(id=str(uuid5(UUID(SEED_ID), f"fixture-{i}")), slug=f"eventra-sample-{i:03}",
        name=f"[SAMPLE] {categories[i % 4]} {i:03}", category=categories[i % 4], city=cities[i % 5],
        price_paise=1000000 + (i % 30) * 500000, tags=genres[i % 4],
        tagline=f"Fictional {categories[i % 4].lower()} listing for marketplace testing.",
        description="SAMPLE DATA ONLY. This fictional artist and illustrative price exist for discovery testing. Photos illustrate a performance style. This listing cannot receive bookings.",
        event_types=[occasions[i % 4], occasions[(i + 1) % 4]]) for i in range(1, 121)]
    base = (datetime.now(timezone.utc) + timedelta(days=3)).replace(hour=0, minute=0, second=0, microsecond=0)
    return dict(project_ref=PROJECT, seed_id=SEED_ID, base_date=base.isoformat(), accounts=accounts, fixtures=fixtures)


def save_private(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise ValueError("Refusing a symlinked credential file.")
    fd, temporary = tempfile.mkstemp(prefix="mock-logins-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as output:
            json.dump(data, output, indent=2)
            output.flush()
            os.fsync(output.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def request_json(client, method, path, **kwargs):
    response = client.request(method, path, **kwargs)
    if not 200 <= response.status_code < 300:
        raise ValueError(f"Supabase account request failed (HTTP {response.status_code}); no provider payload logged. Check the key, target and account status privately.")
    data = response.json()
    if not isinstance(data, dict):
        raise ValueError("Invalid account response.")
    return data


def verify_account(client, account, seed_id):
    data = request_json(client, "POST", "/auth/v1/token?grant_type=password",
                        json={"email": account["email"], "password": account["password"]})
    token = data.get("access_token")
    if not isinstance(token, str) or not token:
        raise ValueError("Account login did not return a session.")
    user = request_json(client, "GET", "/auth/v1/user", headers={"Authorization": f"Bearer {token}"})
    if user.get("id") != account["id"] or user.get("email") != account["email"] or user.get("app_metadata", {}).get("eventra_seed_id") != seed_id:
        raise ValueError("Seed account identity does not match; existing users will not be changed.")
    return True


def provision_accounts(admin, public, state, path):
    # Never reset a password or adopt an account that happens to have the same email.
    users = {}
    for page in range(1, 101):
        result = request_json(admin, "GET", "/auth/v1/admin/users", params={"page": page, "per_page": 100})
        batch = result.get("users")
        if not isinstance(batch, list):
            raise ValueError("Unable to inspect existing Auth users.")
        users.update({user["email"]: user for user in batch if user.get("email")})
        if len(batch) < 100:
            break
    else:
        raise ValueError("Development user listing exceeded the safety limit.")
    for account in state["accounts"]:
        existing = users.get(account["email"])
        if existing:
            if existing.get("app_metadata", {}).get("eventra_seed_id") != SEED_ID:
                raise ValueError("A seed email belongs to an unrelated account. No existing account was modified.")
            if account.get("id") and account["id"] != existing["id"]:
                raise ValueError("Saved account identity differs from the provider.")
            account["id"] = existing["id"]
        else:
            user = request_json(admin, "POST", "/auth/v1/admin/users", json={
                "email": account["email"], "password": account["password"], "email_confirm": True,
                "user_metadata": {"display_name": account["display_name"]},
                "app_metadata": {"eventra_seed_id": SEED_ID, "test_account": True},
            })
            account["id"] = str(UUID(user["id"]))
        account["login_verified"] = verify_account(public, account, SEED_ID)
        save_private(path, state)


def sql_manifest(state):
    """Passwords never enter SQL, audit metadata, process arguments or logs."""
    return {**dataset(), "base_date": state["base_date"], "accounts": [
        {key: account[key] for key in ("id", "email", "kind")} for account in state["accounts"]]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", action="store_true", help="Print counts only; no credentials or remote actions.")
    args = parser.parse_args()
    if args.plan:
        print(json.dumps({"project": PROJECT, "planned": COUNTS, "inserted": False}, indent=2))
        return
    url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    guard_target(url, os.environ.get("APP_ENV", "local"))
    publishable = os.environ.get("SUPABASE_PUBLISHABLE_KEY", "")
    if not publishable:
        raise ValueError("Configure the existing project connection first.")
    if not sys.stdin.isatty():
        raise ValueError("Run npm run seed:development in your own interactive terminal for hidden credential entry.")
    print(f"Target: {url}. Adds labeled test data and 13 confirmed TEST accounts. Sends no emails.")
    print(json.dumps(COUNTS, indent=2))
    if input(f"Type seed development {PROJECT} to continue: ").strip() != f"seed development {PROJECT}":
        raise ValueError("No seed authorized.")
    admin_key = secret("Supabase secret (or legacy service_role) key [hidden]: ")
    admin_url = secret("Postgres admin direct/session URL with sslmode=verify-full [hidden]: ")
    validate_database(admin_url, PROJECT, "postgres")
    if not admin_key or admin_key == publishable or admin_key.startswith("sb_publishable_"):
        raise ValueError("Use the server-only administrative key for this one-off setup.")
    headers = {"apikey": admin_key}
    if not admin_key.startswith("sb_secret_"):
        headers["Authorization"] = f"Bearer {admin_key}"
    ca = os.environ.get("DATABASE_SSLROOTCERT") or certifi.where()
    with psycopg.connect(admin_url, sslrootcert=ca, connect_timeout=10, prepare_threshold=None) as conn:
        role, schema = conn.execute("select current_user, to_regnamespace('app') is not null").fetchone()
        if role != "postgres" or not schema:
            raise ValueError("Expected an installed development schema and maintenance login.")
        conn.commit()
        with httpx.Client(base_url=url, headers=headers, timeout=20, trust_env=False, follow_redirects=False) as admin, \
             httpx.Client(base_url=url, headers={"apikey": publishable}, timeout=20, trust_env=False, follow_redirects=False) as public:
            request_json(admin, "GET", "/auth/v1/admin/users", params={"page": 1, "per_page": 1})
            if STATE_FILE.exists():
                state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
                if state.get("seed_id") != SEED_ID or state.get("project_ref") != PROJECT:
                    raise ValueError("Existing seed state targets another dataset; refusing to overwrite it.")
            else:
                state = dataset()
                state.pop("fixtures")
                state["database_seeded"] = False
                for account in state["accounts"]:
                    account.update(password=secrets.token_urlsafe(24), login_verified=False)
                save_private(STATE_FILE, state)
            if not state.get("database_seeded") and datetime.fromisoformat(state["base_date"]) <= datetime.now(timezone.utc):
                state["base_date"] = dataset()["base_date"]
                save_private(STATE_FILE, state)
            provision_accounts(admin, public, state, STATE_FILE)
        with conn.transaction():
            conn.execute("set local statement_timeout='120s'")
            conn.execute("select set_config('eventra.seed_manifest',%s,true)", (json.dumps(sql_manifest(state)),))
            conn.execute(migration_body((ROOT / "scripts/seed-development.sql").read_text(encoding="utf-8")))
            result = conn.execute("select metadata from app.audit_log where action='development.seed.completed' and entity_id=%s", (SEED_ID,)).fetchone()
            if not result:
                raise ValueError("Seed completion marker missing; database transaction rolled back.")
        state["database_seeded"] = True
        state["counts"] = COUNTS
        save_private(STATE_FILE, state)
    print("Seed completed; all 13 Auth password logins verified. Payments/reviews were not created.")
    print(f"Open {STATE_FILE} locally for the customer, artist and admin test login credentials.")
    print("Use http://127.0.0.1:3000/login. Existing pending-payment holds last 15 minutes; other quotes remain available for testing.")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, KeyError, OSError, psycopg.Error, httpx.HTTPError) as error:
        # HTTP/SQL exception details can contain secret request or connection values.
        print(str(error) if type(error) is ValueError else "Setup stopped. Connection/provider details suppressed to protect credentials.", file=sys.stderr)
        print("No existing users were reset. Auth accounts already created remain recorded in .runtime/mock-logins.json; business data commits atomically. Rerun with the same file to resume.", file=sys.stderr)
        sys.exit(1)
