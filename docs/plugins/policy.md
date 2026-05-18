# Policy Plugin Guide

A **policy plugin** is HiveMind's admission-control point: it sees every
Mycroft `Message` (and every binary payload) about to be forwarded to the
agent bus, and can **allow** it, **deny** it, or **mutate** it. Multiple
policies form a chain, executed in an operator-declared order.

Policies are the mechanism for dynamic ACL checks that depend on
current server state — per-API-key quotas, rate limits, parental
controls, audit logs, sensitive-intent confirmation. Static ACLs that
live on the `Client` record (allowed_types, blacklists) are themselves
expressed as built-in policy plugins by `hivemind-core`.

> Architecture context: see
> [HiveMind-core#85](https://github.com/JarbasHiveMind/HiveMind-core/issues/85).
> This document covers the **plugin author** surface defined in
> `hivemind-plugin-manager`. The chain runner that consumes these
> plugins lives in `hivemind-core`.

---

## Base Class

```python
@dataclass
class PolicyPlugin(_SubProtocol):
    """Base class for HiveMind policy plugins.

    Subclasses override review (and optionally review_binary / observe).
    They are loaded by hivemind-core via the hivemind.policy
    entry-point group and invoked in the order declared by the
    operator's policy.chain config.
    """
    config: Dict[str, Any] = dataclasses.field(default_factory=dict)
    hm_protocol: Optional['HiveMindListenerProtocol'] = None

    def review(self, message, client) -> Verdict: ...
    def review_binary(self, payload, client) -> Verdict: ...
    def observe(self, message, client) -> None: ...
```

Source: `hivemind_plugin_manager/policy.py`.

`PolicyPlugin` extends `_SubProtocol`
(`protocols.py:35`), which provides `.identity`, `.database`, and
`.clients` properties — see [Concepts](../concepts.md#_subprotocol-base).

---

## Hooks

| Method | Called when | Default impl |
|---|---|---|
| `review(message, client)` | A Mycroft `Message` is about to be forwarded to the agent bus. | Returns `Verdict.allow()`. |
| `review_binary(payload, client)` | A binary payload (e.g. raw audio) is about to be forwarded. | Returns `Verdict.allow()`. |
| `observe(message, client)` | A message was successfully emitted to the bus. Use for counters, audit logs, telemetry. | No-op. |

All three are **synchronous**. The chain runner in `hivemind-core` is
synchronous; introducing an async variant would require a coordinated
change across `hivemind-plugin-manager`, `hivemind-core`, and every
agent protocol — out of scope for this contract.

**Failure semantics** (enforced by the chain runner, not the plugin):

- Unhandled exception in `review` / `review_binary` → treated as
  `Verdict.deny("policy_error", reason="policy crashed")`. Fail-closed.
- Unhandled exception in `observe` → logged and swallowed. Observation
  never blocks delivery.
- Unhandled exception in a `Mutation.apply` → logged and skipped; the
  message proceeds with whatever mutations did apply.

---

## `Verdict`

The return value of `review()` and `review_binary()`.

```python
@dataclass
class Verdict:
    denied: bool = False
    code: str = ""
    reason: str = ""
    data: Dict[str, Any] = field(default_factory=dict)
    mutations: List[Mutation] = field(default_factory=list)

    @classmethod
    def allow(cls, *mutations: Mutation) -> "Verdict": ...
    @classmethod
    def deny(cls, code: str, reason: str = "", **data: Any) -> "Verdict": ...
```

A verdict is either denying or allowing-with-mutations:

```python
# Allow, no changes
return Verdict.allow()

# Allow, with mutations
return Verdict.allow(
    AddBlacklistedSkill("adult.skill"),
    SetSessionField("filter_level", "family"),
)

# Deny — short-circuits the chain
return Verdict.deny(
    "quota_exceeded",
    "daily limit of 100 reached",
    limit=100, used=100, window="1d",
)
```

`code` is a **stable, machine-readable** string clients can switch on
(`"quota_exceeded"`, `"intent_blacklisted"`, `"policy_error"`). `reason`
is human-readable. Extra keyword arguments go into `data`, which the
chain runner forwards to the client as part of the `hive.policy.denied`
notification message.

Mutations attached to a *denying* verdict are ignored.

---

## `Mutation`

Typed actions a policy can request on a message being allowed. Adding
new mutation kinds is the explicit, greppable way to extend what
policies are allowed to change — there is no free-form dict-merge
mutation by design.

| Class | Effect |
|---|---|
| `AddBlacklistedSkill(skill_id)` | Appends to `message.context["session"]["blacklisted_skills"]`. |
| `AddBlacklistedIntent(intent_name)` | Appends to `message.context["session"]["blacklisted_intents"]`. |
| `AddBlacklistedMessageType(msg_type)` | Appends to `message.context["session"]["blacklisted_message_types"]`. |
| `SetSessionField(key, value)` | Sets one key in `message.context["session"]`. |
| `SetContextField(path, value)` | Sets a nested key in `message.context` (tuple-typed path). |
| `RewriteUtterance(text)` | Replaces `data["utterances"]` on a `recognizer_loop:utterance` message. Silent no-op on any other `msg_type`. |

All mutations are idempotent on list mutations (no duplicates) and
robust to non-dict context/session values (they coerce). Source:
`hivemind_plugin_manager/policy.py`.

If you need a new mutation kind, add it here in
`hivemind-plugin-manager` rather than as a free-form mechanism in your
plugin — the chain runner is meant to know what plugins are allowed to
change.

---

## Registering a plugin

In your package's `setup.py` / `pyproject.toml`, register under
`hivemind.policy`:

```toml
[project.entry-points."hivemind.policy"]
"hivemind-intent-quota-policy" = "hivemind_intent_quota:IntentQuotaPolicy"
```

Operators then enable your policy in `hivemind-core`'s `policy` config
block:

```json
{
  "policy": {
    "chain": [
      "hivemind-client-acl-policy",
      "hivemind-intent-quota-policy"
    ],
    "hivemind-intent-quota-policy": {
      "per_day": 1000,
      "redis_url": "redis://localhost:6379/0"
    }
  }
}
```

---

## Example: intent quota plugin

A small, realistic policy that tracks per-account utterance counts in
Redis and denies once a daily limit is reached. Uses `Client.metadata`
(see [Database](database.md)) to group counters by `account_id`, so a
deployment can have multiple HiveMind clients sharing one quota.

```python
from hivemind_plugin_manager import PolicyPlugin, Verdict


class IntentQuotaPolicy(PolicyPlugin):
    def __init__(self, config, hm_protocol=None):
        super().__init__(config=config, hm_protocol=hm_protocol)
        self.per_day = config.get("per_day", 1000)
        self.store = RedisCounter(config["redis_url"])

    def review(self, message, client):
        if message.msg_type != "recognizer_loop:utterance":
            return Verdict.allow()
        account = client.user.metadata.get("account_id") or client.key
        used = self.store.get(account, window="1d")
        if used >= self.per_day:
            return Verdict.deny(
                "quota_exceeded",
                f"daily limit {self.per_day} reached",
                limit=self.per_day, used=used,
            )
        return Verdict.allow()

    def observe(self, message, client):
        # Only count messages that were actually emitted to the bus —
        # denials don't increment the counter.
        if message.msg_type != "recognizer_loop:utterance":
            return
        account = client.user.metadata.get("account_id") or client.key
        self.store.incr(account, window="1d")
```

That's the whole plugin: ~20 lines. The chain runner handles the rest
(emitting `hive.policy.denied` to the client, exception fail-closed,
running multiple policies in the configured order, applying
mutations).

---

## Factory

```python
from hivemind_plugin_manager import PolicyPluginFactory

cls = PolicyPluginFactory.get_class("hivemind-intent-quota-policy")
plugin = PolicyPluginFactory.create(
    "hivemind-intent-quota-policy",
    config={"per_day": 100, "redis_url": "redis://..."},
    hm_protocol=my_hm_protocol,
)
```

Source: `hivemind_plugin_manager/__init__.py` — `PolicyPluginFactory`.

`hivemind-core` uses this factory internally to assemble the configured
chain at startup; most plugin authors will never call it directly.
