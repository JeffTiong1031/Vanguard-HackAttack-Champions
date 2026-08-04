import io
import zipfile

from app.models import RedactSpan
from app.parsers.excel import parse_excel
from app.redact.excel import redact_excel

NS = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'


def _excel(parts: dict[str, str]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for name, body in parts.items():
            z.writestr(name, body)
    return buf.getvalue()


def test_excel_redacts_sensitive_span_in_shared_strings():
    data = _excel({
        "xl/workbook.xml": f"<workbook {NS}><sheets><sheet name='Sheet1' sheetId='1'/></sheets></workbook>",
        "xl/sharedStrings.xml": f"<sst {NS}><si><t>Ahmad 880101-14-5566</t></si></sst>",
    })
    extract, _, _, nodes = parse_excel(data)
    start = extract.index("880101-14-5566")
    end = start + len("880101-14-5566")
    span = RedactSpan(start=start, end=end, text="880101-14-5566", placeholder="NRIC_1")

    redacted_bytes = redact_excel(data, [span], nodes)

    # Verify redacted bytes form a valid ZIP and contain the redacted text
    with zipfile.ZipFile(io.BytesIO(redacted_bytes)) as z:
        shared_strings = z.read("xl/sharedStrings.xml").decode("utf-8")
        assert "NRIC_1" in shared_strings
        assert "880101-14-5566" not in shared_strings
