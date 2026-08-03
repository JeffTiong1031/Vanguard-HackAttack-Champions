import hashlib
import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response
from pydantic import ValidationError

from app import limits
from app.auth import check_bearer
from app.models import Coverage, ErrorCode, ErrorResponse, ExtractResponse, RedactRequest, RedactSpan
from app.parsers.docx import parse_docx
from app.parsers.excel import parse_excel
from app.parsers.pdf import parse_pdf
from app.parsers.text import parse_text, truncate
from app.redact.docx import redact_docx
from app.redact.excel import redact_excel
from app.redact.pdf import redact_pdf
from app.safety import SafetyError, guard_zip, run_with_timeout, sniff_format

log = logging.getLogger("vanguard")
router = APIRouter()

_STATUS = {
    ErrorCode.TOO_LARGE: 413,
    ErrorCode.UNSUPPORTED_TYPE: 415,
    ErrorCode.PASSWORD_PROTECTED: 422,
    ErrorCode.NO_TEXT_LAYER: 422,
    ErrorCode.PARSE_FAILED: 422,
    ErrorCode.SUSPICIOUS_ARCHIVE: 422,
    ErrorCode.TIMEOUT: 504,
    ErrorCode.EXTRACT_MISMATCH: 409,
    ErrorCode.REDACTION_FAILED: 422,
}


def _fail(err: SafetyError) -> JSONResponse:
    # Log the CODE and the SIZE. Never the name, never the bytes, never the
    # extract. I3: classes and counts, never values.
    log.info("extract rejected code=%s", err.code.value)
    return JSONResponse(
        status_code=_STATUS[err.code],
        content=ErrorResponse.of(err.code, err.message).model_dump(mode="json"),
    )


@router.post("/v1/extract")
async def extract(request: Request) -> JSONResponse:
    """Parse a file to text. Return the text. Keep nothing.

    🔴 The body is read manually rather than via `UploadFile` on purpose.
    Starlette's UploadFile is a SpooledTemporaryFile with a 1 MB rollover, so
    every file over 1 MB would be written to DISK before our code ran -- F4
    broken by a framework default, which is doc 02 section 4.3's exact
    failure mode and CLAUDE.md's "defaults are where the trap lives".
    """
    denied = check_bearer(request)
    if denied is not None:
        return denied

    filename = request.headers.get("x-vanguard-filename", "upload")

    declared = request.headers.get("content-length")
    if declared and int(declared) > limits.MAX_UPLOAD_BYTES:
        return _fail(SafetyError(
            ErrorCode.TOO_LARGE,
            f"This file is {int(declared) / 1024 / 1024:.0f} MB. The limit is 10 MB, "
            "so it was not checked and has not been sent to the AI.",
        ))

    data = bytearray()
    async for chunk in request.stream():
        data.extend(chunk)
        if len(data) > limits.MAX_UPLOAD_BYTES + 4096:   # slack for multipart framing
            return _fail(SafetyError(
                ErrorCode.TOO_LARGE,
                "This file is larger than the 10 MB limit, so it was not checked "
                "and has not been sent to the AI.",
            ))

    body, parsed_name = _split_multipart(bytes(data))
    if parsed_name:
        filename = parsed_name

    try:
        kind = sniff_format(filename, body)
        if kind == "docx":
            guard_zip(body)
            text, coverage, warnings, _nodes = run_with_timeout(
                parse_docx, body, limits.PARSE_TIMEOUT_SECONDS
            )
        elif kind == "xlsx":
            guard_zip(body)
            text, coverage, warnings, _nodes = run_with_timeout(
                parse_excel, body, limits.PARSE_TIMEOUT_SECONDS
            )
        elif kind == "pdf":
            text, coverage, warnings, _nodes = run_with_timeout(
                parse_pdf, body, limits.PARSE_TIMEOUT_SECONDS
            )
        else:
            text, coverage, warnings, _nodes = parse_text(filename, body)
    except SafetyError as err:
        return _fail(err)
    finally:
        # Explicit, and load-bearing as documentation even though CPython
        # would collect these anyway: nothing here is handed onward.
        data.clear()

    text, was_truncated = truncate(text)
    if was_truncated:
        warnings.append(
            f"Only the first {limits.MAX_EXTRACT_CHARS:,} characters were checked."
        )

    log.info("extract ok format=%s chars=%d truncated=%s", kind, len(text), was_truncated)
    return JSONResponse(
        status_code=200,
        content=ExtractResponse(
            extract=text,
            # Bound to the exact text the user is about to review. /v1/redact
            # recomputes it and refuses on mismatch (Task 5B).
            extract_sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
            chars=len(text),
            truncated=was_truncated,
            format=kind,
            coverage=coverage if isinstance(coverage, Coverage) else Coverage(**coverage),
            warnings=warnings,
        ).model_dump(mode="json"),
    )


