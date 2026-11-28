"""Store approved storage allowances independently of the product catalog."""

from alembic import op

revision = "0063_company_storage_allowance"
down_revision = "0062_company_document_storage"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
CREATE TABLE public.company_storage_allowances (
    tenant_id uuid NOT NULL REFERENCES public.tenants(id) ON DELETE RESTRICT,
    row_version integer NOT NULL CHECK (row_version > 0),
    allowance_bytes bigint NOT NULL CHECK (allowance_bytes BETWEEN 1 AND 9007199254740991),
    approval_id uuid NOT NULL,
    recorded_by name NOT NULL DEFAULT session_user,
    recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (tenant_id, row_version),
    UNIQUE (tenant_id, approval_id)
);
REVOKE ALL ON public.company_storage_allowances FROM PUBLIC, pmcloud_app;
GRANT SELECT(tenant_id, row_version, allowance_bytes)
    ON public.company_storage_allowances TO pmcloud_app;
ALTER TABLE public.company_storage_allowances ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.company_storage_allowances FORCE ROW LEVEL SECURITY;
CREATE POLICY company_allowance_operations ON public.company_storage_allowances
    TO CURRENT_USER USING (true) WITH CHECK (true);
CREATE POLICY company_allowance_admin_read ON public.company_storage_allowances
    FOR SELECT TO pmcloud_app USING (
        tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
        AND public.qms_access_actor_is_active()
        AND EXISTS (
            SELECT 1 FROM public.memberships AS m
            WHERE m.tenant_id = company_storage_allowances.tenant_id
              AND m.user_id = NULLIF(current_setting('app.user_id', true), '')::uuid
              AND m.status = 'active' AND m.role IN ('owner', 'admin')
        )
    );

CREATE FUNCTION public.protect_company_storage_allowance() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog, public, pg_temp AS $$
BEGIN
    RAISE EXCEPTION 'storage allowance history is append-only' USING ERRCODE = '55000';
END;
$$;
REVOKE ALL ON FUNCTION public.protect_company_storage_allowance() FROM PUBLIC, pmcloud_app;
CREATE TRIGGER company_allowance_immutable BEFORE UPDATE OR DELETE
    ON public.company_storage_allowances
    FOR EACH ROW EXECUTE FUNCTION public.protect_company_storage_allowance();

CREATE FUNCTION public.record_company_storage_allowance(
    p_company uuid, p_bytes bigint, p_expected_version integer, p_approval uuid
) RETURNS integer
LANGUAGE plpgsql SECURITY INVOKER SET search_path = pg_catalog, public, pg_temp AS $$
DECLARE
    previous public.company_storage_allowances%ROWTYPE;
    current_version integer;
    next_version integer;
BEGIN
    IF p_company IS NULL OR p_approval IS NULL OR p_bytes IS NULL
       OR p_bytes NOT BETWEEN 1 AND 9007199254740991
       OR p_expected_version IS NULL OR p_expected_version NOT BETWEEN 0 AND 2147483646 THEN
        RAISE EXCEPTION 'invalid storage allowance approval' USING ERRCODE = '22023';
    END IF;
    PERFORM pg_advisory_xact_lock(hashtextextended('company-storage-allowance:' || p_company, 0));
    next_version := p_expected_version + 1;
    SELECT * INTO previous FROM public.company_storage_allowances
     WHERE tenant_id = p_company AND approval_id = p_approval;
    IF FOUND THEN
        IF previous.allowance_bytes <> p_bytes OR previous.row_version <> next_version THEN
            RAISE EXCEPTION 'storage approval already used' USING ERRCODE = '23514';
        END IF;
        RETURN previous.row_version;
    END IF;
    SELECT COALESCE(max(row_version), 0) INTO current_version
      FROM public.company_storage_allowances WHERE tenant_id = p_company;
    IF current_version <> p_expected_version THEN
        RAISE EXCEPTION 'storage allowance version changed' USING ERRCODE = '23514';
    END IF;
    INSERT INTO public.company_storage_allowances
        (tenant_id, row_version, allowance_bytes, approval_id)
        VALUES (p_company, next_version, p_bytes, p_approval);
    RETURN next_version;
END;
$$;
REVOKE ALL ON FUNCTION public.record_company_storage_allowance(uuid, bigint, integer, uuid)
    FROM PUBLIC, pmcloud_app;
""")


def downgrade() -> None:
    op.execute("""
LOCK TABLE public.company_storage_allowances IN ACCESS EXCLUSIVE MODE;
DO $$ BEGIN
    IF EXISTS (SELECT 1 FROM public.company_storage_allowances) THEN
        RAISE EXCEPTION 'cannot discard storage allowance history' USING ERRCODE = '55000';
    END IF;
END $$;
DROP FUNCTION public.record_company_storage_allowance(uuid, bigint, integer, uuid);
DROP TABLE public.company_storage_allowances;
DROP FUNCTION public.protect_company_storage_allowance();
""")
