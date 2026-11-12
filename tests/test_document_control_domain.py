"""Regression tests for the PMC-05 revision lifecycle domain rules."""
import importlib.util
from pathlib import Path
import sys
import unittest
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "apps/api/pmcloud/document_control.py"
spec = importlib.util.spec_from_file_location("pmc_document_control", MODULE)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)

DocumentRevision = module.DocumentRevision
RevisionStatus = module.RevisionStatus
DocumentTransitionError = module.DocumentTransitionError
transition_revision = module.transition_revision


class RevisionLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.revision = DocumentRevision("doc-1", "tenant-1", 1, RevisionStatus.DRAFT)

    def test_complete_controlled_lifecycle(self):
        review = transition_revision(self.revision, RevisionStatus.IN_REVIEW, actor_id="author", author_id="author")
        approved = transition_revision(review, RevisionStatus.APPROVED, actor_id="reviewer", author_id="author")
        effective = transition_revision(
            approved, RevisionStatus.EFFECTIVE, actor_id="reviewer", author_id="author",
            approved_by="reviewer", now=datetime(2026, 11, 12, tzinfo=timezone.utc)
        )
        superseded = transition_revision(effective, RevisionStatus.SUPERSEDED, actor_id="admin", author_id="author")
        self.assertEqual(superseded.status, RevisionStatus.SUPERSEDED)
        self.assertEqual(self.revision.status, RevisionStatus.DRAFT)
        self.assertEqual(effective.effective_at, datetime(2026, 11, 12, tzinfo=timezone.utc))

    def test_author_cannot_approve(self):
        review = transition_revision(self.revision, RevisionStatus.IN_REVIEW, actor_id="author", author_id="author")
        with self.assertRaises(DocumentTransitionError):
            transition_revision(review, RevisionStatus.APPROVED, actor_id="author", author_id="author")

    def test_cannot_skip_review(self):
        with self.assertRaises(DocumentTransitionError):
            transition_revision(self.revision, RevisionStatus.EFFECTIVE, actor_id="admin", author_id="author", approved_by="admin")

    def test_effectiveness_requires_independent_approval(self):
        review = transition_revision(self.revision, RevisionStatus.IN_REVIEW, actor_id="author", author_id="author")
        approved = transition_revision(review, RevisionStatus.APPROVED, actor_id="reviewer", author_id="author")
        with self.assertRaises(DocumentTransitionError):
            transition_revision(approved, RevisionStatus.EFFECTIVE, actor_id="admin", author_id="author", approved_by="author")

    def test_rejected_revision_can_return_to_draft(self):
        review = transition_revision(self.revision, RevisionStatus.IN_REVIEW, actor_id="author", author_id="author")
        rejected = transition_revision(review, RevisionStatus.REJECTED, actor_id="reviewer", author_id="author")
        self.assertEqual(transition_revision(rejected, RevisionStatus.DRAFT, actor_id="author", author_id="author").status, RevisionStatus.DRAFT)


if __name__ == "__main__":
    unittest.main()
