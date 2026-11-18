"""Reject incomplete or substituted study assets before any demo API writes."""

import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1] / "infrastructure/demo/connected_study.py"
SPEC = importlib.util.spec_from_file_location("connected_demo", SOURCE)
study = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(study)


class StudyAssetTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        self.documents = []
        for index in range(1, 9):
            code = f"EST-DOC-{index:03}"
            data = f"%PDF-1.4\nSynthetic {code}\n%%EOF\n".encode()
            (self.root / (code + ".pdf")).write_bytes(data)
            self.documents.append(
                {
                    "code": code,
                    "title": "Synthetic study document",
                    "filename": code + ".pdf",
                    "sha256": hashlib.sha256(data).hexdigest(),
                    "size": len(data),
                }
            )
        self.save()

    def save(self):
        (self.root / "manifest.json").write_text(
            json.dumps({"documents": self.documents})
        )

    def test_complete_verified_library_is_accepted(self):
        assets = study.load_assets(self.root)
        self.assertEqual(set(assets), {f"EST-DOC-{i:03}" for i in range(1, 9)})
        self.assertTrue(
            all(value["bytes"].startswith(b"%PDF-") for value in assets.values())
        )

    def test_missing_document_rejected(self):
        (self.root / "EST-DOC-004.pdf").unlink()
        with self.assertRaises(study.StudyFailure):
            study.load_assets(self.root)

    def test_substituted_file_rejected(self):
        (self.root / "EST-DOC-001.pdf").write_bytes(b"%PDF-1.4\nchanged")
        with self.assertRaises(study.StudyFailure):
            study.load_assets(self.root)

    def test_invalid_pdf_rejected_even_if_hash_matches(self):
        data = b"not a PDF"
        (self.root / "EST-DOC-001.pdf").write_bytes(data)
        self.documents[0].update(
            sha256=hashlib.sha256(data).hexdigest(), size=len(data)
        )
        self.save()
        with self.assertRaises(study.StudyFailure):
            study.load_assets(self.root)

    def test_duplicate_code_cannot_hide_a_missing_document(self):
        self.documents[-1] = self.documents[0]
        self.save()
        with self.assertRaises(study.StudyFailure):
            study.load_assets(self.root)

    def test_path_outside_asset_root_is_denied(self):
        self.documents[0]["filename"] = "../outside.pdf"
        self.save()
        with self.assertRaises(study.StudyFailure):
            study.load_assets(self.root)

    def test_symbolic_link_cannot_substitute_an_asset(self):
        target = self.root / "EST-DOC-001.pdf"
        target.unlink()
        target.symlink_to(self.root / "EST-DOC-002.pdf")
        with self.assertRaises(study.StudyFailure):
            study.load_assets(self.root)


class StudyIntegrityTests(unittest.TestCase):
    def test_parent_rows_and_clean_pdfs_cannot_hide_missing_control_children(self):
        import httpx

        boundary = study.demo_module()
        tables = {
            "processes": ("EST-PROC-", 6),
            "documents": ("EST-DOC-", 8),
            "controls": ("EST-CTL-", 6),
            "control-instances": ("EST-IMP-", 3),
            "risks": ("EST-RSK-", 8),
            "nonconformities": ("EST-NCR-", 6),
            "capas": ("EST-CAPA-", 4),
            "internal-audits/programs": ("EST-PRG-", 3),
            "internal-audits/audits": ("EST-AUD-", 4),
        }
        payload = b"%PDF-1.4\nSynthetic verifier fixture\n%%EOF"
        calls = []

        def handler(request):
            calls.append(request.method)
            path = request.url.path.removeprefix("/api/identity/")
            if path == "organization/units":
                return httpx.Response(
                    200, json=[{"id": "scope", "code": "DEMO-PRACTICA"}]
                )
            if path == "auth/me":
                return httpx.Response(
                    200, json={"id": "20000000-0000-4000-8000-000000000007"}
                )
            if path in tables:
                prefix, count = tables[path]
                return httpx.Response(
                    200,
                    json=[
                        {
                            "id": f"{prefix}{i:03}",
                            "code": f"{prefix}{i:03}",
                            "state": "active",
                        }
                        for i in range(1, count + 1)
                    ],
                )
            if path.endswith("/file"):
                return httpx.Response(200, content=payload)
            if path == "action-center":
                return httpx.Response(200, json={"summary": {"total": 0}})
            return httpx.Response(200, json=[])

        with httpx.Client(transport=httpx.MockTransport(handler)) as client:
            assets = {
                f"EST-DOC-{i:03}": {"sha256": hashlib.sha256(payload).hexdigest()}
                for i in range(1, 9)
            }
            example = study.ConnectedStudy(boundary, client, client, assets)
            example.documents = {
                i: {
                    "document": {"id": f"EST-DOC-{i:03}", "code": f"EST-DOC-{i:03}"},
                    "revision": {"id": "revision"},
                }
                for i in range(1, 9)
            }
            with self.assertRaises(study.StudyFailure):
                example.verify()
        self.assertTrue(all(method == "GET" for method in calls))


class StudyMilestoneTests(unittest.TestCase):
    def test_partial_capa_after_action_creation_cannot_claim_closed_example(self):
        with self.assertRaises(study.StudyFailure):
            study.validate_milestones(
                [{"code": "EST-CAPA-002", "state": "action_planned"}],
                {"EST-WF-003": {"instance_states": ["completed"]}},
                [{"code": "EST-NCR-002", "state": "closed"}],
            )

    def test_workflow_instance_without_execution_cannot_claim_completed_example(self):
        with self.assertRaises(study.StudyFailure):
            study.validate_milestones(
                [{"code": "EST-CAPA-002", "state": "closed"}],
                {"EST-WF-003": {"instance_states": ["active"]}},
                [{"code": "EST-NCR-002", "state": "closed"}],
            )

    def test_closed_capa_cannot_hide_unfinished_incident_closure(self):
        with self.assertRaisesRegex(study.StudyFailure, "NCR"):
            study.validate_milestones(
                [{"code": "EST-CAPA-002", "state": "closed"}],
                {"EST-WF-003": {"instance_states": ["completed"]}},
                [{"code": "EST-NCR-002", "state": "verification"}],
            )

    def test_recorded_terminal_examples_meet_the_teaching_milestones(self):
        study.validate_milestones(
            [{"code": "EST-CAPA-002", "state": "closed"}],
            {"EST-WF-003": {"instance_states": ["completed"]}},
            [{"code": "EST-NCR-002", "state": "closed"}],
        )


if __name__ == "__main__":
    unittest.main()
