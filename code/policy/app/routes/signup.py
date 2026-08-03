from fastapi import APIRouter

from app.deps import get_conn
from app.models import SignupRequest
from app.seed import seed_company

router = APIRouter()


@router.post("/v1/signup", status_code=201)
async def signup(body: SignupRequest) -> dict[str, str]:
    """Create a company and return its Company Admin secret ONCE.

    The plaintext is returned here and never again -- only its SHA-256 is
    stored (orgs.admin_token_hash)."""
    org_id, secret = seed_company(get_conn(), body.company_name)
    return {"org_id": org_id, "secret": secret}
