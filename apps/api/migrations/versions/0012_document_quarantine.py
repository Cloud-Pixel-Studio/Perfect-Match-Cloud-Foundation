# ruff: noqa: E501
"""Add private object references for quarantined document files."""

from alembic import op

revision = "0012_document_quarantine"
down_revision = "0011_qms_document_scope_guard"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(r"""
ALTER TABLE qms_document_revisions ADD COLUMN file_object_key varchar(300);
ALTER TABLE qms_document_revisions ADD CONSTRAINT qms_revision_file_state_check CHECK ((file_state='missing' AND file_object_key IS NULL AND file_sha256 IS NULL AND file_size IS NULL AND file_media_type IS NULL) OR (file_state IN ('quarantined','clean','rejected') AND file_object_key IS NOT NULL AND file_sha256 IS NOT NULL AND file_size>0 AND file_media_type IS NOT NULL));
""")


def downgrade() -> None:
    op.execute(
        "ALTER TABLE qms_document_revisions DROP CONSTRAINT qms_revision_file_state_check; ALTER TABLE qms_document_revisions DROP COLUMN file_object_key;"
    )
