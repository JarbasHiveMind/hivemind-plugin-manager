"""HiveMind policy plugin primitives.

A **policy plugin** is HiveMind's admission-control point: it sees every
Mycroft ``Message`` (and every binary payload) about to be forwarded to the
agent bus, and can allow it, deny it, or mutate it.

This module ships only the *primitives* — the plugin base class and the
typed data the chain runner consumes. The actual chain runner lives in
``hivemind-core`` and is the consumer of everything declared here.

Three concepts:

- :class:`PolicyPlugin` — the base class third-party plugins subclass and
  register under the ``hivemind.policy`` entry-point group.
- :class:`Verdict` — what ``review()`` returns. Either allow (optionally
  carrying mutations) or deny (with a code, reason, and structured data
  for the client-side denial message).
- :class:`Mutation` — typed actions a policy can request on a message that
  is being allowed. Stdlib subclasses cover the common cases; new mutation
  kinds are added here so the set is greppable and the chain runner stays
  honest about what plugins are allowed to change.

Design references:

- https://github.com/JarbasHiveMind/HiveMind-core/issues/85 — admission
  chain spec.
- The OVOS pipeline's utterance-transformer pattern — same allow/mutate/
  veto idea, lifted from ``recognizer_loop:utterance`` to arbitrary bus
  messages, with a typed ``Verdict`` for cross-network denial reporting.
"""
from __future__ import annotations

import abc
import dataclasses
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from ovos_utils.log import LOG

from hivemind_plugin_manager.protocols import _SubProtocol


# ---------------------------------------------------------------------------
# Mutations
# ---------------------------------------------------------------------------

class Mutation(abc.ABC):
    """A typed action a policy can request on a message being allowed.

    Adding new mutation kinds is the explicit, greppable way to extend
    what policies are allowed to change. Don't introduce a free-form
    dict-merge mutation; if there's a recurring need, add a typed
    subclass here.
    """

    @abc.abstractmethod
    def apply(self, message, client) -> None:
        """Mutate ``message`` in place. ``client`` is the
        ``HiveMindClientConnection`` that originated the message, supplied
        so mutations can read identity / session state if needed.

        Implementations must be best-effort: an exception here is logged
        and skipped by the chain runner, so individual mutation failures
        don't kill the whole admission step.
        """
        raise NotImplementedError


@dataclass
class AddBlacklistedSkill(Mutation):
    """Add a skill_id to ``message.context["session"]["blacklisted_skills"]``."""
    skill_id: str

    def apply(self, message, client) -> None:
        session = _ensure_session(message)
        blacklist = session.setdefault("blacklisted_skills", [])
        if self.skill_id not in blacklist:
            blacklist.append(self.skill_id)


@dataclass
class AddBlacklistedIntent(Mutation):
    """Add an intent name to ``message.context["session"]["blacklisted_intents"]``."""
    intent_name: str

    def apply(self, message, client) -> None:
        session = _ensure_session(message)
        blacklist = session.setdefault("blacklisted_intents", [])
        if self.intent_name not in blacklist:
            blacklist.append(self.intent_name)


@dataclass
class AddBlacklistedMessageType(Mutation):
    """Add a Mycroft message-type pattern to a session-level message blacklist."""
    msg_type: str

    def apply(self, message, client) -> None:
        session = _ensure_session(message)
        blacklist = session.setdefault("blacklisted_message_types", [])
        if self.msg_type not in blacklist:
            blacklist.append(self.msg_type)


@dataclass
class SetSessionField(Mutation):
    """Set a single key in ``message.context["session"]``."""
    key: str
    value: Any

    def apply(self, message, client) -> None:
        session = _ensure_session(message)
        session[self.key] = self.value


@dataclass
class SetContextField(Mutation):
    """Set a key path in ``message.context``.

    ``path`` is a tuple of dict keys. Intermediate dicts are created if
    missing. Use this when a policy needs to write outside the
    ``session`` subtree.
    """
    path: Tuple[str, ...]
    value: Any

    def apply(self, message, client) -> None:
        if not self.path:
            return
        target = message.context
        if not isinstance(target, dict):
            target = {}
            message.context = target
        for key in self.path[:-1]:
            nxt = target.get(key)
            if not isinstance(nxt, dict):
                nxt = {}
                target[key] = nxt
            target = nxt
        target[self.path[-1]] = self.value


