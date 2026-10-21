"""Explicit, interactive development bootstrap and read-only Supabase diagnostics.

No account provisioning, reset, seed, production migration or credential logging.
Run through the Node launcher to load the root .env using Node's native parser.
"""
from __future__ import annotations

import argparse
import getpass
import os
from pathlib import Path
import re
import secrets
import sys
import tempfile
from urllib.parse import quote, urlsplit, urlunsplit, parse_qs
import warnings

import certifi
import httpx
import psycopg
from psycopg import sql

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "api"))
from app.settings import Settings, validate_publishable_key  # noqa: E402
from app.persistence import Database  # noqa: E402


def project_ref(url: str) -> str:
    parsed = urlsplit(url)
    match = re.fullmatch(r"([a-z0-9]{20})\.supabase\.co", parsed.hostname or "")
    if not match or parsed.scheme != "https" or parsed.port not in (None, 443) or parsed.username or parsed.password or parsed.path not in ("", "/") or parsed.query or parsed.fragment:
        raise ValueError("Enter the exact HTTPS Supabase project URL from its dashboard.")
    return match[1]


def validate_database(url: str, ref: str, role: str) -> None:
    """Bind pooler username or direct hostname to the intended project."""
    u = urlsplit(url)
    direct = u.hostname == f"db.{ref}.supabase.co" and u.username == role
    pooled = bool(re.fullmatch(r"[a-z0-9-]+\.pooler\.supabase\.com", u.hostname or "")) and u.username == f"{role}.{ref}"
    if u.scheme != "postgresql" or not (direct or pooled) or u.port != 5432 or u.path != "/postgres" or not u.password or u.fragment or parse_qs(u.query) != {"sslmode": ["verify-full"]}:
        raise ValueError("Use this project's direct/session-pooler PostgreSQL URL on port 5432, the required role, and only sslmode=verify-full. Percent-encode the password.")


def runtime_url(admin_url: str, password: str) -> str:
    u = urlsplit(admin_url)
    suffix = u.username[len("postgres"):]
    return urlunsplit(("postgresql", f"eventra_app{suffix}:{quote(password, safe='')}@{u.hostname}:{u.port}", "/postgres", "sslmode=verify-full", ""))


def secret(prompt: str) -> str:
    if not sys.stdin.isatty():
        raise ValueError("Run setup in your own interactive terminal. Secrets cannot be piped or passed as arguments.")
    with warnings.catch_warnings():
        warnings.simplefilter("error", getpass.GetPassWarning)
        return getpass.getpass(prompt).strip()


def merge_env(original: str, updates: dict[str, str]) -> str:
    # Remove duplicate assignments only for our keys; preserve unrelated secrets/comments.
    remaining = dict(updates)
    lines = []
    for line in original.splitlines():
        match = re.match(r"^\s*(?:export\s+)?([A-Z][A-Z0-9_]*)\s*=", line)
        if match and match[1] in updates:
            continue
        lines.append(line)
    for key, value in remaining.items():
        if any(c in value for c in "\r\n\0'"):
            raise ValueError("Environment values must be single-line; URL-encode password punctuation.")
        lines.append(f"{key}='{value}'")
    return "\n".join(lines).rstrip() + "\n"


