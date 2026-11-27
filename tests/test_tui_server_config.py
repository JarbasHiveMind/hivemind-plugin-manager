import json
import os
import tempfile
import unittest
from unittest import mock

from click.testing import CliRunner

_REAL = os.path.join(os.path.expanduser("~"), ".config", "hivemind-core", "server.json")
_REAL_MTIME = os.stat(_REAL).st_mtime_ns if os.path.exists(_REAL) else None
_ISOLATED = tempfile.mkdtemp()
_SAVED = os.environ.get("XDG_CONFIG_HOME")
os.environ["XDG_CONFIG_HOME"] = _ISOLATED
try:
    # tui may load its config at import time, so the import happens isolated
    from hivemind_plugin_manager import tui
finally:
    if _SAVED is None:
        os.environ.pop("XDG_CONFIG_HOME")
    else:
        os.environ["XDG_CONFIG_HOME"] = _SAVED


class TestServerConfigGuard(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        env = mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": self._tmp.name})
        env.start()
        self.addCleanup(env.stop)
        self.dir = os.path.join(self._tmp.name, "hivemind-core")
        os.makedirs(self.dir)
        self.path = os.path.join(self.dir, "server.json")

    def tearDown(self):
        real = os.stat(_REAL).st_mtime_ns if os.path.exists(_REAL) else None
        self.assertEqual(real, _REAL_MTIME, "test touched the real server.json")

    def _set(self):
        with mock.patch.object(tui, "list_plugins", return_value=["p"]):
            return CliRunner().invoke(tui.cli, ["set", "network", "p"])

    def test_unparseable_file_is_left_untouched(self):
        raw = b'{"admin_pass": "secret", "network_protocol": {"module": "x"},}'
        with open(self.path, "wb") as f:
            f.write(raw)
        result = self._set()
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("server.json", result.output)
        with open(self.path, "rb") as f:
            self.assertEqual(f.read(), raw)

    def test_non_object_file_is_left_untouched(self):
        for raw in (b"[1, 2]", b"null"):
            with self.subTest(raw=raw):
                with open(self.path, "wb") as f:
                    f.write(raw)
                result = self._set()
                self.assertNotEqual(result.exit_code, 0)
                self.assertIn("not a JSON object", result.output)
                with open(self.path, "rb") as f:
                    self.assertEqual(f.read(), raw)

    def test_commented_file_keeps_other_settings(self):
        with open(self.path, "w") as f:
            f.write('// hub settings\n# more\n{"admin_pass": "secret"}\n')
        result = self._set()
        self.assertEqual(result.exit_code, 0, result.output)
        with open(self.path) as f:
            data = json.load(f)
        self.assertEqual(data["admin_pass"], "secret")
        self.assertEqual(data["network_protocol"]["module"], "p")

    def test_valid_file_keeps_other_settings(self):
        with open(self.path, "w") as f:
            json.dump({"admin_pass": "secret"}, f)
        result = self._set()
        self.assertEqual(result.exit_code, 0, result.output)
        with open(self.path) as f:
            data = json.load(f)
        self.assertEqual(data["admin_pass"], "secret")
        self.assertEqual(data["network_protocol"]["module"], "p")

    def test_absent_file_is_created(self):
        result = self._set()
        self.assertEqual(result.exit_code, 0, result.output)
        with open(self.path) as f:
            self.assertEqual(json.load(f)["network_protocol"]["module"], "p")
