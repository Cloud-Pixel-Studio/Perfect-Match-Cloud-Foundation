"""Enforce approved company storage allowances for new document bytes."""

from alembic import op

revision = "0064_document_storage_quota"
down_revision = "0063_company_storage_allowance"
branch_labels = None
depends_on = None

PROJECTION = """
CREATE OR REPLACE FUNCTION public.sync_company_document_storage() RETURNS trigger
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
    /* quota check */
    INSERT INTO public.company_document_storage (tenant_id) VALUES (company_id)
        ON CONFLICT (tenant_id) DO NOTHING;
    UPDATE public.company_document_storage
        SET recorded_bytes = recorded_bytes + new_bytes - old_bytes,
            file_count = file_count + (new_bytes > 0)::integer - (old_bytes > 0)::integer
        WHERE tenant_id = company_id;
    RETURN NULL;
END;
$$;
"""


def upgrade() -> None:
    op.execute("""
CREATE FUNCTION public.check_document_storage_quota(p_company uuid, p_bytes bigint) RETURNS void
LANGUAGE plpgsql SECURITY INVOKER SET search_path = pg_catalog, public, pg_temp AS $$
DECLARE
    allowed bigint;
    used bigint;
BEGIN
    -- Use the same company lock as allowance approval and keep it through commit.
    PERFORM pg_advisory_xact_lock(hashtextextended('company-storage-allowance:' || p_company, 0));
    SELECT allowance_bytes INTO allowed
        FROM public.company_storage_allowances
        WHERE tenant_id = p_company ORDER BY row_version DESC LIMIT 1;
    IF allowed IS NULL THEN
        RETURN;
    END IF;
    SELECT recorded_bytes INTO used FROM public.company_document_storage
        WHERE tenant_id = p_company;
    IF p_bytes > allowed - COALESCE(used, 0) THEN
        RAISE EXCEPTION 'company document storage allowance exceeded' USING ERRCODE = 'P0064';
    END IF;
END;
$$;
REVOKE ALL ON FUNCTION public.check_document_storage_quota(uuid, bigint) FROM PUBLIC, pmcloud_app;

CREATE FUNCTION public.reserve_document_storage(p_unit uuid, p_bytes bigint) RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $$
DECLARE
    company_id uuid := NULLIF(current_setting('app.tenant_id', true), '')::uuid;
BEGIN
    IF company_id IS NULL OR p_unit IS NULL OR p_bytes IS NULL OR p_bytes <= 0
       OR NOT public.qms_has_capability('documents.author', p_unit) THEN
        RAISE EXCEPTION 'document storage requires scoped author access' USING ERRCODE = '42501';
    END IF;
    PERFORM public.check_document_storage_quota(company_id, p_bytes);
END;
$$;
REVOKE ALL ON FUNCTION public.reserve_document_storage(uuid, bigint) FROM PUBLIC, pmcloud_app;
GRANT EXECUTE ON FUNCTION public.reserve_document_storage(uuid, bigint) TO pmcloud_app;
""")
    op.execute(
        PROJECTION.replace(
            "/* quota check */",
            """IF new_bytes > old_bytes THEN
        PERFORM public.check_document_storage_quota(company_id, new_bytes - old_bytes);
    END IF;""",
        )
    )


def downgrade() -> None:
    op.execute(PROJECTION.replace("    /* quota check */\n", ""))
    op.execute("""
DROP FUNCTION public.reserve_document_storage(uuid, bigint);
DROP FUNCTION public.check_document_storage_quota(uuid, bigint);
""")
