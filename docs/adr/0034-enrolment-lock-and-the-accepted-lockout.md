# ADR 0034 — Leaving an org requires admin revocation, and the lockout is accepted for now

**Date:** 2026-08-06
**Status:** Accepted (founder decision)
**Relates to:** decision #3 · [ADR 0014](0014-degrade-to-advisory-never-fail-closed.md) ·
[ADR 0016](0016-mvp-first-sequencing.md) · Piece 1 of
[the token-identity plan](../superpowers/plans/2026-08-05-token-identity-and-generic-protection.md)

## Context

The enrolment token is now a person's durable identity: enrolling twice with one token
resolves to one employee, and revoking the token deprovisions that lineage server-side
(HTTP 403 `enrolment revoked` from `/v1/events` and `/v1/policy`).

The founder's requirement is that **enterprise mode is a commitment, not a toggle** — an
enrolled user should not be able to walk out of the org's protection on their own; leaving
requires the admin to revoke.

Piece 1 first gated only the **Switch to Personal** button. Review found that the gate
protected the wrong action: the **Disconnect** button in the same panel called the identical
`clearEnrolment()` — purely local, no server call — and `flushNow()` already drops all event
reporting whenever `getEnrolment()` is null. One unguarded click therefore achieved exactly
the outcome the gate existed to prevent. **Gating one of two doors to the same room is not a
control.**

Both are now gated on one predicate, `canSwitchToPersonal(enrolment)`, short-circuited
inside each handler rather than only via the DOM `disabled` attribute.

## The problem that created

Closing the second door removed the only working escape hatch. Traced end to end:

- `handleRevoked()` fires **only** from `refreshPolicy()`, and **only** on a 403 whose body
  is exactly `{"detail": "enrolment revoked"}`.
- Every other failure — network unreachable, timeout, wrong error shape — falls to the
  cached-policy branch and never touches `enrolment`.
- A **deleted** token produces no 403 at all, because `enrolment_is_revoked()` deliberately
  returns `False` for a missing row. That is not an oversight: it is the same decision that
  protects the ~948 legacy employees who predate `enroll_token_id` and have no lineage to
  revoke.

So a user whose policy service is down, or whose token row was deleted rather than revoked,
has no in-app way out. Their only escape is removing the extension entirely — which forfeits
**all** local protection, strictly worse than the Personal mode the gate exists to force.

## Options

| | Option | Cost |
|---|---|---|
| **A** | **Time-boxed local override** — after N days unreachable, allow self-unenrolment | Real work; N is another unmeasured number; a defector can simply go offline for N days |
| **B** | **Admin support path** — an out-of-band reset code | Real work; needs an admin UI and a delivery channel |
| **C** | **Accept it for this phase** — ops rule: *revoke, don't delete* | Zero; leaves a known trap |

## Decision

**C.** Accept the lockout for the team test and the pitch. Do not build A or B yet.

The founder's reasoning, recorded verbatim in substance:

- The demo path that matters is **admin revokes → extension drops to Personal → the user
  cannot stay in company mode**. That path works and is what a buyer is shown.
- **There is no Delete-token button in the product**, so the deleted-row case is
  out of scope for now. It is governed by an **operational rule — revoke, don't delete** —
  rather than by code.
- **Offline behaviour is stay-enrolled-until-reconnect**, which is acceptable for this phase.

**Revisit trigger — this is the part that must not be lost:** if real *"stuck forever while
online"* cases appear, **revisit option A before any real customer fleet.** The trigger is an
observation, not a date.

## Consequences

- ✅ The control is real: both doors are shut, and the gate is enforced in the handler, not
  merely as a DOM hint.
- ✅ Consistent with ADR 0014 rather than contradicting it. ADR 0014 forbids a *dead engine*
  bricking the user's browsing; this gate does not touch scanning. **A revoked or
  disconnected user keeps full local PII protection** — verified by tracing `scanInto`,
  `runL1` and `l2Scan`, none of which depend on enrolment or policy.
- 🔴 **A known trap ships.** It is written down here rather than discovered later, and it is
  bounded by an ops rule that is only as good as the ops discipline behind it. **If a
  Delete-token button is ever added to the admin console, this ADR's premise dies with it** —
  that is the change to watch for.
- 🟠 The `/v1/events` 403 has **no client-side reaction**: `flushNow()` throws and re-queues.
  In practice the guard's 5-second policy tick clears the enrolment first and the queue is
  then dropped, so the window is small — but the events path is not itself a revocation
  detector, and nothing should be written that assumes it is.
- 🟠 **Switch to Personal** and **Disconnect** are now gated identically and carry identical
  disabled copy, while still differing when enabled (one leaves enterprise mode, the other
  returns to the join form). Whether they should remain two buttons is a UI question the
  founder owns; it is deliberately unresolved rather than silently merged.
