import io
import zipfile
from pathlib import Path

import pytest

from app.models import ErrorCode
from app.parsers.excel import parse_excel
from app.safety import SafetyError

NS = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'


def _excel(parts: dict[str, str | bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for name, body in parts.items():
            if isinstance(body, str):
                z.writestr(name, body.encode("utf-8"))
            else:
                z.writestr(name, body)
    return buf.getvalue()


def test_excel_reads_shared_strings_and_worksheets():
    data = _excel({
        "xl/workbook.xml": f"<workbook {NS}><sheets><sheet name='Sheet1' sheetId='1'/></sheets></workbook>",
        "xl/sharedStrings.xml": f"<sst {NS}><si><t>Ahmad 880101-14-5566</t></si></sst>",
        "xl/worksheets/sheet1.xml": f"<worksheet {NS}><sheetData><row><c t='s'><v>0</v></c></row></sheetData></worksheet>",
    })
    extract, coverage, _, nodes = parse_excel(data)
    assert "880101-14-5566" in extract
    assert "shared_strings" in coverage.read
    assert len(nodes) > 0


def test_excel_reads_comments():
    data = _excel({
        "xl/workbook.xml": f"<workbook {NS}><sheets><sheet name='Sheet1' sheetId='1'/></sheets></workbook>",
        "xl/sharedStrings.xml": f"<sst {NS}><si><t>Clean Cell</t></si></sst>",
        "xl/comments1.xml": f"<comments {NS}><commentList><comment><text><t>IC is 880101-14-5566</t></text></comment></commentList></comments>",
    })
    extract, coverage, _, _ = parse_excel(data)
    assert "880101-14-5566" in extract
    assert "comments" in coverage.read


def test_excel_raises_on_password_protected_or_missing_workbook():
    data = _excel({"some_part.xml": "<xml/>"})
    with pytest.raises(SafetyError) as exc_info:
        parse_excel(data)
    assert exc_info.value.code == ErrorCode.PASSWORD_PROTECTED


def test_excel_reports_images_as_not_read():
    data = _excel({
        "xl/workbook.xml": f"<workbook {NS}/>",
        "xl/sharedStrings.xml": f"<sst {NS}><si><t>text</t></si></sst>",
        "xl/media/image1.png": b"\x89PNG",
    })
    _, coverage, _, _ = parse_excel(data)
    assert any("embedded images" in s for s in coverage.not_read)
