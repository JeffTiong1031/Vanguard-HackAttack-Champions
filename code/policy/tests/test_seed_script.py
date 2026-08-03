from pathlib import Path
import importlib


def test_build_demo_world_writes_a_tokens_file(tmp_path, monkeypatch):
    import scripts.seed as seedmod
    importlib.reload(seedmod)
    out = tmp_path / "DEMO-TOKENS.md"
    summary = seedmod.build_demo_world(out_path=out)
    assert out.exists()
    text = out.read_text(encoding="utf-8")
    assert "Company Admin secret" in text
    assert summary["company_secret"] in text
    # every department and its secret is recorded
    for dept in summary["departments"]:
        assert dept["name"] in text and dept["secret"] in text
