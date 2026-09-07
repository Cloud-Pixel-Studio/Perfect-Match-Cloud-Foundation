"""Establish identity, sessions, tenant membership, and forced RLS.

Revision ID: 0001_identity_multitenancy
Revises:
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0001_identity_multitenancy"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


DDL = r"""
CREATE TABLE tenants (
    id uuid PRIMARY KEY,
    name varchar(160) NOT NULL,
    slug varchar(80) NOT NULL UNIQUE,
    status varchar(20) NOT NULL CHECK (status IN ('active', 'disabled')),
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL
);

CREATE TABLE users (
    id uuid PRIMARY KEY,
    display_name varchar(160) NOT NULL,
    email varchar(320),
    status varchar(20) NOT NULL CHECK (status IN ('active', 'disabled')),
    created_at timestamptz NOT NULL,
    last_login_at timestamptz
);

CREATE TABLE external_identities (
    id uuid PRIMARY KEY,
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    issuer varchar(500) NOT NULL,
    subject varchar(255) NOT NULL,
    created_at timestamptz NOT NULL,
    UNIQUE (issuer, subject)
);

CREATE TABLE memberships (
    id uuid PRIMARY KEY,
    tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role varchar(20) NOT NULL CHECK (role IN ('owner', 'admin', 'member', 'auditor')),
    status varchar(20) NOT NULL CHECK (status IN ('active', 'revoked')),
    created_at timestamptz NOT NULL,
    UNIQUE (tenant_id, user_id)
);

CREATE TABLE application_sessions (
    id uuid PRIMARY KEY,
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash bytea NOT NULL UNIQUE CHECK (octet_length(token_hash) = 32),
    current_tenant_id uuid REFERENCES tenants(id),
    csrf_token_hash bytea NOT NULL CHECK (octet_length(csrf_token_hash) = 32),
    created_at timestamptz NOT NULL,
    expires_at timestamptz NOT NULL,
    last_seen_at timestamptz NOT NULL,
    revoked_at timestamptz
);

CREATE TABLE oidc_login_transactions (
    id uuid PRIMARY KEY,
    state_hash bytea NOT NULL UNIQUE CHECK (octet_length(state_hash) = 32),
    encrypted_pkce_verifier bytea NOT NULL,
    nonce varchar(255) NOT NULL,
    created_at timestamptz NOT NULL,
    expires_at timestamptz NOT NULL,
    used_at timestamptz
);

CREATE TABLE tenant_isolation_probes (
    id uuid PRIMARY KEY,
    tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    value varchar(160) NOT NULL,
    created_at timestamptz NOT NULL
);

CREATE INDEX memberships_user_status_idx ON memberships (user_id, status);
CREATE INDEX memberships_tenant_status_idx ON memberships (tenant_id, status);
CREATE INDEX tenant_isolation_probes_tenant_idx ON tenant_isolation_probes (tenant_id);

REVOKE CREATE ON SCHEMA public FROM PUBLIC;
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO pmcloud_app;

GRANT SELECT, INSERT, UPDATE ON users TO pmcloud_app;
GRANT SELECT, INSERT ON external_identities TO pmcloud_app;
GRANT SELECT ON tenants, memberships TO pmcloud_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON application_sessions TO pmcloud_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON oidc_login_transactions TO pmcloud_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON tenant_isolation_probes TO pmcloud_app;

ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE users FORCE ROW LEVEL SECURITY;
CREATE POLICY users_self ON users
    USING (id = NULLIF(current_setting('app.user_id', true), '')::uuid)
    WITH CHECK (id = NULLIF(current_setting('app.user_id', true), '')::uuid);

ALTER TABLE external_identities ENABLE ROW LEVEL SECURITY;
ALTER TABLE external_identities FORCE ROW LEVEL SECURITY;
CREATE POLICY external_identity_subject ON external_identities
    USING (
        issuer = current_setting('app.issuer', true)
        AND subject = current_setting('app.subject', true)
    )
    WITH CHECK (
        issuer = current_setting('app.issuer', true)
        AND subject = current_setting('app.subject', true)
        AND user_id = NULLIF(current_setting('app.user_id', true), '')::uuid
    );

ALTER TABLE tenants ENABLE ROW LEVEL SECURITY;
ALTER TABLE tenants FORCE ROW LEVEL SECURITY;
CREATE POLICY tenants_active_membership ON tenants FOR SELECT USING (
    status = 'active' AND EXISTS (
        SELECT 1 FROM memberships m
        WHERE m.tenant_id = tenants.id
          AND m.user_id = NULLIF(current_setting('app.user_id', true), '')::uuid
          AND m.status = 'active'
    )
);

ALTER TABLE memberships ENABLE ROW LEVEL SECURITY;
ALTER TABLE memberships FORCE ROW LEVEL SECURITY;
CREATE POLICY memberships_self ON memberships FOR SELECT USING (
    user_id = NULLIF(current_setting('app.user_id', true), '')::uuid
);

ALTER TABLE application_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE application_sessions FORCE ROW LEVEL SECURITY;
CREATE POLICY sessions_by_secret ON application_sessions
    USING (
        encode(token_hash, 'hex') = current_setting('app.session_hash', true)
        OR user_id = NULLIF(current_setting('app.user_id', true), '')::uuid
    )
    WITH CHECK (user_id = NULLIF(current_setting('app.user_id', true), '')::uuid);

ALTER TABLE oidc_login_transactions ENABLE ROW LEVEL SECURITY;
ALTER TABLE oidc_login_transactions FORCE ROW LEVEL SECURITY;
CREATE POLICY login_transaction_by_state ON oidc_login_transactions
    USING (encode(state_hash, 'hex') = current_setting('app.login_state_hash', true))
    WITH CHECK (encode(state_hash, 'hex') = current_setting('app.login_state_hash', true));

ALTER TABLE tenant_isolation_probes ENABLE ROW LEVEL SECURITY;
ALTER TABLE tenant_isolation_probes FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_probe_isolation ON tenant_isolation_probes
    USING (
        tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
        AND EXISTS (
            SELECT 1 FROM memberships m
            WHERE m.tenant_id = tenant_isolation_probes.tenant_id
              AND m.user_id = NULLIF(current_setting('app.user_id', true), '')::uuid
              AND m.status = 'active'
        )
    )
    WITH CHECK (
        tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
        AND EXISTS (
            SELECT 1 FROM memberships m
            WHERE m.tenant_id = tenant_isolation_probes.tenant_id
              AND m.user_id = NULLIF(current_setting('app.user_id', true), '')::uuid
              AND m.status = 'active'
        )
    );
"""


def upgrade() -> None:
    op.execute(DDL)


def downgrade() -> None:
    op.execute(
        """
        DROP TABLE tenant_isolation_probes;
        DROP TABLE oidc_login_transactions;
        DROP TABLE application_sessions;
        DROP TABLE memberships;
        DROP TABLE external_identities;
        DROP TABLE users;
        DROP TABLE tenants;
        """
    )
