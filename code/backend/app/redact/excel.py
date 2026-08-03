"""Apply accepted masks to the ORIGINAL Excel (.xlsx/.xlsm) file.

The extract's NodeRef map indicates which XML node each extract character came
from, so a span becomes a set of (node, local range) edits. Everything not
edited -- formulas, styles, charts, and media -- is copied through untouched.
"""
import io
import zipfile
from xml.etree import ElementTree

from app.models import ErrorCode, RedactSpan
from app.parsers.text import NodeRef
from app.safety import SafetyError

MAIN_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
ElementTree.register_namespace(
    "", "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
)
ElementTree.register_namespace(
    "r", "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
)


def redact_excel(data: bytes, spans: list[RedactSpan], nodes: list[NodeRef]) -> bytes:
    # part -> node_index -> list of (local_start, local_end, replacement)
    edits: dict[str, dict[int, list[tuple[int, int, str]]]] = {}

    for span in spans:
        touched = [
            n for n in nodes
            if n.extract_start < span.end and n.extract_start + n.length > span.start
        ]
        if not touched:
            raise SafetyError(
                ErrorCode.REDACTION_FAILED,
                f'Vanguard could not apply the mask for "{span.text}" to this document, '
                "so nothing was changed and the file has not been sent to the AI.",
            )

        for position, node in enumerate(touched):
            local_start = max(0, span.start - node.extract_start)
            local_end = min(node.length, span.end - node.extract_start)
            replacement = span.placeholder if position == 0 else ""
            edits.setdefault(node.part, {}).setdefault(node.node_index, []).append(
                (local_start, local_end, replacement)
            )

    source = zipfile.ZipFile(io.BytesIO(data))
    out_buffer = io.BytesIO()

    with zipfile.ZipFile(out_buffer, "w", zipfile.ZIP_DEFLATED) as out:
        for item in source.infolist():
            payload = source.read(item.filename)
            if item.filename in edits:
                payload = _rewrite_excel_part(payload, edits[item.filename])
            out.writestr(item, payload)

    return out_buffer.getvalue()


def _rewrite_excel_part(part: bytes, by_node: dict[int, list[tuple[int, int, str]]]) -> bytes:
    root = ElementTree.fromstring(part)
    node_index = 0
    for node in root.iter():
        if node.tag not in (f"{MAIN_NS}t", f"{MAIN_NS}v"):
            continue
        ranges = by_node.get(node_index)
        if ranges and node.text:
            text = node.text
            for local_start, local_end, replacement in sorted(ranges, reverse=True):
                text = text[:local_start] + replacement + text[local_end:]
            node.text = text
            node.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
        node_index += 1
    return ElementTree.tostring(root, encoding="UTF-8", xml_declaration=True)
