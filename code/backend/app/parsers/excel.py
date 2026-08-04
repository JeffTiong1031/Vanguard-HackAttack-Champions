"""Excel (.xlsx/.xlsm) text extraction over OOXML parts directly.

Reads sharedStrings.xml, worksheets/sheet*.xml, and comments*.xml using
stdlib zipfile + xml.etree.ElementTree without heavy third-party dependencies.
"""
import io
import re
import zipfile
from xml.etree import ElementTree

from app.models import Coverage, ErrorCode
from app.parsers.text import ExtractResult, NodeRef
from app.safety import SafetyError

MAIN_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"

PART_GROUPS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"^xl/sharedStrings\.xml$"), "shared_strings"),
    (re.compile(r"^xl/worksheets/sheet\d*\.xml$"), "worksheets"),
    (re.compile(r"^xl/comments\d*\.xml$"), "comments"),
    (re.compile(r"^xl/threadedComments/threadedComment\d*\.xml$"), "comments"),
]


def _text_of_part(part_name: str, part: bytes, base: int) -> tuple[str, list[NodeRef]]:
    try:
        root = ElementTree.fromstring(part)
    except ElementTree.ParseError:
        return "", []

    pieces: list[str] = []
    refs: list[NodeRef] = []
    cursor = base
    node_index = 0

    for node in root.iter():
        if node.tag in (f"{MAIN_NS}t", f"{MAIN_NS}v"):
            body = node.text or ""
            if body:
                refs.append(NodeRef(part_name, node_index, cursor, len(body)))
                pieces.append(body)
                cursor += len(body)
            node_index += 1
        elif node.tag in (f"{MAIN_NS}si", f"{MAIN_NS}row", f"{MAIN_NS}comment"):
            if pieces and not pieces[-1].endswith("\n"):
                pieces.append("\n")
                cursor += 1

    return "".join(pieces), refs


def parse_excel(data: bytes) -> ExtractResult:
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise SafetyError(
            ErrorCode.PARSE_FAILED,
            "This Excel file looks damaged and could not be opened. It has not "
            "been sent to the AI.",
        ) from exc

    names = archive.namelist()

    # Password-protected or non-OOXML Excel
    if "xl/workbook.xml" not in names:
        raise SafetyError(
            ErrorCode.PASSWORD_PROTECTED,
            "This Excel file appears to be password-protected or unsupported, "
            "so it could not be checked. It has not been sent to the AI.",
        )

    chunks: list[str] = []
    refs: list[NodeRef] = []
    read: list[str] = []
    cursor = 0

    for pattern, label in PART_GROUPS:
        matched = sorted(n for n in names if pattern.match(n))
        if not matched:
            continue
        if label not in read:
            read.append(label)
        for name in matched:
            body, part_refs = _text_of_part(name, archive.read(name), cursor)
            if not body.strip():
                continue
            chunks.append(body)
            refs.extend(part_refs)
            cursor += len(body) + 1    # +1 for the "\n" join

    extracted_text = "\n".join(chunks)

    if not extracted_text.strip():
        raise SafetyError(
            ErrorCode.NO_TEXT_LAYER,
            "This Excel file contains no readable text, so it was not checked "
            "and has not been sent to the AI.",
        )

    images = [n for n in names if n.startswith("xl/media/")]
    not_read = [f"{len(images)} embedded images (no OCR)"] if images else []

    return extracted_text, Coverage(read=read, not_read=not_read), [], refs
