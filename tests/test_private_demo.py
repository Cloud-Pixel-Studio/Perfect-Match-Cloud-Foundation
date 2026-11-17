"""Credential destination boundaries for the authorized private demo loader."""

import importlib.util
import unittest
from pathlib import Path

import httpx

SOURCE = Path(__file__).resolve().parents[1] / "infrastructure/demo/seed.py"
SPEC = importlib.util.spec_from_file_location("private_demo", SOURCE)
demo = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(demo)


class PrivateDemoBoundaryTests(unittest.TestCase):
    def test_only_exact_approved_https_origin(self):
        self.assertTrue(demo.allowed(demo.ORIGIN + "/products"))
        for value in (
            "http://demo.3-238-70-198.sslip.io/products",
            "https://3-238-70-198.sslip.io/",
            demo.ORIGIN + ".example.test/",
            "https://user:password@demo.3-238-70-198.sslip.io/",
            demo.ORIGIN + ":444/",
            "https://example.test/",
        ):
            with self.subTest(value=value):
                self.assertFalse(demo.allowed(value))

    def test_foreign_redirect_rejected_before_following(self):
        seen = []

        def handler(request):
            seen.append(str(request.url))
            return httpx.Response(302, headers={"location": "https://example.test/"})

        with (
            httpx.Client(transport=httpx.MockTransport(handler)) as client,
            self.assertRaises(demo.DemoError),
        ):
            demo.navigate(client, client.get(demo.ORIGIN + "/login"))
        self.assertEqual(len(seen), 1)

    def test_foreign_form_rejected_before_sending_credentials(self):
        seen = []

        def handler(request):
            seen.append(request.method)
            return httpx.Response(
                200,
                text='<form id="kc-form-login" action="https://example.test/login"></form>',
            )

        with (
            httpx.Client(transport=httpx.MockTransport(handler)) as client,
            self.assertRaises(demo.DemoError),
        ):
            demo.login(client, "synthetic-user", "synthetic-password")
        self.assertEqual(seen, ["GET"])

    def test_other_same_origin_form_rejected(self):
        seen = []

        def handler(request):
            seen.append(request.method)
            return httpx.Response(
                200, text='<form id="kc-form-login" action="/admin/"></form>'
            )

        with (
            httpx.Client(transport=httpx.MockTransport(handler)) as client,
            self.assertRaises(demo.DemoError),
        ):
            demo.login(client, "synthetic-user", "synthetic-password")
        self.assertEqual(seen, ["GET"])

    def test_request_hook_blocks_foreign_origin(self):
        with self.assertRaises(demo.DemoError):
            demo.check_request(httpx.Request("GET", "https://example.test/"))

    def test_redirect_loop_is_bounded(self):
        seen = []

        def handler(request):
            seen.append(request.method)
            return httpx.Response(302, headers={"location": "/loop"})

        with (
            httpx.Client(transport=httpx.MockTransport(handler)) as client,
            self.assertRaises(demo.DemoError),
        ):
            demo.navigate(client, client.get(demo.ORIGIN + "/loop"))
        self.assertEqual(len(seen), 13)


class BootstrapRecoveryTests(unittest.TestCase):
    def test_six_users_with_missing_memberships_are_not_complete(self):
        from sqlalchemy import create_engine, text

        source = SOURCE.with_name("bootstrap.py")
        spec = importlib.util.spec_from_file_location("demo_bootstrap", source)
        bootstrap = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(bootstrap)
        engine = create_engine("sqlite://")
        with engine.begin() as connection:
            connection.execute(text("CREATE TABLE users (id text PRIMARY KEY)"))
            connection.execute(
                text("CREATE TABLE external_identities (user_id text, issuer text)")
            )
            connection.execute(
                text("CREATE TABLE memberships (tenant_id text, user_id text)")
            )
            for index in range(1, 7):
                user = f"20000000-0000-4000-8000-{index:012}"
                connection.execute(
                    text("INSERT INTO users VALUES (:user)"), {"user": user}
                )
                connection.execute(
                    text("INSERT INTO external_identities VALUES (:user, :issuer)"),
                    {"user": user, "issuer": demo.ORIGIN + "/realms/perfect-match"},
                )
            self.assertFalse(
                bootstrap.existing_demo_complete(
                    connection, demo.ORIGIN + "/realms/perfect-match"
                )
            )
            pairs = [(1, 4), (1, 1), (2, 2), (1, 3), (2, 3), (2, 5), (2, 6)]
            for tenant, user in pairs:
                connection.execute(
                    text("INSERT INTO memberships VALUES (:tenant, :user)"),
                    {
                        "tenant": f"10000000-0000-4000-8000-{tenant:012}",
                        "user": f"20000000-0000-4000-8000-{user:012}",
                    },
                )
            self.assertTrue(
                bootstrap.existing_demo_complete(
                    connection, demo.ORIGIN + "/realms/perfect-match"
                )
            )
            self.assertFalse(
                bootstrap.existing_demo_complete(
                    connection, "https://wrong.example.test/realms/perfect-match"
                )
            )


if __name__ == "__main__":
    unittest.main()
