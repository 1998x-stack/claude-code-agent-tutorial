import unittest
from sandbox_manifest import SandboxManifest, EffectRequest, preview


def config(**kw):
    base = dict(enabled=True, fail_if_unavailable=True,
                allow_unsandboxed_retry=False,
                network_hosts=frozenset({"docs.example.org"}),
                writable_subdirs=frozenset({"scratch"}))
    base.update(kw)
    return SandboxManifest(**base)


class ManifestTests(unittest.TestCase):
    def test_purely_declared_read_or_writable_effects(self):
        self.assertTrue(preview(config(), EffectRequest("inspect"))[0])
        self.assertTrue(preview(config(), EffectRequest(
            "test", writes_to="scratch/report.txt"))[0])
        self.assertTrue(preview(config(), EffectRequest(
            "test", connects_to="DOCS.EXAMPLE.ORG"))[0])

    def test_unsandboxed_retry_never_allowed(self):
        self.assertFalse(preview(config(), EffectRequest("test", unsandboxed=True))[0])
        with self.assertRaises(ValueError):
            config(allow_unsandboxed_retry=True).validate()

    def test_never_fall_back_without_os_isolation(self):
        with self.assertRaises(ValueError):
            config(enabled=False).validate()
        with self.assertRaises(ValueError):
            config(fail_if_unavailable=False).validate()
        for flag in ("false", 1, None):
            with self.subTest(flag=flag), self.assertRaises(ValueError):
                config(enabled=flag).validate()

    def test_reject_network_and_file_escape(self):
        self.assertFalse(preview(config(), EffectRequest(
            "test", connects_to="external.example.org"))[0])
        for path in ("../secrets", "/etc/passwd", "src/a.txt", "scratch/../other",
                     "C:/Windows/win.ini", "scratch/file:secret", "bad\npath"):
            with self.subTest(path=path):
                self.assertFalse(preview(config(), EffectRequest(
                    "test", writes_to=path))[0])

    def test_invalid_host_and_write_configuration_rejected(self):
        with self.assertRaises(ValueError):
            config(network_hosts=frozenset({"https://evil.example"})).validate()
        with self.assertRaises(ValueError):
            config(writable_subdirs=frozenset({"C:/temp"})).validate()
        with self.assertRaises(ValueError):
            config(network_hosts={"docs.example.org"}).validate()

    def test_unknown_profile_and_invalid_request_fail_closed(self):
        self.assertFalse(preview(config(), EffectRequest("arbitrary-shell"))[0])
        with self.assertRaises(ValueError):
            EffectRequest("test", unsandboxed="false")


if __name__ == "__main__":
    unittest.main()
