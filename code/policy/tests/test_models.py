"""A minimal guard on I3: event models must reject fields they don't declare.

This is not the full model test suite -- that arrives in Task 7. It exists
because this task's own self-review question is "would the test still pass if
extra='forbid' were removed from UsageEvent?" and the brief's Step 1 test
(test_app.py::test_healthz) never touches app.models at all, so the answer
would be yes. This closes that gap for the one line the brief calls out as
most important, without duplicating Task 7's scope.
"""
import pytest
from pydantic import ValidationError

from app.models import UsageEvent


def test_usage_event_rejects_a_field_it_does_not_declare():
    """A client trying to smuggle prompt text in gets a 422, not silence."""
    with pytest.raises(ValidationError):
        UsageEvent(
            host="chatgpt.com",
            type="pii_block",
            ts="2026-07-20T00:00:00Z",
            prompt="this should never be accepted",
        )


def test_usage_event_finding_hash_must_be_64_hex_chars():
    with pytest.raises(ValidationError):
        UsageEvent(host="chatgpt.com", type="pii_block", ts="t", finding_hash="not-hex")

    # Accepted: exactly 64 hex chars.
    ok = UsageEvent(host="chatgpt.com", type="pii_block", ts="t", finding_hash="a" * 64)
    assert ok.finding_hash == "a" * 64


def test_usage_event_finding_hash_uppercase_normalized_to_lowercase():
    """Uppercase hex hash is accepted and stored normalized to lowercase."""
    upper_hash = "A" * 64
    event = UsageEvent(host="chatgpt.com", type="pii_block", ts="t", finding_hash=upper_hash)
    assert event.finding_hash == "a" * 64


def test_usage_event_finding_hash_mixed_case_normalized_to_lowercase():
    """Mixed-case hex hash is accepted and stored normalized to lowercase."""
    mixed_hash = "Ab" * 32
    event = UsageEvent(host="chatgpt.com", type="pii_block", ts="t", finding_hash=mixed_hash)
    assert event.finding_hash == ("ab" * 32)


def test_usage_event_finding_hash_rejects_wrong_length():
    """Hashes of incorrect length are rejected."""
    # 63 chars
    with pytest.raises(ValidationError):
        UsageEvent(host="chatgpt.com", type="pii_block", ts="t", finding_hash="a" * 63)

    # 65 chars
    with pytest.raises(ValidationError):
        UsageEvent(host="chatgpt.com", type="pii_block", ts="t", finding_hash="a" * 65)


def test_usage_event_finding_hash_rejects_non_hex_chars():
    """Hashes with non-hex characters are rejected."""
    with pytest.raises(ValidationError):
        UsageEvent(host="chatgpt.com", type="pii_block", ts="t", finding_hash="g" * 64)


def test_usage_event_finding_hash_optional():
    """finding_hash is optional and can be None or omitted."""
    # Omitted
    event1 = UsageEvent(host="chatgpt.com", type="pii_block", ts="t")
    assert event1.finding_hash is None

    # Explicitly None
    event2 = UsageEvent(host="chatgpt.com", type="pii_block", ts="t", finding_hash=None)
    assert event2.finding_hash is None


from app.models import AppealCreate, AppealDecision


def test_appeal_create_defaults_disclosed_text_to_none():
    a = AppealCreate(pseudo_id="p1", decision_type="ethics", category="covert_surveillance", reason="I meant defence", scope_fingerprint="a" * 64)
    assert a.disclosed_text is None


def test_appeal_create_rejects_unknown_field():
    with pytest.raises(ValidationError):
        AppealCreate(pseudo_id="p1", decision_type="pii", category="NRIC", reason="ok", prompt="leaked")


def test_appeal_create_rejects_bad_decision_type():
    with pytest.raises(ValidationError):
        AppealCreate(pseudo_id="p1", decision_type="tool", category="x", reason="ok")


def test_appeal_decision_only_allows_binary_verdicts():
    assert AppealDecision(decision="approved").note is None
    assert AppealDecision(
        decision="blocked", reason_code="policy_requirement_not_met", note="Use an approved tool."
    ).decision == "blocked"
    with pytest.raises(ValidationError):
        AppealDecision(decision="maybe")
    with pytest.raises(ValidationError):
        AppealDecision(decision="blocked")
