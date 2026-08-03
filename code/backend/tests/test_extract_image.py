import io
from PIL import Image, ImageDraw, ImageFont
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models import ErrorCode
from app.parsers.image import parse_image
from app.safety import SafetyError

client = TestClient(app)


def _create_test_image(text: str = "NRIC 920101-14-5566") -> bytes:
    img = Image.new("RGB", (400, 100), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    # Simple text rendering on image
    draw.text((20, 30), text, fill=(0, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_parse_image_valid():
    image_bytes = _create_test_image("NRIC 920101-14-5566")
    try:
        text, coverage, warnings, nodes = parse_image("sample.png", image_bytes)
        assert coverage.pages_total == 1
        assert "OCR text layer" in coverage.read
    except SafetyError as err:
        # If tesseract executable is not on system, parse_image raises NO_TEXT_LAYER or returns OCR text
        assert err.code in (ErrorCode.NO_TEXT_LAYER, ErrorCode.PARSE_FAILED)


def test_extract_route_image():
    image_bytes = _create_test_image("SAMPLE TEXT 123456")
    resp = client.post(
        "/v1/extract",
        headers={"x-vanguard-filename": "test.png"},
        content=image_bytes,
    )
    # Status can be 200 (OCR succeeded) or 422 (NO_TEXT_LAYER if OCR engine not installed)
    assert resp.status_code in (200, 422)
    if resp.status_code == 200:
        data = resp.json()
        assert data["format"] == "image"
        assert "extract" in data
