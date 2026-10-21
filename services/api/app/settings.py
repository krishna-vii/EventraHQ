"""Fail closed on configuration that could leave the workstation."""

from dataclasses import dataclass
from ipaddress import ip_address
import os
import base64
import json
from pathlib import Path
from urllib.parse import urlsplit, parse_qs


def validate_publishable_key(key: str) -> None:
    """Reject privileged keys. This shape check never authenticates a user."""
    if key.startswith("sb_publishable_") and len(key) > 25 and not any(c.isspace() for c in key):
        return
    try:
        payload = key.split(".")[1]
        claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
        if len(key.split(".")) == 3 and claims.get("role") == "anon":
            return
    except (ValueError, IndexError, TypeError, AttributeError):
        pass
    raise ValueError("Use a Supabase publishable key or legacy anon key, never a secret/service_role key.")


def loopback_host(host: str | None) -> bool:
    # Do not resolve arbitrary DNS names: that would admit DNS rebinding.
    if host == "localhost":
        return True
    try:
        return ip_address(host or "").is_loopback
    except ValueError:
        return False


@dataclass(frozen=True)
class Settings:
    app_env: str = "local"
    app_origin: str = "http://127.0.0.1:3000"
    inference_base_url: str = "http://127.0.0.1:11434"
    inference_model: str = "qwen3.5:4b"
    database_url: str | None = None
    database_sslrootcert: str = ""
    queue_wait_seconds: float = 30
    generation_timeout_seconds: float = 120
    supabase_url: str = ""
    supabase_key: str = ""
    allow_managed_services: bool = False
    inference_provider: str = "ollama"
    hosted_ai_url: str = ""
    hosted_ai_key: str = ""
    hosted_ai_model: str = ""
    razorpay_key_id: str = ""
    razorpay_key_secret: str = ""
    razorpay_webhook_secret: str = ""
    api_hostname: str = ""

    def __post_init__(self) -> None:
        if self.app_env not in ("local", "staging", "production"):
            raise ValueError("Unknown APP_ENV.")
        if self.app_env == "local" and self.app_origin != "http://127.0.0.1:3000":
            raise ValueError("APP_ORIGIN must use the canonical loopback gateway.")
        if self.app_env != "local" and (urlsplit(self.app_origin).scheme != "https" or not self.database_url or not self.supabase_url or not self.supabase_key or not self.api_hostname):
            raise ValueError("Hosted environments require HTTPS APP_ORIGIN, API_HOSTNAME, database and Supabase configuration.")
        origin = urlsplit(self.app_origin)
        if not origin.hostname or origin.username or origin.password or origin.path or origin.query or origin.fragment:
            raise ValueError("APP_ORIGIN must be a plain origin without credentials, path or query.")
        if self.api_hostname and any(c not in 'abcdefghijklmnopqrstuvwxyz0123456789.-' for c in self.api_hostname):
            raise ValueError("API_HOSTNAME must be an exact lowercase hostname, never a wildcard.")
        if self.supabase_url:
            u = urlsplit(self.supabase_url)
            local = u.scheme == "http" and loopback_host(u.hostname) and u.port == 54321
            managed = self.allow_managed_services and u.scheme == "https" and (u.hostname or "").endswith(".supabase.co")
            if not (local or managed) or u.username or u.password or u.query or u.fragment or u.path not in ("", "/"):
                raise ValueError("Supabase must be local or an explicitly enabled managed Supabase origin.")
        if self.database_sslrootcert and not Path(self.database_sslrootcert).is_file():
            raise ValueError("DATABASE_SSLROOTCERT must point to the downloaded database CA certificate file.")
        if self.inference_provider not in ("ollama", "hosted"):
            raise ValueError("Unknown inference provider.")
        if self.inference_provider == "hosted":
            u = urlsplit(self.hosted_ai_url)
            if not self.allow_managed_services or u.scheme != "https" or not u.hostname or u.username or u.password or u.query or u.fragment or not self.hosted_ai_key or not self.hosted_ai_model:
                raise ValueError("Hosted AI requires explicit HTTPS endpoint, model, credentials and managed-services opt-in.")
        if self.razorpay_key_id and not self.razorpay_key_id.startswith("rzp_test_"):
            raise ValueError("Only Razorpay test keys are enabled; live payments require a separate release review.")
        model_url = urlsplit(self.inference_base_url)
        if (
            model_url.scheme != "http"
            or not loopback_host(model_url.hostname)
            or model_url.username or model_url.password
            or model_url.path not in ("", "/")
            or model_url.query or model_url.fragment
            or model_url.port is None
        ):
            raise ValueError("INFERENCE_BASE_URL must be an HTTP loopback origin with an explicit port.")
        if self.inference_model != "qwen3.5:4b":
            raise ValueError("Only the qualified initial model profile qwen3.5:4b is allowlisted.")
        if not 0 < self.queue_wait_seconds <= 30 or not 0 < self.generation_timeout_seconds <= 120:
            raise ValueError("Inference timeout limits exceed the workstation policy.")
        if self.database_url:
            database_url = urlsplit(self.database_url)
            if database_url.username != 'eventra_app' and not (database_url.username or '').startswith('eventra_app.'):
                raise ValueError("DATABASE_URL must use the restricted eventra_app database role.")
            managed_db = (self.allow_managed_services and (database_url.hostname or "").endswith((".supabase.co", ".pooler.supabase.com")) and database_url.port in (5432, 6543) and parse_qs(database_url.query) == {"sslmode": ["verify-full"]})
            if (
                database_url.scheme not in ("postgresql", "postgresql+psycopg")
                or not (managed_db or (loopback_host(database_url.hostname) and database_url.port == 54322 and not database_url.query))
                or database_url.fragment
            ):
                raise ValueError("DATABASE_URL must target local PostgreSQL on port 54322 without URL options.")

    @classmethod
    def from_environment(cls) -> "Settings":
        if os.getenv("SUPABASE_PUBLISHABLE_KEY"):
            validate_publishable_key(os.environ["SUPABASE_PUBLISHABLE_KEY"])
        return cls(
            app_env=os.getenv("APP_ENV", "local"),
            app_origin=os.getenv("APP_ORIGIN", "http://127.0.0.1:3000"),
            inference_base_url=os.getenv("INFERENCE_BASE_URL", "http://127.0.0.1:11434"),
            inference_model=os.getenv("INFERENCE_MODEL", "qwen3.5:4b"),
            database_url=os.getenv("DATABASE_URL") or None,
            database_sslrootcert=os.getenv("DATABASE_SSLROOTCERT", ""),
            supabase_url=os.getenv("SUPABASE_URL", "").rstrip("/"),
            supabase_key=os.getenv("SUPABASE_PUBLISHABLE_KEY", ""),
            allow_managed_services=os.getenv("ALLOW_MANAGED_SERVICES") == "true",
            inference_provider=os.getenv("INFERENCE_PROVIDER", "ollama"),
            hosted_ai_url=os.getenv("HOSTED_AI_URL", ""),
            hosted_ai_key=os.getenv("HOSTED_AI_KEY", ""),
            hosted_ai_model=os.getenv("HOSTED_AI_MODEL", ""),
            razorpay_key_id=os.getenv("RAZORPAY_KEY_ID", ""),
            razorpay_key_secret=os.getenv("RAZORPAY_KEY_SECRET", ""),
            razorpay_webhook_secret=os.getenv("RAZORPAY_WEBHOOK_SECRET", ""),
            api_hostname=os.getenv("API_HOSTNAME", ""),
        )
