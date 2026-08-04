import io
import zipfile
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
FIX = Path(__file__).parent / "fixtures"
NS = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'


def _post(name: str, data: bytes, content_type: str = "application/octet-stream"):
    return client.post("/v1/extract", files={"file": (name, data, content_type)})


def test_txt_round_trip():
    r = _post("notes.txt", b"Ahmad 880101-14-5566")
    assert r.status_code == 200
    body = r.json()
    assert body["format"] == "txt"
    assert "880101-14-5566" in body["extract"]
    assert body["truncated"] is False


def test_oversized_upload_is_rejected_with_a_human_message():
    r = _post("big.txt", b"x" * (11 * 1024 * 1024))
    assert r.status_code == 413
    assert r.json()["error"]["code"] == "too_large"
    assert "10 MB" in r.json()["error"]["message"]


def test_unsupported_type_is_415_and_names_what_is_supported():
    r = _post("binary.exe", b"MZ\x90\x00\x03\x00\x00\x00")
    assert r.status_code == 415
    assert r.json()["error"]["code"] == "unsupported_type"


def test_zip_bomb_is_refused_before_decompression():
    r = _post("bomb.docx", (FIX / "zip_bomb.docx").read_bytes())
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "suspicious_archive"


def test_scanned_pdf_is_an_error_not_a_clean_extract():
    r = _post("scan.pdf", (FIX / "scanned_no_text.pdf").read_bytes())
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "no_text_layer"


def test_truncation_is_reported_rather_than_silent():
    r = _post("big.txt", b"a" * 150_000)
    assert r.status_code == 200
    assert r.json()["truncated"] is True
    assert r.json()["chars"] == 100_000


def test_docx_comment_text_reaches_the_extract():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("word/document.xml", f"<w:document {NS}><w:body><w:p><w:t>clean</w:t></w:p></w:body></w:document>")
        z.writestr("word/comments.xml", f"<w:comments {NS}><w:comment><w:p><w:t>880101-14-5566</w:t></w:p></w:comment></w:comments>")
    r = _post("memo.docx", buf.getvalue())
    assert r.status_code == 200
    assert "880101-14-5566" in r.json()["extract"]


def test_healthz():
    assert client.get("/healthz").json() == {"ok": True}
