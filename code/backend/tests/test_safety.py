import pytest
from pathlib import Path
from app.models import ErrorCode
from app.safety import SafetyError, guard_zip, run_with_timeout, sniff_format

FIX = Path(__file__).parent / "fixtures"


def test_sniff_prefers_magic_bytes_over_the_filename():
    # A PDF renamed to .docx must be treated as a PDF, not trusted by extension.
    assert sniff_format("payroll.docx", b"%PDF-1.7\n...") == "pdf"


def test_sniff_accepts_image_types():
    assert sniff_format("photo.jpg", b"\xff\xd8\xff\xe0blah") == "image"
    assert sniff_format("graphic.png", b"\x89PNG\r\n\x1a\n...") == "image"


def test_sniff_rejects_an_unsupported_type():
    with pytest.raises(SafetyError) as e:
        sniff_format("program.exe", b"MZ\x90\x00...")
    assert e.value.code == ErrorCode.UNSUPPORTED_TYPE


def test_guard_zip_rejects_a_compression_bomb():
    with pytest.raises(SafetyError) as e:
        guard_zip((FIX / "zip_bomb.docx").read_bytes())
    assert e.value.code == ErrorCode.SUSPICIOUS_ARCHIVE


def test_guard_zip_rejects_too_many_entries():
    with pytest.raises(SafetyError) as e:
        guard_zip((FIX / "many_entries.docx").read_bytes())
    assert e.value.code == ErrorCode.SUSPICIOUS_ARCHIVE


def test_guard_zip_accepts_an_ordinary_archive():
    import io, zipfile
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("word/document.xml", "<w:t>hello</w:t>")
    guard_zip(buf.getvalue())  # must not raise


def test_run_with_timeout_kills_a_hanging_parser():
    with pytest.raises(SafetyError) as e:
        run_with_timeout(_spin, b"", seconds=0.5)
    assert e.value.code == ErrorCode.TIMEOUT


def _spin(_data: bytes):
    while True:
        pass