def save_env(updates: dict[str, str], path: Path | None = None) -> None:
    path = path or ROOT / ".env"
    if path.is_symlink():
        raise ValueError("Refusing to replace a symlinked environment file.")
    content = merge_env(path.read_text(encoding="utf-8") if path.exists() else "", updates)
    # Temporary file stays beside .env, under its existing directory ACL, never stdout.
    descriptor, temporary = tempfile.mkstemp(prefix=".env.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as output:
            output.write(content)
            output.flush()
            os.fsync(output.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def migration_body(source: str) -> str:
    # Checked-in migrations each have one outer transaction; execute all in one.
    match = re.fullmatch(r"\s*(?:--[^\n]*\n\s*)*begin\s*;(?P<body>.*)commit\s*;\s*", source, re.IGNORECASE | re.DOTALL)
    if not match:
        raise ValueError("Migration format changed. Review it instead of bootstrapping automatically.")
    return match["body"]


def auth_check(url: str, key: str) -> None:
    validate_publishable_key(key)
    with httpx.Client(timeout=10, trust_env=False, follow_redirects=False) as client:
        response = client.get(url + "/auth/v1/settings", headers={"apikey": key})
    if response.status_code != 200:
        raise ValueError("Supabase Auth rejected the key or is unavailable. Check this project's publishable key.")
    data = response.json()
    if data.get("disable_signup") or not data.get("external", {}).get("email"):
        raise ValueError("Enable email sign-up in Supabase Authentication before continuing.")
    if data.get("mailer_autoconfirm") is not False:
        raise ValueError("Enable email confirmation in Supabase Authentication before continuing.")


def setup(bootstrap: bool) -> None:
    if os.getenv("APP_ENV", "local") != "local":
        raise ValueError("This helper is only for local app development, never a production environment.")
    default = os.getenv("SUPABASE_URL", "")
    url = (input(f"Supabase project URL [{default}]: ").strip() or default).rstrip("/")
    ref = project_ref(url)
    key = secret("Supabase publishable (or legacy anon) key [hidden]: ")
    auth_check(url, key)
    cert = input("Downloaded database root CA file (Enter uses system CA bundle): ").strip().strip('"')
    if cert and not Path(cert).is_file():
        raise ValueError("Certificate file does not exist. Download it from Database Settings; never disable TLS verification.")
    ca = cert or certifi.where()
    if bootstrap:
        print("This adds EventraHQ tables, policies and a restricted runtime login to a fresh DEVELOPMENT database.")
        print("It refuses an existing app schema; it does not reset, delete records, import sample artists or provision resources.")
        if input(f"Type development {ref} to approve this exact target: ").strip() != f"development {ref}":
            raise ValueError("Development target confirmation did not match. No database changes made.")
        admin_url = secret("Postgres admin direct/session URL with sslmode=verify-full [hidden]: ")
        validate_database(admin_url, ref, "postgres")
        password = secrets.token_urlsafe(36)
        db_url = runtime_url(admin_url, password)
        migrations = sorted((ROOT / "supabase/migrations").glob("*.sql"))
        bodies = [(path, migration_body(path.read_text(encoding="utf-8"))) for path in migrations]
        # No admin URL/password is written to disk. Abort the entire schema on error.
        with psycopg.connect(admin_url, sslrootcert=ca, connect_timeout=10, prepare_threshold=None) as conn:
            conn.execute("set local statement_timeout='60s'")
            conn.execute("set local lock_timeout='5s'")
            conn.execute("select pg_advisory_xact_lock(19261019)")
            if conn.execute("select to_regnamespace('app') is not null or exists(select 1 from pg_roles where rolname='eventra_app')").fetchone()[0]:
                raise ValueError("Existing EventraHQ schema/login detected. Use configure for an installed database; review incremental migrations separately.")
            if not conn.execute("select to_regclass('auth.users') is not null and to_regclass('storage.buckets') is not null").fetchone()[0]:
                raise ValueError("The target is not a ready Supabase database.")
            # Preserve unrelated migration history; never overwrite a recorded version.
            conn.execute("create schema if not exists supabase_migrations")
            conn.execute("create table if not exists supabase_migrations.schema_migrations(version text primary key, statements text[], name text)")
            for path, body in bodies:
                version, name = path.stem.split("_", 1)
                if conn.execute("select 1 from supabase_migrations.schema_migrations where version=%s", (version,)).fetchone():
                    raise ValueError("A migration version already exists. Stop and inspect history; nothing was overwritten.")
                conn.execute(body, prepare=False)
                conn.execute("insert into supabase_migrations.schema_migrations(version,statements,name) values(%s,%s,%s)", (version, [path.read_text(encoding="utf-8")], name))
            conn.execute(sql.SQL("alter role eventra_app password {}").format(sql.Literal(password)))
        print("Development schema committed. No fictional listings were inserted.")
    else:
        db_url = secret("Restricted eventra_app direct/session database URL [hidden]: ")
        validate_database(db_url, ref, "eventra_app")
    config = Settings(database_url=db_url, database_sslrootcert=cert, supabase_url=url, supabase_key=key, allow_managed_services=True)
    updates = {"APP_ENV": "local", "APP_ORIGIN": "http://127.0.0.1:3000", "ALLOW_MANAGED_SERVICES": "true", "SUPABASE_URL": url, "SUPABASE_PUBLISHABLE_KEY": key, "DATABASE_URL": db_url, "DATABASE_SSLROOTCERT": cert}
    # Save the generated password before the pooler login probe, which can lag role creation.
    # Bootstrap committed at this point: preserve credentials even if a subsequent check fails.
    save_env(updates)
    print("Saved backend settings to the ignored root .env. No administrator credentials were saved.")
    if not doctor(config):
        raise ValueError("Connection checks are incomplete. Settings are saved; inspect the checks and rerun npm run supabase:check.")
    print("Connection checks passed. Finish dashboard email templates and the real two-account acceptance checklist in docs/SUPABASE_SETUP.md.")


def doctor(settings: Settings | None = None) -> bool:
    settings = settings or Settings.from_environment()
    missing = [name for name, value in [("SUPABASE_URL", settings.supabase_url), ("SUPABASE_PUBLISHABLE_KEY", settings.supabase_key), ("DATABASE_URL", settings.database_url)] if not value]
    if missing:
        print("NOT CONNECTED: missing " + ", ".join(missing) + ". Run npm run supabase:setup in your own terminal.")
        return False
    try:
        auth_check(settings.supabase_url, settings.supabase_key)
        print("PASS: Auth reachable; publishable key accepted; email confirmation enabled.")
        with Database(settings).connect() as conn:
            role = conn.execute("select rolcreatedb,rolcreaterole,rolinherit,exists(select 1 from pg_auth_members m where m.member=r.oid) from pg_roles r where rolname=current_user").fetchone()
            if any(role):
                raise ValueError("Runtime role has excessive privileges or membership.")
            tables = conn.execute("select count(*),count(*) filter(where not relrowsecurity) from pg_class c join pg_namespace n on n.oid=c.relnamespace where n.nspname='app' and c.relkind in ('r','p')").fetchone()
            if tables[0] < 27 or tables[1]:
                raise ValueError("App tables are missing or Row Level Security is disabled.")
            extensions = {r[0] for r in conn.execute("select extname from pg_extension")}
            if not {"postgis", "vector", "btree_gist"}.issubset(extensions):
                raise ValueError("Required database extensions are missing.")
            acl = conn.execute("select has_function_privilege('eventra_app','app.marketplace_command(text,jsonb)','execute'),has_function_privilege('anon','app.marketplace_command(text,jsonb)','execute'),has_function_privilege('authenticated','app.marketplace_command(text,jsonb)','execute')").fetchone()
            if acl != (True, False, False):
                raise ValueError("Marketplace command grants do not match the server-only boundary.")
            if conn.execute("select count(*) from app.profiles").fetchone()[0] != 0:
                raise ValueError("Anonymous runtime identity can see private profiles.")
            conn.execute("select id from public.artist_marketplace limit 1")
            policies = {r[0] for r in conn.execute("select policyname from pg_policies where schemaname='storage' and tablename='objects'")}
            if not {"eventra_portfolio_read", "eventra_portfolio_insert", "eventra_portfolio_delete"}.issubset(policies):
                raise ValueError("Portfolio Storage policies are missing.")
        print("PASS: restricted database login, extensions, RLS, private-row isolation, command grants and catalogue projection.")
        print("PASS: portfolio policy definitions exist. Actual upload/download and bucket configuration still require the acceptance checklist.")
        return True
    except (ValueError, psycopg.Error, httpx.HTTPError) as error:
        if isinstance(error, ValueError):
            print("FAIL: " + str(error))
        else:
            print("FAIL: service connection/query failed (" + type(error).__name__ + "). Check project status, password, certificate and migrations. No credentials were logged.")
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("bootstrap", "configure", "check"))
    args = parser.parse_args()
    try:
        if args.action == "check":
            return 0 if doctor() else 1
        setup(args.action == "bootstrap")
        return 0
    except (ValueError, psycopg.Error, httpx.HTTPError, OSError, EOFError, getpass.GetPassWarning) as error:
        # Provider/SQL error strings can contain connection strings or literal passwords.
        message = str(error) if isinstance(error, ValueError) else type(error).__name__ + ": setup stopped; verify connection/certificate/schema permissions. No credentials logged."
        print("SETUP INCOMPLETE: " + message)
        return 1
    except KeyboardInterrupt:
        print("\nSetup cancelled.")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
