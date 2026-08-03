from enum import Enum
from typing import Literal, Optional
from pydantic import BaseModel, Field, field_validator


class ErrorCode(str, Enum):
    TOO_LARGE = "too_large"
    UNSUPPORTED_TYPE = "unsupported_type"
    PASSWORD_PROTECTED = "password_protected"
    NO_TEXT_LAYER = "no_text_layer"
    PARSE_FAILED = "parse_failed"
    TIMEOUT = "timeout"
    SUSPICIOUS_ARCHIVE = "suspicious_archive"
    # /v1/redact only:
    EXTRACT_MISMATCH = "extract_mismatch"     # re-parse disagreed with the reviewed extract
    REDACTION_FAILED = "redaction_failed"     # a span could not be located or removed


class Coverage(BaseModel):
    """What we read and — load-bearing — what we did not.

    Pushback 3: a CLEAN verdict on the extract is not a CLEAN verdict on the
    file. `not_read` is rendered in the review pane so the boundary of the
    check is visible to the user rather than implied.
    """
    read: list[str] = Field(default_factory=list)
    not_read: list[str] = Field(default_factory=list)
    pages_total: Optional[int] = None
    pages_with_text: Optional[int] = None


class ExtractResponse(BaseModel):
    extract: str
    #: SHA-256 of `extract`. The redact call sends it back; the backend
    #: re-parses and refuses if the hash differs. Offsets reviewed against one
    #: parse must never be applied against another -- see RedactRequest.
    extract_sha256: str
    chars: int
    truncated: bool
    format: Literal["txt", "csv", "docx", "pdf", "xlsx"]
    coverage: Coverage
    warnings: list[str] = Field(default_factory=list)


class RedactSpan(BaseModel):
    """One accepted mask, in EXTRACT coordinates.

    `text` is carried alongside the offsets deliberately: DOCX redaction maps
    by offset (exact), PDF redaction locates by string search (U30). Sending
    both means one contract serves both mechanisms.
    """
    start: int = Field(ge=0)
    end: int = Field(ge=0)
    text: str
    placeholder: str

    @field_validator("end")
    @classmethod
    def _ordered(cls, end: int, info) -> int:
        start = info.data.get("start")
        if start is not None and end <= start:
            raise ValueError("end must be greater than start")
        return end


class RedactRequest(BaseModel):
    """Sent as the `spec` field of the multipart body, beside `file`.

    🔴 The ORIGINAL bytes are re-uploaded because the backend kept nothing
    (F4). That is the cost of zero retention and it is the right trade: a
    server-side cache of "the file we are about to redact" is precisely doc 02
    section 4.3's "silently degrades zero retention to short retention".
    """
    extract_sha256: str
    spans: list[RedactSpan]


class ErrorBody(BaseModel):
    code: ErrorCode
    message: str          # user-facing, already phrased for a non-engineer


class ErrorResponse(BaseModel):
    error: ErrorBody

    @classmethod
    def of(cls, code: ErrorCode, message: str) -> "ErrorResponse":
        return cls(error=ErrorBody(code=code, message=message))
