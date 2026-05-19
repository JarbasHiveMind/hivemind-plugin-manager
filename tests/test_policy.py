"""Tests for hivemind_plugin_manager.policy primitives.

Covers:
- Verdict factories (allow / deny).
- PolicyPlugin default behaviour (no-op allow + observe).
- PolicyPluginFactory entry-point discovery.
- Re-exports from the package top-level.
- Mutation ABC contract.

Concrete mutation subclasses are agent-specific and live with their
consumer (e.g. ``hivemind_ovos_agent_plugin.policy``); they are tested
there.
"""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from hivemind_plugin_manager import (HiveMindPluginTypes, Mutation,
                                     PolicyPlugin, PolicyPluginFactory,
                                     Verdict)


class _FakeMessage:
    """Minimal stand-in for ovos_bus_client.message.Message."""

    def __init__(self, msg_type="t", data=None, context=None):
        self.msg_type = msg_type
        self.data = data if data is not None else {}
        self.context = context if context is not None else {}


# ---------------------------------------------------------------------------
# Verdict
# ---------------------------------------------------------------------------

class TestVerdictFactories(unittest.TestCase):
    def test_allow_default(self):
        v = Verdict.allow()
        self.assertFalse(v.denied)
        self.assertEqual(v.code, "")
        self.assertEqual(v.mutations, [])

    def test_allow_with_mutations(self):
        class _M(Mutation):
            def apply(self, message, client) -> None:
                pass

        m1, m2 = _M(), _M()
        v = Verdict.allow(m1, m2)
        self.assertFalse(v.denied)
        self.assertEqual(v.mutations, [m1, m2])

    def test_deny_basic(self):
        v = Verdict.deny("quota_exceeded")
        self.assertTrue(v.denied)
        self.assertEqual(v.code, "quota_exceeded")
        self.assertEqual(v.reason, "")
        self.assertEqual(v.data, {})

    def test_deny_with_reason_and_data(self):
        v = Verdict.deny("quota_exceeded", "daily limit reached",
                         limit=100, used=100)
        self.assertTrue(v.denied)
        self.assertEqual(v.code, "quota_exceeded")
        self.assertEqual(v.reason, "daily limit reached")
        self.assertEqual(v.data, {"limit": 100, "used": 100})


# ---------------------------------------------------------------------------
# Mutation ABC
# ---------------------------------------------------------------------------

class TestMutationABC(unittest.TestCase):
    def test_cannot_instantiate_abstract(self):
        with self.assertRaises(TypeError):
            Mutation()

    def test_subclass_must_implement_apply(self):
        class _Incomplete(Mutation):
            pass
        with self.assertRaises(TypeError):
            _Incomplete()

    def test_concrete_subclass_works(self):
        class _Concrete(Mutation):
            def apply(self, message, client) -> None:
                message.context["k"] = "v"

        msg = _FakeMessage()
        _Concrete().apply(msg, client=None)
        self.assertEqual(msg.context, {"k": "v"})


# ---------------------------------------------------------------------------
# PolicyPlugin defaults
# ---------------------------------------------------------------------------

class TestPolicyPluginDefaults(unittest.TestCase):
    def test_review_default_allows(self):
        v = PolicyPlugin().review(_FakeMessage(), client=None)
        self.assertFalse(v.denied)
        self.assertEqual(v.mutations, [])

    def test_review_binary_default_allows(self):
        v = PolicyPlugin().review_binary(b"\x00\x01", client=None)
        self.assertFalse(v.denied)

    def test_observe_default_is_noop(self):
        # Just verify it doesn't raise.
        PolicyPlugin().observe(_FakeMessage(), client=None)

    def test_is_subclass_of_sub_protocol(self):
        from hivemind_plugin_manager.protocols import _SubProtocol
        self.assertTrue(issubclass(PolicyPlugin, _SubProtocol))


# ---------------------------------------------------------------------------
# Plugin discovery via the hivemind.policy entry-point group
# ---------------------------------------------------------------------------

class TestPolicyPluginFactory(unittest.TestCase):
    def test_get_class_raises_for_unknown_name(self):
        with patch("hivemind_plugin_manager.find_plugins",
                   return_value={}):
            with self.assertRaises(KeyError):
                PolicyPluginFactory.get_class("missing")

    def test_get_class_returns_registered(self):
        class _MyPolicy(PolicyPlugin):
            pass

        with patch("hivemind_plugin_manager.find_plugins",
                   return_value={"my": _MyPolicy}):
            self.assertIs(PolicyPluginFactory.get_class("my"), _MyPolicy)

    def test_create_passes_config_and_hm_protocol(self):
        class _MyPolicy(PolicyPlugin):
            pass

        with patch("hivemind_plugin_manager.find_plugins",
                   return_value={"my": _MyPolicy}):
            hm = MagicMock(name="hm_protocol")
            plug = PolicyPluginFactory.create("my", config={"a": 1},
                                              hm_protocol=hm)
            self.assertIsInstance(plug, _MyPolicy)
            self.assertEqual(plug.config, {"a": 1})
            self.assertIs(plug.hm_protocol, hm)


# ---------------------------------------------------------------------------
# Re-exports + enum
# ---------------------------------------------------------------------------

class TestPackageReExports(unittest.TestCase):
    def test_primitives_exposed_at_top_level(self):
        import hivemind_plugin_manager as pkg
        for name in ("PolicyPlugin", "Verdict", "Mutation",
                     "PolicyPluginFactory"):
            self.assertTrue(hasattr(pkg, name), f"missing top-level: {name}")

    def test_concrete_mutations_not_re_exported(self):
        """Concrete OVOS-specific mutations now live in hivemind-ovos-agent-plugin."""
        import hivemind_plugin_manager as pkg
        for name in ("AddBlacklistedSkill", "AddBlacklistedIntent",
                     "AddBlacklistedMessageType", "SetSessionField",
                     "SetContextField", "RewriteUtterance"):
            self.assertFalse(hasattr(pkg, name),
                             f"{name} should not be re-exported by the "
                             f"generic plugin-manager")

    def test_policy_enum_value(self):
        self.assertEqual(HiveMindPluginTypes.POLICY.value, "hivemind.policy")


if __name__ == "__main__":
    unittest.main()
