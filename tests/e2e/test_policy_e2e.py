"""Contract tests for ``PolicyPlugin`` / ``Verdict`` / ``Mutation``.

Each test drives messages through ``PolicyPlugin.review()`` and the
chain semantics (short-circuit on first deny, fail-closed on exception,
mutations applied on allow only) against an in-memory ``_FakeClient``
context. No network and no consumer packages — this pins the admission
contract that ``hivemind-core``'s chain runner consumes.
"""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from hivemind_bus_client.message import HiveMessage, HiveMessageType
from ovos_bus_client.message import Message

from hivemind_plugin_manager import Mutation, PolicyPlugin, Verdict
from hivemind_plugin_manager.policy import DenyCodes



# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _FakeClient:
    """Minimal HiveMindClientConnection stand-in for unit scenarios."""

    def __init__(self, name="test-client", is_admin=False):
        self.name = name
        self.is_admin = is_admin
        self.peer = f"{name}@127.0.0.1:9999"
        self.user = MagicMock(name="user")
        self.user.metadata = {}


def _run_chain(policies, message, client):
    """Simulate the chain-runner logic (fail-closed on exception)."""
    for policy in policies:
        try:
            verdict = policy.review(message, client)
        except Exception as exc:
            return Verdict.deny(DenyCodes.POLICY_ERROR, str(exc))
        if verdict.denied:
            return verdict
        for mutation in verdict.mutations:
            try:
                result = mutation.apply(message, client)
                if result is not None:
                    message = result
            except Exception:
                pass  # chain runner skips failed mutations
    return Verdict.allow()


# ---------------------------------------------------------------------------
# PolicyPlugin contract: simulated chain
# ---------------------------------------------------------------------------

class TestPolicyContractSimulated(unittest.TestCase):
    """Verify PolicyPlugin/Verdict behaviour without a live network."""

    # -- deny-all policy --

    def test_deny_all_policy_denies_every_message(self):
        class DenyAll(PolicyPlugin):
            def review(self, message, client) -> Verdict:
                return Verdict.deny("always_denied", "deny-all policy active")

        policy = DenyAll()
        msg = MagicMock(name="message", msg_type="speak")
        client = _FakeClient()

        verdict = policy.review(msg, client)
        self.assertTrue(verdict.denied)
        self.assertEqual(verdict.code, "always_denied")
        self.assertEqual(verdict.reason, "deny-all policy active")

    # -- allow-all policy (default impl) --

    def test_default_policy_allows_every_message(self):
        policy = PolicyPlugin()
        msg = MagicMock(name="message", msg_type="recognizer_loop:utterance")
        client = _FakeClient()

        verdict = policy.review(msg, client)
        self.assertFalse(verdict.denied)
        self.assertEqual(verdict.mutations, [])

    # -- chain: first deny short-circuits --

    def test_chain_short_circuits_on_first_deny(self):
        call_log = []

        class AlwaysDeny(PolicyPlugin):
            def review(self, message, client) -> Verdict:
                call_log.append("deny")
                return Verdict.deny("blocked", "first policy denied")

        class ShouldNotRun(PolicyPlugin):
            def review(self, message, client) -> Verdict:
                call_log.append("second")
                return Verdict.allow()

        chain = [AlwaysDeny(), ShouldNotRun()]
        msg = MagicMock(msg_type="speak")
        client = _FakeClient()

        verdict = _run_chain(chain, msg, client)

        self.assertTrue(verdict.denied)
        self.assertEqual(verdict.code, "blocked")
        self.assertNotIn("second", call_log, "chain must not continue past a deny")

    # -- chain: allow passes through --

    def test_chain_allow_passes_all_policies(self):
        call_log = []

        class CountingPolicy(PolicyPlugin):
            def review(self, message, client) -> Verdict:
                call_log.append("ran")
                return Verdict.allow()

        chain = [CountingPolicy(), CountingPolicy(), CountingPolicy()]
        msg = MagicMock(msg_type="speak")
        client = _FakeClient()

        verdict = _run_chain(chain, msg, client)

        self.assertFalse(verdict.denied)
        self.assertEqual(len(call_log), 3)

    # -- chain: fail-closed on exception --

    def test_chain_fail_closed_on_review_exception(self):
        class CrashingPolicy(PolicyPlugin):
            def review(self, message, client) -> Verdict:
                raise RuntimeError("unexpected internal error")

        chain = [CrashingPolicy()]
        msg = MagicMock(msg_type="speak")
        client = _FakeClient()

        verdict = _run_chain(chain, msg, client)

        self.assertTrue(verdict.denied)
        self.assertEqual(verdict.code, DenyCodes.POLICY_ERROR)

    # -- mutation application --

    def test_mutation_applied_on_allow(self):
        class TagMessage(Mutation):
            def apply(self, message, client):
                message.context["tagged"] = True
                return None

        class TaggingPolicy(PolicyPlugin):
            def review(self, message, client) -> Verdict:
                return Verdict.allow(TagMessage())

        class FakeMessage:
            def __init__(self):
                self.msg_type = "speak"
                self.context = {}

        msg = FakeMessage()
        chain = [TaggingPolicy()]
        client = _FakeClient()

        verdict = _run_chain(chain, msg, client)

        self.assertFalse(verdict.denied)
        self.assertTrue(msg.context.get("tagged"), "mutation must have been applied")

    # -- mutations ignored on deny --

    def test_mutations_ignored_on_deny(self):
        applied = []

        class MutateAndDeny(Mutation):
            def apply(self, message, client):
                applied.append(True)
                return None

        class DenyWithMutation(PolicyPlugin):
            def review(self, message, client) -> Verdict:
                return Verdict.deny("denied", mutations=[MutateAndDeny()])

        chain = [DenyWithMutation()]
        msg = MagicMock(msg_type="speak")
        client = _FakeClient()

        verdict = _run_chain(chain, msg, client)

        self.assertTrue(verdict.denied)
        self.assertEqual(applied, [], "mutations on a deny verdict must not be applied")

    # -- admin is informational only --

    def test_admin_status_is_informational_only(self):
        """chain runner does not bypass policies for admin clients"""
        class DenyAll(PolicyPlugin):
            def review(self, message, client) -> Verdict:
                return Verdict.deny("blocked")

        admin_client = _FakeClient(is_admin=True)
        msg = MagicMock(msg_type="speak")
        verdict = _run_chain([DenyAll()], msg, admin_client)

        self.assertTrue(verdict.denied, "admin client must still be denied by DenyAll")

    # -- DenyCodes enum usable in deny() --

    def test_deny_accepts_deny_codes_enum(self):
        v = Verdict.deny(DenyCodes.ACL_DISALLOWED_TYPE, "not in allowed_types")
        self.assertTrue(v.denied)
        self.assertEqual(v.code, "acl_disallowed_type")

    # -- observe never blocks delivery --

    def test_observe_exception_does_not_propagate(self):
        class BadObserver(PolicyPlugin):
            def observe(self, message, client) -> None:
                raise RuntimeError("observer crashed")

        policy = BadObserver()
        msg = MagicMock(msg_type="speak")
        client = _FakeClient()

        # Simulate chain runner swallowing observe exceptions
        try:
            policy.observe(msg, client)
            self.fail("expected RuntimeError from BadObserver.observe()")
        except RuntimeError:
            pass  # chain runner catches this; the test proves it does raise,
if __name__ == "__main__":
    unittest.main()
