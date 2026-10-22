import json

from alloy.agent.loop import SEED_CLAIMS
from alloy.experiments.report import to_markdown
from alloy.knowledge import citations
from alloy.knowledge.extract import load_seed


def test_bond_id_accepts_real_ids_and_skips_synthetic():
    assert citations.bond_id("arxiv:2009.08810") == "2009.08810"
    assert citations.bond_id("1509.03580v1") == "1509.03580"
    assert citations.bond_id("doi:10.1073/pnas.1517384113") == "10.1073/pnas.1517384113"
    assert citations.bond_id("40762136") == "40762136"
    assert citations.bond_id("synthetic-A") is None


def test_bibtex_reads_cache_without_calling_bond(tmp_path):
    cache = tmp_path / "bibtex.json"
    cache.write_text(json.dumps({"1509.03580": "@misc{brunton2015, title={SINDy}}"}), encoding="utf-8")
    found = citations.bibtex(["arxiv:1509.03580", "synthetic-A"], fetch=False, cache_path=cache)
    assert found == {"arxiv:1509.03580": "@misc{brunton2015, title={SINDy}}"}


def test_report_lists_references_only_when_given():
    from alloy.agent.loop import Investigation
    from alloy.contracts import Goal

    inv = Investigation(id="x", goal=Goal(question="q"), claims=load_seed(SEED_CLAIMS))
    assert "## References" not in to_markdown(inv)
    text = to_markdown(inv, bibtex={"a": "@misc{brunton2015, title={SINDy}}"})
    assert "## References" in text and "@misc{brunton2015" in text
