"""Bind login transactions and enforce valid session tenant membership.

Revision ID: 0002_identity_binding
Revises: 0001_identity_multitenancy
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0002_identity_binding"
down_revision: str | None = "0001_identity_multitenancy"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE oidc_login_transactions DISABLE ROW LEVEL SECURITY;
        DELETE FROM oidc_login_transactions;
        ALTER TABLE oidc_login_transactions
            ADD COLUMN login_binding_hash bytea NOT NULL
            CHECK (octet_length(login_binding_hash) = 32);
        ALTER TABLE oidc_login_transactions ENABLE ROW LEVEL SECURITY;
        ALTER TABLE oidc_login_transactions FORCE ROW LEVEL SECURITY;

        DROP POLICY sessions_by_secret ON application_sessions;
        CREATE POLICY sessions_by_secret ON application_sessions
            USING (
                encode(token_hash, 'hex') = current_setting('app.session_hash', true)
                OR user_id = NULLIF(current_setting('app.user_id', true), '')::uuid
            )
            WITH CHECK (
                user_id = NULLIF(current_setting('app.user_id', true), '')::uuid
                AND (
                    current_tenant_id IS NULL
                    OR EXISTS (
                        SELECT 1
                        FROM memberships m
                        WHERE m.tenant_id = application_sessions.current_tenant_id
                          AND m.user_id = application_sessions.user_id
                          AND m.status = 'active'
                    )
                )
            );
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP POLICY sessions_by_secret ON application_sessions;
        CREATE POLICY sessions_by_secret ON application_sessions
            USING (
                encode(token_hash, 'hex') = current_setting('app.session_hash', true)
                OR user_id = NULLIF(current_setting('app.user_id', true), '')::uuid
            )
            WITH CHECK (user_id = NULLIF(current_setting('app.user_id', true), '')::uuid);

        ALTER TABLE oidc_login_transactions DISABLE ROW LEVEL SECURITY;
        ALTER TABLE oidc_login_transactions DROP COLUMN login_binding_hash;
        ALTER TABLE oidc_login_transactions ENABLE ROW LEVEL SECURITY;
        ALTER TABLE oidc_login_transactions FORCE ROW LEVEL SECURITY;
        """
    )
