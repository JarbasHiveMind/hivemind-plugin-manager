"""Minimal example policy plugin.

Package entry point:

    [options.entry_points]
    hivemind.policy =
        example-utterance-limit = my_plugin:UtteranceLimitPolicy

HiveMind Core config:

    {
        "policy": {
            "example-utterance-limit": {
                "limit": 10
            }
        }
    }

This example keeps counts in memory so it is only useful for tests or demos.
Production quota plugins should use persistent storage.
"""

from collections import defaultdict

from hivemind_plugin_manager.protocols import PolicyDecision, PolicyProtocol


class UtteranceLimitPolicy(PolicyProtocol):
    """Deny recognizer utterances after a per-api-key limit."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.limit = int(self.config.get("limit", 10))
        self.counts = defaultdict(int)

    def authorize_bus_message(self, message, context):
        if message.msg_type != "recognizer_loop:utterance":
            return PolicyDecision()

        api_key = getattr(context.user, "api_key", "") or context.client.key
        if self.counts[api_key] >= self.limit:
            return PolicyDecision(
                allowed=False,
                code="utterance_limit_exceeded",
                reason="utterance limit exceeded",
                data={"limit": self.limit},
            )

        return PolicyDecision()

    def record_bus_message(self, message, context, result=None):
        if message.msg_type != "recognizer_loop:utterance":
            return

        api_key = getattr(context.user, "api_key", "") or context.client.key
        self.counts[api_key] += 1