def _split_multipart(raw: bytes) -> tuple[bytes, str | None]:
    """Split a simple single-file multipart/form-data payload without disk spooling.

     Starlette's `python-multipart` parser writes large parts to temporary files on disk.
     To enforce zero-retention (F4), we parse the boundary in-memory.
    """
    if not raw.startswith(b"--"):
        return raw, None

    first_line_end = raw.find(b"\r\n")
    if first_line_end < 0:
        return raw, None

    boundary = raw[:first_line_end]
    parts = raw.split(boundary)

    for part in parts:
        head, _, tail = part.partition(b"\r\n\r\n")
        if b'name="file"' in head:
            payload = tail.rstrip(b"\r\n-")
            marker = b'filename="'
            if marker in head:
                start = head.index(marker) + len(marker)
                filename = head[start : head.index(b'"', start)].decode("utf-8", "replace")
                return payload, filename
            return payload, None

    return raw, None


async def _read_multipart_with_spec(raw_request: Request) -> tuple[bytes, str, str]:
    """Read a multipart request containing `file` and `spec` fields directly into memory."""
    declared = raw_request.headers.get("content-length")
    if declared and int(declared) > limits.MAX_UPLOAD_BYTES:
        raise SafetyError(
            ErrorCode.TOO_LARGE,
            f"This file is {int(declared) / 1024 / 1024:.0f} MB. The limit is 10 MB, "
            "so it was not checked and has not been sent to the AI.",
        )

    data = bytearray()
    async for chunk in raw_request.stream():
        data.extend(chunk)
        if len(data) > limits.MAX_UPLOAD_BYTES + 4096:
            raise SafetyError(
                ErrorCode.TOO_LARGE,
                "This file is larger than the 10 MB limit, so it was not checked "
                "and has not been sent to the AI.",
            )

    raw = bytes(data)
    filename = raw_request.headers.get("x-vanguard-filename", "upload")

    if not raw.startswith(b"--"):
        return raw, filename, "{}"

    first_line_end = raw.find(b"\r\n")
    if first_line_end < 0:
        return raw, filename, "{}"

    boundary = raw[:first_line_end]
    parts = raw.split(boundary)
    file_body = raw
    file_name: str | None = None
    spec_raw = "{}"

    for part in parts:
        head, _, tail = part.partition(b"\r\n\r\n")
        payload = tail.rstrip(b"\r\n-")
        if b'name="file"' in head:
            file_body = payload
            marker = b'filename="'
            if marker in head:
                start = head.index(marker) + len(marker)
                file_name = head[start : head.index(b'"', start)].decode("utf-8", "replace")
        elif b'name="spec"' in head:
            spec_raw = payload.decode("utf-8", errors="replace")

    return file_body, file_name or filename, spec_raw


@router.post("/v1/redact")
async def redact(request: Request) -> Response:
    """Apply accepted masks to the original file, in its original format."""
    denied = check_bearer(request)
    if denied is not None:
        return denied

    try:
        body, filename, spec_raw = await _read_multipart_with_spec(request)
    except SafetyError as err:
        return _fail(err)

    try:
        spec = RedactRequest.model_validate_json(spec_raw)
    except ValidationError:
        return _fail(SafetyError(ErrorCode.PARSE_FAILED, "The redaction request was malformed."))

    try:
        kind = sniff_format(filename, body)
        if kind == "docx":
            guard_zip(body)
            text, _, _, nodes = run_with_timeout(parse_docx, body, limits.PARSE_TIMEOUT_SECONDS)
        elif kind == "xlsx":
            guard_zip(body)
            text, _, _, nodes = run_with_timeout(parse_excel, body, limits.PARSE_TIMEOUT_SECONDS)
        elif kind == "pdf":
            text, _, _, nodes = run_with_timeout(parse_pdf, body, limits.PARSE_TIMEOUT_SECONDS)
        else:
            text, _, _, nodes = parse_text(filename, body)
        text, _ = truncate(text)

        if hashlib.sha256(text.encode("utf-8")).hexdigest() != spec.extract_sha256:
            raise SafetyError(
                ErrorCode.EXTRACT_MISMATCH,
                "This file changed between checking and sending, so it was not "
                "redacted and has not been sent to the AI. Please attach it again.",
            )

        for span in spec.spans:
            if text[span.start : span.end] != span.text:
                raise SafetyError(
                    ErrorCode.REDACTION_FAILED,
                    f'Vanguard could not apply the mask for "{span.text}" to this document, '
                    "so nothing was changed and the file has not been sent to the AI.",
                )

        stem, _, suffix = filename.rpartition(".")
        if kind == "docx":
            payload = redact_docx(body, spec.spans, nodes)
            media = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        elif kind == "xlsx":
            payload = redact_excel(body, spec.spans, nodes)
            media = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        elif kind == "pdf":
            payload = redact_pdf(body, spec.spans)
            media = "application/pdf"
        else:
            payload = _apply_to_text(text, spec.spans).encode("utf-8")
            media = "text/csv" if kind == "csv" else "text/plain"
        out_name = f"{stem or filename}.redacted.{suffix or 'txt'}"
    except SafetyError as err:
        return _fail(err)

    log.info("redact ok format=%s spans=%d", kind, len(spec.spans))
    return Response(
        content=payload,
        media_type=media,
        headers={"x-vanguard-redacted-name": out_name},
    )


def _apply_to_text(text: str, spans: list[RedactSpan]) -> str:
    for span in sorted(spans, key=lambda s: s.start, reverse=True):
        text = text[: span.start] + span.placeholder + text[span.end :]
    return text
