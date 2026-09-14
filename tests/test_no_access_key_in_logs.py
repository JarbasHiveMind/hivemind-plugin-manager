"""The access key must not reach the logs through a lifecycle callback.

``ClientCallbacks`` defaults interpolated the whole
``HiveMindClientConnection`` dataclass, whose ``__repr__`` includes ``key`` —
the secret a satellite authenticates with. Each callback is installed on the
listener, the binary protocol and the agent protocol, so a node running at
DEBUG wrote the key six times per connection into a log operators paste into
bug reports.
"""
import unittest
from dataclasses import dataclass
from typing import Optional
from unittest.mock import patch

from hivemind_plugin_manager import protocols

SECRET = "super-secret-access-key"


@dataclass
class _Conn:
    """Enough of HiveMindClientConnection to reproduce the leak."""
    key: str = SECRET
    peer: str = "test-client::1::sat::abc123"

    def __repr__(self) -> str:
        # the real dataclass repr names the key; keep that faithfully
        return f"HiveMindClientConnection(key={self.key!r}, peer={self.peer!r})"


class _NoPeer:
    """A stand-in without a peer, as a transport may build before a client."""
    key = SECRET

    def __repr__(self) -> str:
        return f"<stand-in key={self.key!r}>"


CALLBACKS = ("on_connect", "on_disconnect", "on_invalid_key",
             "on_invalid_protocol")


class TestCallbacksDoNotLogTheKey(unittest.TestCase):

    def _lines(self, cb_name, client):
        lines = []
        with patch.object(protocols.LOG, "debug", side_effect=lines.append):
            getattr(protocols, cb_name)(client)
        return lines

    def test_no_callback_logs_the_access_key(self):
        for name in CALLBACKS:
            with self.subTest(callback=name):
                lines = self._lines(name, _Conn())
                self.assertTrue(lines, f"{name} logged nothing")
                for line in lines:
                    self.assertNotIn(SECRET, line)

    def test_every_callback_names_the_peer(self):
        for name in CALLBACKS:
            with self.subTest(callback=name):
                lines = self._lines(name, _Conn())
                self.assertIn("test-client::1::sat::abc123", lines[0])

    def test_a_client_without_a_peer_still_logs_a_line(self):
        for name in CALLBACKS:
            with self.subTest(callback=name):
                lines = self._lines(name, _NoPeer())
                self.assertTrue(lines, f"{name} raised or logged nothing")
                self.assertNotIn(SECRET, lines[0])
                self.assertIn("<unknown peer>", lines[0])

    def test_an_empty_peer_does_not_produce_a_bare_line(self):
        lines = self._lines("on_connect", _Conn(peer=""))
        self.assertIn("<unknown peer>", lines[0])
        self.assertNotIn(SECRET, lines[0])

    def test_the_defaults_on_ClientCallbacks_are_the_patched_functions(self):
        cb = protocols.ClientCallbacks()
        for name in CALLBACKS:
            with self.subTest(callback=name):
                self.assertIs(getattr(cb, name), getattr(protocols, name))


if __name__ == "__main__":
    unittest.main()
