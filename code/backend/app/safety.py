import io
import zipfile
from concurrent.futures import ProcessPoolExecutor, TimeoutError as FuturesTimeout
from typing import Any, Callable

from app import limits
from app.models import ErrorCode


class SafetyError(Exception):
    def __init__(self, code: ErrorCode, message: str):
        super().__init__(message)
        self.code = code
        self.message = message

    def __reduce__(self):
        return (SafetyError, (self.code, self.message))


_MAGIC: list[tuple[bytes, str]] = [
    (b"%PDF-", "pdf"),
    (b"PK\x03\x04", "zip"),   # OOXML container; refined below
    (b"\x89PNG\r\n\x1a\n", "image"),
    (b"\xff\xd8\xff", "image"),
    (b"BM", "image"),
    (b"II*\x00", "image"),
    (b"MM\x00*", "image"),
]


def sniff_format(filename: str, data: bytes) -> str:
    """Magic bytes first, filename second.

    A renamed file is the cheapest attack there is, and trusting the
    extension is how a PDF parser gets handed a ZIP.
    """
    head = data[:12]
    if head.startswith(b"RIFF") and b"WEBP" in head:
        return "image"

    for magic, kind in _MAGIC:
        if head.startswith(magic):
            if kind != "zip":
                return kind
            # OOXML: only DOCX is supported in v1. Distinguish by part name.
            try:
                with zipfile.ZipFile(io.BytesIO(data)) as z:
                    names = set(z.namelist())
            except zipfile.BadZipFile as exc:
                raise SafetyError(
                    ErrorCode.PARSE_FAILED,
                    "This file looks damaged and could not be opened.",
                ) from exc
            if "word/document.xml" in names:
                return "docx"
            if any(n.startswith("xl/") for n in names):
                return "xlsx"
            if any(n.startswith("ppt/") for n in names):
                raise SafetyError(
                    ErrorCode.UNSUPPORTED_TYPE,
                    "PowerPoint files aren't checked yet. Please export the "
                    "slides as PDF and attach that instead.",
                )
            raise SafetyError(
                ErrorCode.UNSUPPORTED_TYPE,
                "This archive type isn't supported.",
            )

    lowered = filename.lower()
    if lowered.endswith(".csv"):
        return "csv"
    if lowered.endswith((".txt", ".md", ".log")):
        return "txt"
    if lowered.endswith((".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff")):
        return "image"
    raise SafetyError(
        ErrorCode.UNSUPPORTED_TYPE,
        "Vanguard can check .txt, .csv, .docx, .xlsx, images (.png, .jpg, .webp) and .pdf files. "
        "This one isn't one of those, so it was not sent to the AI.",
    )


def guard_zip(data: bytes) -> None:
    """Reject compression bombs BEFORE any entry is decompressed."""
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            infos = z.infolist()
    except zipfile.BadZipFile as exc:
        raise SafetyError(
            ErrorCode.PARSE_FAILED, "This file looks damaged and could not be opened."
        ) from exc

    if len(infos) > limits.MAX_ZIP_ENTRIES:
        raise SafetyError(
            ErrorCode.SUSPICIOUS_ARCHIVE,
            "This document contains an unusual number of internal parts and "
            "was not opened. It has not been sent to the AI.",
        )

    total_uncompressed = sum(i.file_size for i in infos)
    total_compressed = max(1, sum(i.compress_size for i in infos))
    if total_uncompressed > limits.MAX_ZIP_UNCOMPRESSED_BYTES:
        raise SafetyError(
            ErrorCode.SUSPICIOUS_ARCHIVE,
            "This document expands to an unexpectedly large size and was not "
            "opened. It has not been sent to the AI.",
        )
    if total_uncompressed / total_compressed > limits.MAX_ZIP_RATIO:
        raise SafetyError(
            ErrorCode.SUSPICIOUS_ARCHIVE,
            "This document expands to an unexpectedly large size and was not "
            "opened. It has not been sent to the AI.",
        )


def run_with_timeout(fn: Callable[[bytes], Any], data: bytes, seconds: float) -> Any:
    """Run a parser in a separate PROCESS so a pathological input can be killed.

    A thread cannot be killed in CPython, so a thread-plus-timeout would leave
    a spinning parser holding a worker forever -- a self-inflicted DoS while
    reporting a clean timeout. The process pool is the honest mechanism.
    """
    with ProcessPoolExecutor(max_workers=1) as pool:
        future = pool.submit(fn, data)
        try:
            return future.result(timeout=seconds)
        except FuturesTimeout as exc:
            for proc in pool._processes.values():
                proc.kill()
            raise SafetyError(
                ErrorCode.TIMEOUT,
                "This file took too long to read, so it was not checked and "
                "has not been sent to the AI.",
            ) from exc
