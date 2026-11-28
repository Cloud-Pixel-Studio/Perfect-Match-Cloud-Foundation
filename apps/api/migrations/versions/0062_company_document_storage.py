"""Track the storage occupied by recorded clean document files per company."""

from alembic import op

revision = "0062_company_document_storage"
down_revision = "0061_employee_directory"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
CREATE TABLE public.company_document_storage (
    tenant_id uuid PRIMARY KEY REFERENCES public.tenants(id) ON DELETE CASCADE,
    recorded_bytes bigint NOT NULL DEFAULT 0 CHECK (recorded_bytes >= 0),
    file_count bigint NOT NULL DEFAULT 0 CHECK (file_count >= 0)
);
REVOKE ALL ON public.company_document_storage FROM PUBLIC, pmcloud_app;
GRANT SELECT ON public.company_document_storage TO pmcloud_app;
ALTER TABLE public.company_document_storage ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.company_document_storage FORCE ROW LEVEL SECURITY;
CREATE POLICY company_storage_projection_owner ON public.company_document_storage
    TO CURRENT_USER USING (true) WITH CHECK (true);
CREATE POLICY company_storage_admin_read ON public.company_document_storage
    FOR SELECT TO pmcloud_app USING (
        tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
        AND public.qms_access_actor_is_active()
        AND EXISTS (
            SELECT 1 FROM public.memberships AS m
            WHERE m.tenant_id = company_document_storage.tenant_id
              AND m.user_id = NULLIF(current_setting('app.user_id', true), '')::uuid
              AND m.status = 'active' AND m.role IN ('owner', 'admin')
        )
    );

LOCK TABLE public.qms_document_revisions IN SHARE ROW EXCLUSIVE MODE;
CREATE POLICY company_storage_backfill ON public.qms_document_revisions
    FOR SELECT TO CURRENT_USER USING (true);
INSERT INTO public.company_document_storage (tenant_id, recorded_bytes, file_count)
    SELECT tenant_id, sum(file_size)::bigint, count(*)
    FROM public.qms_document_revisions
    WHERE file_state = 'clean' AND file_object_key IS NOT NULL AND file_size > 0
    GROUP BY tenant_id;
DROP POLICY company_storage_backfill ON public.qms_document_revisions;

CREATE FUNCTION public.sync_company_document_storage() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $$
DECLARE
    old_bytes bigint := 0;
    new_bytes bigint := 0;
    company_id uuid;
BEGIN
    IF TG_OP <> 'INSERT' AND OLD.file_state = 'clean'
        AND OLD.file_object_key IS NOT NULL AND OLD.file_size > 0 THEN
        old_bytes := OLD.file_size;
    END IF;
    IF TG_OP <> 'DELETE' AND NEW.file_state = 'clean'
        AND NEW.file_object_key IS NOT NULL AND NEW.file_size > 0 THEN
        new_bytes := NEW.file_size;
    END IF;
    IF old_bytes = new_bytes THEN
        RETURN NULL;
    END IF;
    company_id := CASE WHEN TG_OP = 'DELETE' THEN OLD.tenant_id ELSE NEW.tenant_id END;
    INSERT INTO public.company_document_storage (tenant_id) VALUES (company_id)
        ON CONFLICT (tenant_id) DO NOTHING;
    UPDATE public.company_document_storage
        SET recorded_bytes = recorded_bytes + new_bytes - old_bytes,
            file_count = file_count + (new_bytes > 0)::integer - (old_bytes > 0)::integer
        WHERE tenant_id = company_id;
    RETURN NULL;
END;
$$;
REVOKE ALL ON FUNCTION public.sync_company_document_storage() FROM PUBLIC, pmcloud_app;
CREATE TRIGGER company_document_storage_refresh
    AFTER INSERT OR UPDATE OF file_state, file_size, file_object_key OR DELETE
    ON public.qms_document_revisions
    FOR EACH ROW EXECUTE FUNCTION public.sync_company_document_storage();
""")


def downgrade() -> None:
    op.execute("""
DROP TRIGGER company_document_storage_refresh ON public.qms_document_revisions;
DROP FUNCTION public.sync_company_document_storage();
DROP TABLE public.company_document_storage;
""")
