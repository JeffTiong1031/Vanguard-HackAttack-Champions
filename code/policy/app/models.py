"""Wire models.

The event models are where I3 is enforced structurally: `extra="forbid"` means
a client that tries to send prompt text gets a 422 rather than having the field
silently ignored. A field that is ignored today is a field someone stores
tomorrow.
"""
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class EnrollRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    token: str


class ToolPolicy(BaseModel):
    llm_id: str
    host: str
    display_name: str
    status: Literal["approved", "blocked"]


class CategoryPolicy(BaseModel):
    key: str
    label: str
    enabled: bool


class PolicyBody(BaseModel):
    org_id: str
    org_name: str
    version: int
    tools: list[ToolPolicy]
    categories: list[CategoryPolicy]


class EnrollResponse(BaseModel):
    org_id: str
    org_name: str
    pseudo_id: str
    department: str
    department_id: str | None = None
    policy: PolicyBody


class AccessRequestCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pseudo_id: str
    llm_id: str
    reason: str = Field(min_length=1, max_length=500)


DecisionReason = Literal[
    "policy_requirement_not_met",
    "prohibited_use",
    "insufficient_evidence",
    "scope_mismatch",
    "other",
]


class BinaryDecision(BaseModel):
    """A durable access decision. There is no provisional third outcome."""

    model_config = ConfigDict(extra="forbid")
    decision: Literal["approved", "blocked"]
    reason_code: Optional[DecisionReason] = None
    note: Optional[str] = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def blocked_decisions_explain_the_next_step(self):
        if self.decision == "blocked" and (not self.reason_code or not (self.note or "").strip()):
            raise ValueError("blocked decisions require reason_code and an actionable note")
        return self


class UsageEvent(BaseModel):
    """One governance event.

    There is no field for prompt text, and `extra="forbid"` means one cannot
    be smuggled in. `finding_hash` is a salted hash reference (I3).
    """
    model_config = ConfigDict(extra="forbid")

    host: str
    type: Literal["visit_unapproved", "warn_shown", "request_sent", "ethics_block", "pii_block"]
    category: Optional[str] = None
    finding_hash: Optional[str] = None
    ts: str

    @field_validator("finding_hash")
    @classmethod
    def _hash_is_hex64(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if len(v) != 64 or any(c not in "0123456789abcdef" for c in v.lower()):
            raise ValueError("finding_hash must be a 64-character hex digest")
        return v.lower()


class EventBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pseudo_id: str
    events: list[UsageEvent] = Field(max_length=100)


class AdminLogin(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: Literal["company", "department"]
    secret: str = Field(max_length=200)


class SignupRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    company_name: str = Field(min_length=1, max_length=120)


class AppealCreate(BaseModel):
    """An employee contesting an automated enforcement decision.

    I3: there is NO field for the prompt by default. `disclosed_text` is the one
    place raw text can enter, and only when the employee ticks the opt-in box in
    the modal. extra="forbid" means a client cannot smuggle the prompt under some
    other key.
    """
    model_config = ConfigDict(extra="forbid")
    pseudo_id: str
    decision_type: Literal["ethics", "pii"]
    category: str
    reason: str = Field(min_length=1, max_length=500)
    disclosed_text: Optional[str] = Field(default=None, max_length=4000)
    # Defines the exact, persistent approval scope without carrying prompt text.
    scope_fingerprint: Optional[str] = Field(default=None, min_length=64, max_length=64)

    @field_validator("scope_fingerprint")
    @classmethod
    def _scope_is_hex64(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        if any(c not in "0123456789abcdef" for c in value.lower()):
            raise ValueError("scope_fingerprint must be a 64-character hex digest")
        return value.lower()

    @model_validator(mode="after")
    def ethics_appeals_have_a_fixed_scope(self):
        if self.decision_type == "ethics" and self.scope_fingerprint is None:
            raise ValueError("ethics appeals require scope_fingerprint")
        return self


class AccessDecision(BinaryDecision):
    pass


class AppealDecision(BinaryDecision):
    pass
