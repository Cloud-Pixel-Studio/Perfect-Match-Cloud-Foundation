"""Store normalized employee portraits privately and charge company capacity."""

from alembic import op

revision = "0065_employee_portraits"
down_revision = "0064_document_storage_quota"
branch_labels = None
depends_on = None

QUOTA = """
CREATE OR REPLACE FUNCTION public.check_document_storage_quota(p_company uuid, p_bytes bigint)
RETURNS void LANGUAGE plpgsql SECURITY INVOKER
SET search_path = pg_catalog, public, pg_temp AS $$
DECLARE
    allowed bigint;
    used bigint;
BEGIN
    PERFORM pg_advisory_xact_lock(hashtextextended('company-storage-allowance:' || p_company, 0));
    SELECT allowance_bytes INTO allowed
        FROM public.company_storage_allowances
        WHERE tenant_id = p_company ORDER BY row_version DESC LIMIT 1;
    IF allowed IS NULL THEN
        RETURN;
    END IF;
    SELECT recorded_bytes /* portraits */ INTO used FROM public.company_document_storage
        WHERE tenant_id = p_company;
    IF p_bytes > allowed - COALESCE(used, 0) THEN
        RAISE EXCEPTION 'company document storage allowance exceeded' USING ERRCODE = 'P0064';
    END IF;
END;
$$;
"""


def upgrade() -> None:
    op.execute("""
ALTER TABLE public.employee_profiles
    ADD COLUMN portrait bytea,
    ADD COLUMN portrait_bytes integer GENERATED ALWAYS AS (octet_length(portrait)) STORED,
    ADD CONSTRAINT employee_portrait_format CHECK (
        portrait IS NULL OR (
          portrait_bytes BETWEEN 4 AND 400000
          AND substring(portrait FROM 1 FOR 3) = decode('ffd8ff', 'hex')
        )
    );
GRANT UPDATE (portrait) ON public.employee_profiles TO pmcloud_app;

ALTER TABLE public.company_document_storage
    ADD COLUMN employee_photo_bytes bigint NOT NULL DEFAULT 0 CHECK (employee_photo_bytes >= 0),
    ADD COLUMN employee_photo_count bigint NOT NULL DEFAULT 0 CHECK (employee_photo_count >= 0);
""")
    op.execute(QUOTA.replace("/* portraits */", "+ employee_photo_bytes"))
    op.execute("""
CREATE FUNCTION public.sync_employee_portrait_storage() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $$
DECLARE
    old_bytes bigint := 0;
    new_bytes bigint := 0;
    company_id uuid;
BEGIN
    IF TG_OP = 'INSERT' THEN
        IF NEW.portrait IS NOT NULL THEN
            RAISE EXCEPTION 'create the employee before adding a portrait' USING ERRCODE = '23514';
        END IF;
        RETURN NULL;
    END IF;
    old_bytes := COALESCE(OLD.portrait_bytes, 0);
    IF TG_OP = 'UPDATE' THEN
        IF NEW.portrait IS NOT DISTINCT FROM OLD.portrait THEN
            RETURN NULL;
        END IF;
        IF OLD.status <> 'active' OR NEW.status <> 'active' THEN
            RAISE EXCEPTION 'portrait changes require an active profile' USING ERRCODE = '23514';
        END IF;
        new_bytes := COALESCE(NEW.portrait_bytes, 0);
    END IF;
    IF old_bytes = new_bytes THEN
        RETURN NULL;
    END IF;
    company_id := CASE WHEN TG_OP = 'DELETE' THEN OLD.tenant_id ELSE NEW.tenant_id END;
    IF new_bytes > old_bytes THEN
        PERFORM public.check_document_storage_quota(company_id, new_bytes - old_bytes);
    END IF;
    INSERT INTO public.company_document_storage (tenant_id) VALUES (company_id)
        ON CONFLICT (tenant_id) DO NOTHING;
    UPDATE public.company_document_storage
        SET employee_photo_bytes = employee_photo_bytes + new_bytes - old_bytes,
            employee_photo_count = employee_photo_count
                + (new_bytes > 0)::integer - (old_bytes > 0)::integer
        WHERE tenant_id = company_id;
    RETURN NULL;
END;
$$;
REVOKE ALL ON FUNCTION public.sync_employee_portrait_storage() FROM PUBLIC, pmcloud_app;
CREATE TRIGGER employee_portrait_storage_refresh
    AFTER INSERT OR UPDATE OF portrait OR DELETE ON public.employee_profiles
    FOR EACH ROW EXECUTE FUNCTION public.sync_employee_portrait_storage();
""")


def downgrade() -> None:
    op.execute("""
LOCK TABLE public.employee_profiles IN ACCESS EXCLUSIVE MODE;
CREATE POLICY employee_portrait_downgrade_check ON public.employee_profiles
    FOR SELECT TO CURRENT_USER USING (true);
DO $$ BEGIN
    IF EXISTS (SELECT 1 FROM public.employee_profiles WHERE portrait IS NOT NULL) THEN
        RAISE EXCEPTION 'cannot discard employee portraits' USING ERRCODE = '55000';
    END IF;
END $$;
DROP POLICY employee_portrait_downgrade_check ON public.employee_profiles;
DROP TRIGGER employee_portrait_storage_refresh ON public.employee_profiles;
DROP FUNCTION public.sync_employee_portrait_storage();
ALTER TABLE public.employee_profiles DROP CONSTRAINT employee_portrait_format,
    DROP COLUMN portrait_bytes, DROP COLUMN portrait;
""")
    op.execute(QUOTA.replace(" /* portraits */", ""))
    op.execute("""
ALTER TABLE public.company_document_storage
    DROP COLUMN employee_photo_bytes, DROP COLUMN employee_photo_count;
""")
