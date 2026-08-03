from pathlib import Path
import importlib


def test_seed_populates_named_analytics(tmp_path):
    import scripts.seed as seedmod
    importlib.reload(seedmod)
    summary = seedmod.build_demo_world(out_path=tmp_path / "DEMO-TOKENS.md")
    from app.deps import get_conn
    from app.analytics import analytics_summary
    s = analytics_summary(get_conn(), summary["org_id"], 30, None)
    assert s["totals"]["events"] > 0
    assert any(e["name"] != "Unnamed" for e in s["top_employees"])
    assert len(s["usage_trend"]) > 0
