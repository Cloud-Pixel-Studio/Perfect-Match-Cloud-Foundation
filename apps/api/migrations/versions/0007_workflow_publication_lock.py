"""Serialize configuration edits against workflow publication."""

from alembic import op

revision = "0007_workflow_publication_lock"
down_revision = "0006_workflow_immutability"
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
          -- Serialize edits against publication before inspecting status.
          -- Stable ordering avoids opposing locks on two parent versions.
          PERFORM id FROM workflow_versions
            WHERE id IN (old_version_id, new_version_id)
            ORDER BY id FOR SHARE;
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
