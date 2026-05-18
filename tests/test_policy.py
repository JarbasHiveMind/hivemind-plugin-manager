"""Tests for hivemind_plugin_manager.policy.

Covers:
- Mutation subclasses (apply behaviour + idempotency).
- Verdict factories (allow / deny).
- PolicyPlugin default behaviour (no-op allow + observe).
- PolicyPluginFactory entry-point discovery.
- Re-exports from the package top-level.
"""
from __future__ import annotations

import dataclasses
import unittest
from unittest.mock import MagicMock, patch

from hivemind_plugin_manager import (HiveMindPluginTypes, PolicyPlugin,
                                     PolicyPluginFactory, Verdict)
from hivemind_plugin_manager.policy import (AddBlacklistedIntent,
                                            AddBlacklistedMessageType,
                                            AddBlacklistedSkill, Mutation,
                                            RewriteUtterance, SetContextField,
                                            SetSessionField)


class _FakeMessage:
    """Minimal stand-in for ovos_bus_client.message.Message — just enough
    surface for the Mutation tests. Avoids the bus_client dependency in
    these unit tests."""

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
        m = AddBlacklistedSkill("foo")
        v = Verdict.allow(m, AddBlacklistedIntent("bar"))
        self.assertFalse(v.denied)
        self.assertEqual(len(v.mutations), 2)
        self.assertIs(v.mutations[0], m)

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
# Mutations
# ---------------------------------------------------------------------------

class TestAddBlacklistedSkill(unittest.TestCase):
    def test_creates_list_when_missing(self):
        msg = _FakeMessage()
        AddBlacklistedSkill("weather.skill").apply(msg, client=None)
        self.assertEqual(
            msg.context["session"]["blacklisted_skills"],
            ["weather.skill"],
        )

    def test_appends_to_existing(self):
        msg = _FakeMessage(context={"session": {"blacklisted_skills": ["a"]}})
        AddBlacklistedSkill("b").apply(msg, client=None)
        self.assertEqual(
            msg.context["session"]["blacklisted_skills"], ["a", "b"],
        )

    def test_dedupes(self):
        msg = _FakeMessage(context={"session": {"blacklisted_skills": ["a"]}})
        AddBlacklistedSkill("a").apply(msg, client=None)
        self.assertEqual(msg.context["session"]["blacklisted_skills"], ["a"])

    def test_recovers_from_non_dict_session(self):
        msg = _FakeMessage(context={"session": "garbage"})
        AddBlacklistedSkill("x").apply(msg, client=None)
        self.assertEqual(msg.context["session"], {"blacklisted_skills": ["x"]})

    def test_recovers_from_non_dict_context(self):
        msg = _FakeMessage(context="garbage")
        AddBlacklistedSkill("x").apply(msg, client=None)
        self.assertEqual(msg.context, {"session": {"blacklisted_skills": ["x"]}})


class TestAddBlacklistedIntent(unittest.TestCase):
    def test_dedupes_and_appends(self):
        msg = _FakeMessage()
        AddBlacklistedIntent("intent.a").apply(msg, client=None)
        AddBlacklistedIntent("intent.b").apply(msg, client=None)
        AddBlacklistedIntent("intent.a").apply(msg, client=None)
        self.assertEqual(
            msg.context["session"]["blacklisted_intents"],
            ["intent.a", "intent.b"],
        )


class TestAddBlacklistedMessageType(unittest.TestCase):
    def test_appends(self):
        msg = _FakeMessage()
        AddBlacklistedMessageType("speak").apply(msg, client=None)
        self.assertEqual(
            msg.context["session"]["blacklisted_message_types"], ["speak"],
        )


class TestSetSessionField(unittest.TestCase):
    def test_sets_field(self):
        msg = _FakeMessage()
        SetSessionField("lang", "pt-pt").apply(msg, client=None)
        self.assertEqual(msg.context["session"]["lang"], "pt-pt")

    def test_overwrites_existing(self):
        msg = _FakeMessage(context={"session": {"lang": "en-us"}})
        SetSessionField("lang", "de-de").apply(msg, client=None)
        self.assertEqual(msg.context["session"]["lang"], "de-de")


class TestSetContextField(unittest.TestCase):
    def test_sets_top_level_key(self):
        msg = _FakeMessage()
        SetContextField(("source",), "policy").apply(msg, client=None)
        self.assertEqual(msg.context["source"], "policy")

    def test_creates_nested_path(self):
        msg = _FakeMessage()
        SetContextField(("a", "b", "c"), 1).apply(msg, client=None)
        self.assertEqual(msg.context["a"]["b"]["c"], 1)

    def test_overwrites_non_dict_intermediate(self):
        msg = _FakeMessage(context={"a": "scalar"})
        SetContextField(("a", "b"), 1).apply(msg, client=None)
        self.assertEqual(msg.context["a"], {"b": 1})

    def test_empty_path_is_noop(self):
        msg = _FakeMessage(context={"k": "v"})
        SetContextField((), "anything").apply(msg, client=None)
        self.assertEqual(msg.context, {"k": "v"})

    def test_non_dict_context_is_replaced(self):
        msg = _FakeMessage(context="garbage")
        SetContextField(("k",), "v").apply(msg, client=None)
        self.assertEqual(msg.context, {"k": "v"})


class TestRewriteUtterance(unittest.TestCase):
    def test_rewrites_recognizer_loop_utterance(self):
        msg = _FakeMessage(
            "recognizer_loop:utterance",
            data={"utterances": ["old"], "lang": "en-us"},
        )
        RewriteUtterance("new").apply(msg, client=None)
        self.assertEqual(msg.data["utterances"], ["new"])
        self.assertEqual(msg.data["lang"], "en-us")  # unrelated fields preserved

    def test_noop_for_other_msg_types(self):
        msg = _FakeMessage("speak", data={"utterance": "hi"})
        RewriteUtterance("new").apply(msg, client=None)
        self.assertEqual(msg.data, {"utterance": "hi"})  # unchanged

    def test_noop_when_data_is_not_dict(self):
        msg = _FakeMessage("recognizer_loop:utterance", data=None)
        msg.data = ["not", "a", "dict"]
        RewriteUtterance("x").apply(msg, client=None)
        self.assertEqual(msg.data, ["not", "a", "dict"])


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
    def test_policy_types_exposed_at_top_level(self):
        import hivemind_plugin_manager as pkg
        for name in ("PolicyPlugin", "Verdict", "Mutation",
                     "AddBlacklistedSkill", "AddBlacklistedIntent",
                     "AddBlacklistedMessageType", "SetSessionField",
                     "SetContextField", "RewriteUtterance"):
            self.assertTrue(hasattr(pkg, name), f"missing top-level: {name}")

    def test_policy_enum_value(self):
        self.assertEqual(HiveMindPluginTypes.POLICY.value, "hivemind.policy")


if __name__ == "__main__":
    unittest.main()
