"""Protect the source version when workflow configuration is reassigned."""

from alembic import op

revision = "0006_workflow_immutability"
down_revision = "0005_workflow_engine"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION reject_published_workflow_configuration() RETURNS trigger
        LANGUAGE plpgsql SECURITY INVOKER SET search_path = public, pg_catalog AS $$
        DECLARE old_version_id uuid; new_version_id uuid;
        BEGIN
          IF TG_OP <> 'INSERT' THEN
            old_version_id := COALESCE(
              NULLIF(to_jsonb(OLD)->>'workflow_version_id', '')::uuid, OLD.id);
          END IF;
          IF TG_OP <> 'DELETE' THEN
            new_version_id := COALESCE(
              NULLIF(to_jsonb(NEW)->>'workflow_version_id', '')::uuid, NEW.id);
          END IF;
          IF EXISTS (SELECT 1 FROM workflow_versions
                     WHERE id IN (old_version_id, new_version_id) AND status = 'published') THEN
            RAISE EXCEPTION 'published workflow configuration is immutable' USING ERRCODE = '23514';
          END IF;
          IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
          RETURN NEW;
        END;
        $$;
        """
    )


def downgrade() -> None:
    # Restore the preceding schema only on an explicit migration rollback.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION reject_published_workflow_configuration() RETURNS trigger
        LANGUAGE plpgsql SECURITY INVOKER SET search_path = public, pg_catalog AS $$
        DECLARE version_id uuid;
        BEGIN
          version_id := CASE WHEN TG_OP = 'DELETE' THEN
            COALESCE(NULLIF(to_jsonb(OLD)->>'workflow_version_id', '')::uuid, OLD.id)
            ELSE COALESCE(NULLIF(to_jsonb(NEW)->>'workflow_version_id', '')::uuid, NEW.id)
          END;
          IF EXISTS (SELECT 1 FROM workflow_versions
                     WHERE id = version_id AND status = 'published') THEN
            RAISE EXCEPTION 'published workflow configuration is immutable' USING ERRCODE = '23514';
          END IF;
          RETURN COALESCE(NEW, OLD);
        END;
        $$;
        """
    )
