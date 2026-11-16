"""Safety regressions for the development-only, non-destructive demo loader."""

import importlib.util
import unittest
from pathlib import Path

import httpx

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/seed-demo-sandbox.py"
SPEC = importlib.util.spec_from_file_location("demo_sandbox", SCRIPT)
demo = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(demo)


class DemoSafetyTests(unittest.TestCase):
    def client(self, handler):
        client = httpx.Client(transport=httpx.MockTransport(handler))
        client.cookies.set("pm_csrf", "synthetic-test-csrf")
        self.addCleanup(client.close)
        return client

    def test_production_and_unspecified_environments_rejected(self):
        for value in (None, "production", "staging", "Development"):
            with self.subTest(value=value), self.assertRaises(demo.DemoFailure):
                demo.validate_environment({"PMC_ENVIRONMENT": value})

    def test_missing_credentials_rejected(self):
        with self.assertRaises(demo.DemoFailure):
            demo.validate_environment({"PMC_ENVIRONMENT": "development"})

    def test_existing_edited_or_retired_record_is_never_overwritten(self):
        calls = []

        def handler(request):
            calls.append(request.method)
            return httpx.Response(
                200,
                json=[
                    {
                        "id": "synthetic",
                        "code": "LAB-001",
                        "unit_id": "same",
                        "name": "User modification",
                        "status": "retired",
                    }
                ],
            )

        client = self.client(handler)
        sandbox = demo.Sandbox(client, client, client)
        row, fresh = sandbox.ensure(
            client,
            "/records",
            {
                "code": "LAB-001",
                "unit_id": "same",
                "name": "Seed name",
            },
        )
        self.assertFalse(fresh)
        self.assertEqual(row["name"], "User modification")
        self.assertEqual(row["status"], "retired")
        self.assertEqual(calls, ["GET"])

    def test_collision_in_another_scope_is_denied_without_write(self):
        client = self.client(
            lambda _: httpx.Response(
                200,
                json=[
                    {
                        "id": "synthetic",
                        "code": "LAB-001",
                        "unit_id": "foreign",
                    }
                ],
            )
        )
        sandbox = demo.Sandbox(client, client, client)
        with self.assertRaises(demo.DemoFailure):
            sandbox.ensure(
                client, "/records", {"code": "LAB-001", "unit_id": "expected"}
            )

    def test_full_unpaged_catalog_is_not_assumed_complete(self):
        client = self.client(
            lambda _: httpx.Response(
                200, json=[{"id": str(index)} for index in range(100)]
            )
        )
        sandbox = demo.Sandbox(client, client, client)
        with self.assertRaises(demo.DemoFailure):
            sandbox.rows(client, "/records", paginated=False)

    def test_repeated_page_is_detected(self):
        client = self.client(
            lambda _: httpx.Response(
                200, json=[{"id": str(index)} for index in range(50)]
            )
        )
        sandbox = demo.Sandbox(client, client, client)
        with self.assertRaises(demo.DemoFailure):
            sandbox.rows(client, "/records")

    def test_existing_record_on_second_page_does_not_create_duplicate(self):
        calls = []

        def handler(request):
            calls.append(request.method)
            offset = int(request.url.params["offset"])
            rows = (
                [{"id": str(i), "code": f"other-{i}"} for i in range(50)]
                if offset == 0
                else [{"id": "target", "code": "LAB-001"}]
            )
            return httpx.Response(200, json=rows)

        client = self.client(handler)
        sandbox = demo.Sandbox(client, client, client)
        row, fresh = sandbox.ensure(client, "/records", {"code": "LAB-001"})
        self.assertEqual(row["id"], "target")
        self.assertFalse(fresh)
        self.assertEqual(calls, ["GET", "GET"])

    def test_no_external_target_can_receive_authentication(self):
        client = self.client(lambda _: self.fail("network should not be called"))
        sandbox = demo.Sandbox(client, client, client)
        for path in ("https://example.com", "//example.com", "relative"):
            with self.subTest(path=path), self.assertRaises(demo.DemoFailure):
                sandbox.request(client, "POST", path, {})

    def test_http_errors_do_not_echo_response_secrets(self):
        client = self.client(
            lambda _: httpx.Response(500, text="synthetic-sensitive-body")
        )
        sandbox = demo.Sandbox(client, client, client)
        with self.assertRaises(demo.DemoFailure) as caught:
            sandbox.request(client, "GET", "/records")
        self.assertNotIn("synthetic-sensitive-body", str(caught.exception))

    def test_pdf_xref_points_to_real_objects_and_escapes_text(self):
        content = demo.pdf_document("Example (practice)")
        self.assertTrue(content.startswith(b"%PDF-1.4"))
        xref = int(content.split(b"startxref\n")[1].splitlines()[0])
        self.assertEqual(content[xref : xref + 4], b"xref")
        for index, line in enumerate(content[xref:].splitlines()[3:8], 1):
            offset = int(line.split()[0])
            self.assertTrue(content[offset:].startswith(f"{index} 0 obj".encode()))
        self.assertIn(b"Example \\(practice\\)", content)
        self.assertNotIn(b"/JavaScript", content)


if __name__ == "__main__":
    unittest.main()
