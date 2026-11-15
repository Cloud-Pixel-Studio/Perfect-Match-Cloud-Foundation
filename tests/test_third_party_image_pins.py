"""Regression tests for the Compose/Trivy image digest consistency gate."""
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("image_pins", ROOT / "scripts/check-third-party-image-pins.py")
assert SPEC and SPEC.loader
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


class PinTests(unittest.TestCase):
    def setUp(self):
        self.compose = (ROOT / "docker-compose.yml").read_text()
        self.workflow = (ROOT / ".github/workflows/security.yml").read_text()

    def test_repository_is_consistent(self):
        self.assertEqual(module.validate(self.compose, self.workflow), [])

    def test_changed_digest_fails(self):
        changed = self.compose.replace("sha256:f7a49e3f3972ebed5be2ed4befa4a0c68eb7bdddba6e692d42729ceb545134b8", "sha256:" + "a" * 64)
        self.assertIn("seaweedfs: security scan does not target Compose digest", module.validate(changed, self.workflow))

    def test_unpinned_image_fails(self):
        changed = self.compose.replace("chrislusf/seaweedfs:4.51@sha256:f7a49e3f3972ebed5be2ed4befa4a0c68eb7bdddba6e692d42729ceb545134b8", "chrislusf/seaweedfs:4.51")
        self.assertIn("seaweedfs: image is not digest-pinned", module.validate(changed, self.workflow))

    def test_missing_scan_fails(self):
        changed = self.workflow.replace("trivy image --format json --scanners vuln --output artifacts/trivy-keycloak-image.json", "echo disabled")
        self.assertIn("keycloak: security scan does not target Compose digest", module.validate(self.compose, changed))


if __name__ == "__main__":
    unittest.main()
