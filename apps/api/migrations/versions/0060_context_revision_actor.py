"""Keep the display name of the authenticated actor with each context revision."""

from alembic import op

revision = "0060_context_revision_actor"
down_revision = "0059_qms_scope_basis"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
ALTER TABLE public.qms_context_revisions ADD COLUMN actor_display_name varchar(160);
CREATE OR REPLACE FUNCTION public.append_qms_context_revision() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $$
DECLARE recorded_name varchar(160);
BEGIN
 SELECT directory.display_name INTO recorded_name
 FROM public.organization_member_directory() AS directory
 WHERE directory.user_id=NEW.updated_by_user_id;
 INSERT INTO public.qms_context_revisions(
  record_id,tenant_id,unit_id,row_version,command,snapshot,actor_display_name
 ) VALUES(
  NEW.id,NEW.tenant_id,NEW.unit_id,NEW.row_version,
  current_setting('app.qms_context_command'),to_jsonb(NEW),NULLIF(recorded_name,'')
 );
 RETURN NULL;
END; $$;
""")


def downgrade() -> None:
    op.execute("""
CREATE OR REPLACE FUNCTION public.append_qms_context_revision() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $$
BEGIN
 INSERT INTO public.qms_context_revisions(record_id,tenant_id,unit_id,row_version,command,snapshot)
 VALUES(
  NEW.id,NEW.tenant_id,NEW.unit_id,NEW.row_version,
  current_setting('app.qms_context_command'),to_jsonb(NEW)
 );
 RETURN NULL;
END; $$;
ALTER TABLE public.qms_context_revisions DROP COLUMN actor_display_name;
""")
