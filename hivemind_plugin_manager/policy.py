"""HiveMind policy plugin primitives.

A **policy plugin** is HiveMind's admission-control point: it sees every
Mycroft ``Message`` (and every binary payload) about to be forwarded to the
agent bus, and can allow it, deny it, or mutate it.

This module ships only the *primitives* — the plugin base class, the
typed verdict, and the :class:`Mutation` abstract base class. Concrete
mutation kinds are agent-specific and live with their consumer (e.g.
the OVOS agent plugin ships ``AddBlacklistedSkill``, ``AddBlacklistedIntent``,
``RewriteUtterance``, etc., since those manipulate OVOS session/message
shape). New agent integrations bring their own mutation set.

Three concepts:

- :class:`PolicyPlugin` — the base class third-party plugins subclass and
  register under the ``hivemind.policy`` entry-point group.
- :class:`Verdict` — what ``review()`` returns. Either allow (optionally
  carrying mutations) or deny (with a code, reason, and structured data
  for the client-side denial message).
- :class:`Mutation` — abstract base for typed actions a policy can request
  on a message that is being allowed. Concrete subclasses live with the
  agent plugin that knows the message shape.

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
from typing import Any, ClassVar, Dict, List, Optional

from hivemind_plugin_manager.protocols import _SubProtocol


# ---------------------------------------------------------------------------
# Mutation ABC
# ---------------------------------------------------------------------------

class Mutation(abc.ABC):
    """A typed action a policy can request on a message being allowed.

    Concrete subclasses are agent-specific and live with the consumer
    (e.g. ``hivemind_ovos_agent_plugin.policy`` for the OVOS bridge).
    Adding new mutation kinds is the explicit, greppable way to extend
    what policies are allowed to change on that agent's messages.
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

    Class attributes (declared on the subclass, not the instance):

    - :attr:`BYPASS_ADMIN`: if ``True``, this policy is skipped entirely
      when ``client.is_admin`` is ``True``. Set this on policies that
      enforce restrictions admins should be exempt from (whitelist
      checks, agent-specific blacklists, session validation, etc.).
      Default ``False`` — quotas, audit, rate-limiting and similar
      policies should apply to admins too.
    """

    BYPASS_ADMIN: ClassVar[bool] = False

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
]
