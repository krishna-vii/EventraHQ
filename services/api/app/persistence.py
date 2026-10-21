"""Short, parameterized transactions using a non-owner runtime role and verified identity."""
import asyncio
import json
import logging
from uuid import UUID

import psycopg
import certifi
from fastapi import HTTPException
from .settings import Settings

logger = logging.getLogger("eventrahq")


class Database:
    def __init__(self, settings: Settings):
        self.url = settings.database_url
        self.sslrootcert = settings.database_sslrootcert or certifi.where()

    def connect(self, actor: str | None = None):
        if not self.url:
            raise HTTPException(503, "Account data requires a configured Supabase database. See docs/DEPLOYMENT.md.")
        conn = psycopg.connect(self.url.replace("postgresql+psycopg://", "postgresql://", 1), connect_timeout=5, prepare_threshold=None, **({"sslrootcert": self.sslrootcert} if "sslmode=verify-full" in self.url else {}))
        try:
            # Reject accidental owner/service credentials before handling user data.
            role = conn.execute("select current_user, rolsuper, rolbypassrls from pg_roles where rolname=current_user").fetchone()
            if role[0] != "eventra_app" or role[1] or role[2]:
                raise HTTPException(503, "Runtime database credentials must use the restricted eventra_app role.")
            conn.execute("select set_config('request.jwt.claim.sub', %s, true)", (str(UUID(actor)) if actor else "",))
            conn.execute("set local statement_timeout='5000ms'")
            conn.execute("set local lock_timeout='3000ms'")
            return conn
        except Exception:
            conn.close()
            raise

    def _call(self, action: str, payload: dict, actor: str | None):
        with self.connect(actor) as conn:
            return conn.execute("select app.marketplace_command(%s, %s::jsonb)", (action, json.dumps(payload))).fetchone()[0]

    async def call(self, action: str, payload: dict | None = None, actor: str | None = None):
        try:
            return await asyncio.to_thread(self._call, action, payload or {}, actor)
        except HTTPException:
            raise
        except psycopg.errors.InsufficientPrivilege:
            raise HTTPException(403, "You do not have permission for this action.")
        except (psycopg.errors.ExclusionViolation, psycopg.errors.UniqueViolation):
            raise HTTPException(409, "This action conflicts with an existing record or reservation. Refresh and try again.")
        except (psycopg.errors.CheckViolation, psycopg.errors.RaiseException, psycopg.errors.NoDataFound):
            raise HTTPException(409, "The record is unavailable, expired, or cannot make this transition. Refresh and check the details.")
        except (psycopg.errors.InvalidTextRepresentation, psycopg.errors.NotNullViolation, psycopg.errors.ForeignKeyViolation):
            raise HTTPException(422, "Check the submitted record and required fields.")
        except psycopg.Error as exc:
            logger.error("database_operation_failed action=%s sqlstate=%s", action, exc.sqlstate)
            raise HTTPException(503, "The database could not complete this operation. Verify migrations and retry.") from None
