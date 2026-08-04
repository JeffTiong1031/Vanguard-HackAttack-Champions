"""Actionable rejection and remediation guidance engine.

Translates binary decision reason codes and policy categories into clear,
actionable next steps for employees when an access request or appeal is blocked.
"""

REMEDIATION_MAP = {
    "policy_requirement_not_met": (
        "Access is blocked because organizational compliance rules are not met for this tool or scope. "
        "Review department AI usage guidelines or request a policy exception from your Department Admin."
    ),
    "prohibited_use": (
        "This activity or data category is strictly prohibited under company security policy. "
        "Remove restricted data attributes or switch to an enterprise-approved internal LLM."
    ),
    "insufficient_evidence": (
        "The review request lacked sufficient justification or context. "
        "Submit a new request detailing your business use case and data classification."
    ),
    "scope_mismatch": (
        "The requested scope does not match approved department usage patterns. "
        "Ensure your prompt and tool scope align with your assigned department role."
    ),
    "other": (
        "Access remains strictly blocked under current binary policy governance. "
        "Contact your Department Compliance Officer for further guidance."
    ),
}


def get_remediation_guidance(reason_code: str | None, category: str | None = None) -> dict[str, str]:
    """Generates structured remediation guidance for a blocked decision."""
    code = reason_code or "policy_requirement_not_met"
    summary = REMEDIATION_MAP.get(code, REMEDIATION_MAP["other"])
    
    category_hint = f" Note: This enforcement applies to the '{category}' category." if category else ""

    return {
        "title": f"Access Blocked ({code.replace('_', ' ').title()})",
        "summary": summary + category_hint,
        "action_required": "Remediate flagged data/scope and submit a fresh request or appeal.",
    }