@dataclass
class RewriteUtterance(Mutation):
    """Replace the utterance text in a ``recognizer_loop:utterance``
    Mycroft message. Silent no-op on any other ``msg_type``."""
    text: str

    def apply(self, message, client) -> None:
        if getattr(message, "msg_type", None) != "recognizer_loop:utterance":
            return
        if not isinstance(message.data, dict):
            return
        message.data["utterances"] = [self.text]


def _ensure_session(message) -> Dict[str, Any]:
    """Return ``message.context["session"]``, creating it if missing."""
    if not isinstance(message.context, dict):
        message.context = {}
    session = message.context.get("session")
    if not isinstance(session, dict):
        session = {}
        message.context["session"] = session
    return session


# ---------------------------------------------------------------------------
# Verdict
# ---------------------------------------------------------------------------

@dataclass
class Verdict:
    """The answer a :class:`PolicyPlugin` returns from ``review()``.

    Either denying (the message will not be emitted; the client receives
    a ``hive.policy.denied`` notification carrying ``code`` / ``reason`` /
    ``data``) or allowing — optionally with one or more
    :class:`Mutation` objects describing what the policy wants changed on
    the message before it proceeds.

    Mutations attached to a *denying* verdict are ignored. The chain
    short-circuits on the first denial.
    """

    denied: bool = False
    code: str = ""
    reason: str = ""
    data: Dict[str, Any] = field(default_factory=dict)
    mutations: List[Mutation] = field(default_factory=list)

    @classmethod
    def allow(cls, *mutations: Mutation) -> "Verdict":
        """Construct an allow-verdict, optionally carrying mutations."""
        return cls(mutations=list(mutations))

    @classmethod
    def deny(cls, code: str, reason: str = "", **data: Any) -> "Verdict":
        """Construct a deny-verdict.

        ``code`` is a stable machine-readable string
        (e.g. ``"quota_exceeded"``, ``"intent_blacklisted"``,
        ``"policy_error"``). ``reason`` is human-readable. Extra keyword
        arguments are forwarded into ``data`` for the client-side
        denial message.
        """
        return cls(denied=True, code=code, reason=reason, data=dict(data))


# ---------------------------------------------------------------------------
# PolicyPlugin
# ---------------------------------------------------------------------------

@dataclass
class PolicyPlugin(_SubProtocol):
    """Base class for HiveMind policy plugins.

    Subclasses override ``review`` (and optionally ``review_binary``
    / ``observe``). They are loaded by ``hivemind-core`` via the
    ``hivemind.policy`` entry-point group and invoked in the order
    declared by the operator's ``policy.chain`` config.

    Three hooks, all synchronous (matches the broader ``_SubProtocol``
    contract used by other plugin types in this package):

    - :meth:`review` — for Mycroft ``Message`` instances. Called before
      ``bus.emit()``.
    - :meth:`review_binary` — for binary payloads (e.g. raw audio).
      Default impl returns ``Verdict.allow()`` so plugins ignore
      binaries unless they care.
    - :meth:`observe` — called after a message was successfully
      emitted to the bus. Use for counters, audit logs, telemetry. Must
      not raise.

    The chain runner in ``hivemind-core`` catches any unhandled
    exception in ``review`` / ``review_binary`` and treats it as
    ``Verdict.deny("policy_error", ...)`` (fail-closed, no operator
    knob). ``observe`` exceptions are logged and swallowed.
    """

    config: Dict[str, Any] = dataclasses.field(default_factory=dict)
    hm_protocol: Optional["HiveMindListenerProtocol"] = None

    def review(self, message, client) -> Verdict:
        """Inspect a Mycroft Message about to be forwarded to the agent bus.

        Override to allow/deny/mutate. The default implementation allows
        everything — subclasses are expected to be opinionated.
        """
        return Verdict.allow()

    def review_binary(self, payload, client) -> Verdict:
        """Inspect a binary payload about to be forwarded to the agent
        bus. Default: allow."""
        return Verdict.allow()

    def observe(self, message, client) -> None:
        """Called after a Message was successfully emitted to the bus.

        Use for counters, audit logs, telemetry. Must not raise — if
        you can't help yourself, wrap your code in ``try/except`` and
        log it; the chain runner does the same as a safety net.
        """
        pass


__all__ = [
    "PolicyPlugin",
    "Verdict",
    "Mutation",
    "AddBlacklistedSkill",
    "AddBlacklistedIntent",
    "AddBlacklistedMessageType",
    "SetSessionField",
    "SetContextField",
    "RewriteUtterance",
]
