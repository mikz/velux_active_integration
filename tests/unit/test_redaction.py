"""Host-side redaction regressions, runnable without HA or Docker."""

import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from tests.lab.redaction import REDACTED, sanitize_artifacts


class ArtifactRedactionTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)

    def test_redacts_late_docker_logs_exact_secret_and_pin(self):
        logs = self.root / "docker" / "ha.log"
        logs.parent.mkdir()
        logs.write_text("token=opaque-secret; HAP PIN: 123-45-678\n", encoding="utf-8")
        sanitize_artifacts(self.root, ["opaque-secret"])
        self.assertEqual(logs.read_text(), f"token={REDACTED}; HAP PIN: {REDACTED}\n")

    def test_generic_bearer_jwt_and_pairing_keys_preserve_json(self):
        jwt = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJoYSJ9.abcdefgHIJKLMNOP"
        path = self.root / "trace.json"
        path.write_text(
            json.dumps(
                {
                    "header": "Bearer unlisted-token_123",
                    "jwt": jwt,
                    "iOSDeviceLTSK": "private-material",
                    "AccessoryLTPK": "pairing-material",
                    "state": "on",
                }
            )
        )
        sanitize_artifacts(self.root, [])
        content = json.loads(path.read_text())
        self.assertEqual(
            content,
            {
                "header": f"Bearer {REDACTED}",
                "jwt": REDACTED,
                "iOSDeviceLTSK": REDACTED,
                "AccessoryLTPK": REDACTED,
                "state": "on",
            },
        )

    def test_redacts_zip_text_and_comments_preserves_image_member(self):
        path = self.root / "trace.zip"
        image = b"\x89PNG\r\n\x1a\n\x00secret-value123-45-678"
        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.comment = b"secret-value"
            info = zipfile.ZipInfo("trace.network")
            info.comment = b"secret-value"
            archive.writestr(info, '{"token": "secret-value", "pin": "123-45-678"}')
            archive.writestr("resources/screenshot.png", image)
        sanitize_artifacts(self.root, ["secret-value"])
        with zipfile.ZipFile(path) as archive:
            self.assertEqual(archive.comment, REDACTED.encode())
            self.assertEqual(archive.getinfo("trace.network").comment, REDACTED.encode())
            self.assertEqual(
                json.loads(archive.read("trace.network")), {"token": REDACTED, "pin": REDACTED}
            )
            self.assertEqual(archive.read("resources/screenshot.png"), image)

    def test_preserves_images_and_non_utf_binary(self):
        images = {
            "image.png": b"secret-value123-45-678",
            "image-no-extension": b"GIF89asecret-value",
            "data.bin": b"\xff\x00secret-value",
        }
        for name, contents in images.items():
            (self.root / name).write_bytes(contents)
        sanitize_artifacts(self.root, ["secret-value"])
        for name, contents in images.items():
            self.assertEqual((self.root / name).read_bytes(), contents)

    def test_control_receipt_and_symlink_are_untouched(self):
        control = self.root / "control"
        control.mkdir()
        receipt = control / "secrets.json"
        receipt.write_text('["secret-value"]')
        link = self.root / "receipt-link.json"
        link.symlink_to(receipt)
        sanitize_artifacts(self.root, ["secret-value"])
        self.assertEqual(receipt.read_text(), '["secret-value"]')
        self.assertTrue(link.is_symlink())

    def test_json_escaped_secrets_and_unicode_text(self):
        secret = 'my"secret\\value'
        json_path = self.root / "escaped.json"
        json_path.write_text(json.dumps({"token": secret}))
        utf16_path = self.root / "utf16.log"
        utf16_path.write_bytes("HAP 123-45-678".encode("utf-16"))
        sanitize_artifacts(self.root, [secret])
        self.assertEqual(json.loads(json_path.read_text()), {"token": REDACTED})
        self.assertEqual(utf16_path.read_bytes().decode("utf-16"), f"HAP {REDACTED}")

    def test_nested_zip_and_idempotence(self):
        nested = io.BytesIO()
        with zipfile.ZipFile(nested, "w") as archive:
            archive.writestr("ha.log", "Bearer token-not-in-list")
        path = self.root / "trace.zip"
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("nested.zip", nested.getvalue())
        sanitize_artifacts(self.root, [])
        sanitized = path.read_bytes()
        sanitize_artifacts(self.root, [])
        self.assertEqual(path.read_bytes(), sanitized)
        with (
            zipfile.ZipFile(path) as outer,
            zipfile.ZipFile(io.BytesIO(outer.read("nested.zip"))) as inner,
        ):
            self.assertEqual(inner.read("ha.log"), f"Bearer {REDACTED}".encode())

    def test_malformed_zip_raises(self):
        (self.root / "trace.zip").write_bytes(b"not a zip")
        with self.assertRaises(zipfile.BadZipFile):
            sanitize_artifacts(self.root, [])

    def test_unlisted_onboarding_refresh_and_url_credentials_in_nested_trace(self):
        credentials = {
            name: name + "-ephemeral-value"
            for name in ("auth_code", "refresh_token", "access_token", "password", "client_secret")
        }
        body = json.dumps(credentials)
        events = [
            {"response": credentials, "postData": {"text": body}},
            {"url": "http://ha:8123/api/brands/icon.png?token=unrecorded-value&size=32"},
            {"url": "http://ha:8123/auth?code=unrecorded-code&amp;state=keep"},
        ]
        nested = io.BytesIO()
        with zipfile.ZipFile(nested, "w") as archive:
            archive.writestr("trace.network", "\n".join(map(json.dumps, events)) + "\n")
        path = self.root / "evidence.zip"
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("trace.zip", nested.getvalue())
        with self.assertRaisesRegex(ValueError, "requires redaction"):
            sanitize_artifacts(self.root, [], check=True)
        original = path.read_bytes()
        sanitize_artifacts(self.root, [])
        self.assertNotEqual(path.read_bytes(), original)
        with zipfile.ZipFile(path) as outer:
            with zipfile.ZipFile(io.BytesIO(outer.read("trace.zip"))) as inner:
                records = [json.loads(line) for line in inner.read("trace.network").splitlines()]
        self.assertEqual(records[0]["response"], dict.fromkeys(credentials, REDACTED))
        self.assertEqual(
            json.loads(records[0]["postData"]["text"]), dict.fromkeys(credentials, REDACTED)
        )
        self.assertEqual(
            records[1]["url"], f"http://ha:8123/api/brands/icon.png?token={REDACTED}&size=32"
        )
        self.assertEqual(records[2]["url"], f"http://ha:8123/auth?code={REDACTED}&amp;state=keep")
        sanitize_artifacts(self.root, [], check=True)
        cleaned = path.read_bytes()
        sanitize_artifacts(self.root, [])
        self.assertEqual(path.read_bytes(), cleaned)

    def test_private_home_paths_and_json_escaped_windows_paths(self):
        path = self.root / "inspect.json"
        path.write_text(
            json.dumps(
                {
                    "mount": "/Users/auditor/work/controller/.lab/run",
                    "source": "/home/operator/project/test.py",
                    "windows": r"C:\Users\auditor\project\test.py",
                    "ci": "/home/runner/work/public/project/test.py",
                }
            )
        )
        sanitize_artifacts(self.root, [])
        result = json.loads(path.read_text())
        for name in ("mount", "source", "windows"):
            self.assertEqual(result[name], "[PRIVATE_PATH]")
        self.assertEqual(result["ci"], "/home/runner/work/public/project/test.py")

    def test_publication_check_does_not_modify_dirty_evidence(self):
        path = self.root / "trace.json"
        path.write_text(json.dumps({"auth_code": "one-time-lab-code"}))
        original = path.read_bytes()
        with self.assertRaisesRegex(ValueError, "requires redaction"):
            sanitize_artifacts(self.root, [], check=True)
        self.assertEqual(path.read_bytes(), original)

    def test_publication_check_rejects_control_secrets_and_symlinks(self):
        control = self.root / "control"
        control.mkdir()
        receipt = control / "secrets.json"
        receipt.write_text("[]")
        with self.assertRaisesRegex(ValueError, "Control data"):
            sanitize_artifacts(self.root, [], check=True)
        receipt.unlink()
        (self.root / "link").symlink_to(control)
        with self.assertRaisesRegex(ValueError, "Symlink"):
            sanitize_artifacts(self.root, [], check=True)

    def test_redaction_refuses_colliding_evidence_keys_without_overwriting(self):
        path = self.root / "coverage.json"
        path.write_text(json.dumps({"/Users/first/file.py": 1, "/Users/second/file.py": 2}))
        original = path.read_bytes()
        with self.assertRaisesRegex(ValueError, "merge JSON"):
            sanitize_artifacts(self.root, [])
        self.assertEqual(path.read_bytes(), original)

    def test_redaction_refuses_colliding_archive_members_without_overwriting(self):
        path = self.root / "evidence.zip"
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("/Users/first/file.txt", "first")
            archive.writestr("/Users/second/file.txt", "second")
        original = path.read_bytes()
        with self.assertRaisesRegex(ValueError, "merge archive"):
            sanitize_artifacts(self.root, [])
        self.assertEqual(path.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
