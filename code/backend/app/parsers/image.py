import io
import logging

from PIL import Image
import pytesseract

from app.models import Coverage, ErrorCode
from app.parsers.text import ExtractResult
from app.safety import SafetyError

log = logging.getLogger("vanguard")


def parse_image(filename: str, data: bytes) -> ExtractResult:
    """Extract text from an image via OCR.

    Supports PNG, JPEG, WEBP, BMP, TIFF.
    Uses PIL for decoding and PyTesseract/PyMuPDF for OCR.
    Returns (text, coverage, warnings, nodes).
    """
    try:
        img = Image.open(io.BytesIO(data))
        img.verify()
        img = Image.open(io.BytesIO(data))
    except Exception as exc:
        raise SafetyError(
            ErrorCode.PARSE_FAILED,
            "This image looks damaged or corrupted and could not be opened.",
        ) from exc

    warnings: list[str] = []
    text = ""

    try:
        # Grayscale conversion enhances OCR accuracy
        ocr_img = img.convert("L")
        text = pytesseract.image_to_string(ocr_img).strip()
    except pytesseract.TesseractNotFoundError:
        log.warning("Tesseract binary not installed on system, trying fallback OCR")
        text = _try_pymupdf_ocr(data)
    except Exception as exc:
        log.warning("PyTesseract OCR failed: %s, trying fallback", exc)
        text = _try_pymupdf_ocr(data)

    if not text.strip():
        raise SafetyError(
            ErrorCode.NO_TEXT_LAYER,
            "No readable text was detected in this image. "
            "It has not been sent to the AI.",
        )

    coverage = Coverage(
        read=["OCR text layer"],
        not_read=["non-text visual elements"],
        pages_total=1,
        pages_with_text=1,
    )

    return text, coverage, warnings, []


def _try_pymupdf_ocr(data: bytes) -> str:
    """Fallback OCR using PyMuPDF if Tesseract binary is not directly available."""
    try:
        import fitz
        doc = fitz.open(stream=data, filetype="png")
        if len(doc) > 0:
            page = doc[0]
            text = page.get_text().strip()
            if text:
                return text
            try:
                tp = page.get_textpage_ocr()
                return tp.extractTEXT().strip()
            except Exception:
                pass
    except Exception:
        pass
    return ""
