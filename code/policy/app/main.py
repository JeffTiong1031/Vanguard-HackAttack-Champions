import logging
import mimetypes

# Fix Windows registry MIME type issue where .js files default to text/plain
mimetypes.add_type("text/javascript", ".js")
mimetypes.add_type("text/css", ".css")

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.requests import Request

from app.deps import get_conn

# No APM, no body capture. Same posture as code/backend/app/main.py, and this
# module is where a reviewer looks to confirm it.
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("vanguard.policy")

app = FastAPI(title="Vanguard policy", version="0.1.0")

# The extension calls this from its background service worker, whose origin is
# chrome-extension://<id>. Demo-grade: allow all origins. Production pins the
# extension id.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["content-type", "if-none-match", "x-vanguard-session"],
    expose_headers=["etag"],
)


@app.exception_handler(RequestValidationError)
async def _validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Return WHICH field was rejected, never WHAT was in it.

    `UsageEvent` and `EnrollRequest` both set `extra="forbid"` so that a
    field we never wanted stored (prompt text, an enrolment token typed
    under the wrong key) gets a 422 instead of being written to SQLite or
    our own logs. That defence has a hole FastAPI's DEFAULT handler doesn't
    close: pydantic's `RequestValidationError.errors()` includes the
    offending value verbatim under `input` -- for `extra_forbidden` that is
    literally the rejected field's value, and for a `missing`-field error
    it can be the *entire request body*, secret fields and all (proven
    while testing this handler: a mistyped `token` key surfaces the whole
    body, token included, under the `missing` error's `input`). FastAPI's
    default handler serialises `errors()` straight into the response, so
    the value that was never supposed to reach SQLite or our logs reaches
    an HTTP response body instead -- exactly the kind of place a reverse
    proxy, API gateway, or error-tracking SDK captures by default, per this
    service's own posture on APM tools that capture bodies "and nobody
    notices for six months."

    Registered app-wide (not per-router): every model in `app/models.py`
    that sets `extra="forbid"` is protected by construction, including ones
    added later. `type`, `loc`, and `msg` are kept -- a developer still
    needs to know WHICH field was rejected and WHY. Only `input` (and any
    non-JSON-serialisable `ctx`, which some pydantic error kinds attach) is
    stripped. Do not "simplify" this back to FastAPI's default handler: the
    default is the vulnerability.

    🔴 ONE OBLIGATION THIS HANDLER CANNOT DISCHARGE FOR YOU. `msg` is passed
    through untouched, and a custom `field_validator` controls its text. If
    you ever write `raise ValueError(f"bad reason: {v}")`, the value you
    just refused travels out in `msg` and this scrubbing buys nothing.
    Validators must describe the RULE, never quote the INPUT -- see
    `finding_hash` in models.py, whose message names the expected format and
    not the value it rejected. This matters most for free text the user
    typed, such as `AccessRequestCreate.reason`.
    """
    scrubbed = [
        {k: v for k, v in error.items() if k not in ("input", "ctx")}
        for error in exc.errors()
    ]
    return JSONResponse(status_code=422, content={"detail": scrubbed})


@app.get("/healthz")
async def healthz() -> dict[str, bool]:
    return {"ok": True}


from app.routes import admin as _admin  # noqa: E402  (import after `app` exists)
from app.routes import appeals as _appeals  # noqa: E402
from app.routes import dept as _dept  # noqa: E402
from app.routes import enroll as _enroll  # noqa: E402
from app.routes import events as _events  # noqa: E402
from app.routes import policy as _policy  # noqa: E402
from app.routes import requests as _requests  # noqa: E402
from app.routes import signup as _signup  # noqa: E402

app.include_router(_admin.router)
app.include_router(_appeals.router)
app.include_router(_dept.router)
app.include_router(_enroll.router)
app.include_router(_events.router)
app.include_router(_policy.router)
app.include_router(_requests.router)
app.include_router(_signup.router)

from pathlib import Path  # noqa: E402

from fastapi.staticfiles import StaticFiles  # noqa: E402

_STATIC = Path(__file__).parent / "static"
if _STATIC.exists():
    # Registered LAST so /v1/* and /healthz resolve first.
    app.mount("/", StaticFiles(directory=str(_STATIC), html=True), name="console")
else:
    # app/static/ is git-ignored -- it only exists after `npm run build` in
    # admin/. This is evaluated ONCE at import time, so starting uvicorn
    # before the build leaves / 404ing until the server is RESTARTED, not
    # just until the build finishes. On stage that reads as a broken
    # product, so this has to be loud enough that an operator notices it in
    # a scrolling log, not a debug-level line nobody greps for.
    log.warning(
        "console not built: %s does not exist -- / will 404. "
        "Run `npm run build` in admin/, then RESTART this server "
        "(the mount is decided once, at import time).",
        _STATIC,
    )
