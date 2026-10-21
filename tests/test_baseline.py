import json

from alloy import bench
from alloy.agent.baseline import _claims_text
from alloy.contracts import Claim


def test_score_checks_cause_and_answer_against_oracle():
    scenario = bench.load_scenarios(["short_record"])[0]
    truth = bench.Oracle(hard_conditions={}, means={"a": 0.1, "b": 0.5}, acceptable=["a"])
    good = bench.score("x", scenario, truth, cause="t_end", answer="a", runs=10)
    bad = bench.score("x", scenario, truth, cause="noise", answer="b", runs=10)
    assert good.cause_correct and good.answer_correct and good.answer_oracle_error == 0.1
    assert not bad.cause_correct and not bad.answer_correct


def test_plain_agent_gets_all_claim_evidence_including_zero_and_units():
    claim = Claim(
        id="units-trap", paper="10.example/paper", title="Measured result", method="sindy",
        quantity="coef_error", value=0.0, unit="percent", outcome="perfect recovery",
        conditions={"system": "lorenz", "noise": 0.0}, quote="Zero percent error.", source="manual",
    )
    text = _claims_text([claim])
    assert json.loads(text.removeprefix("- ")) == claim.model_dump()
    assert '"value": 0.0' in text and '"outcome": "perfect recovery"' in text


def test_plain_agent_can_distinguish_relative_error_from_percent():
    claims = [
        Claim(id="relative", paper="a", method="sindy", quantity="coef_error", value=0.02, unit="relative"),
        Claim(id="percent", paper="b", method="sindy", quantity="coef_error", value=2.0, unit="percent"),
    ]
    received = [json.loads(line.removeprefix("- ")) for line in _claims_text(claims).splitlines()]
    assert [(c["id"], c["value"], c["unit"]) for c in received] == [
        ("relative", 0.02, "relative"), ("percent", 2.0, "percent"),
    ]


def test_claim_quote_newlines_do_not_break_claim_boundaries():
    claims = [Claim(id="a", paper="p", method="sindy", quantity="coef_error", quote="A line.\nAnother line.")]
    text = _claims_text(claims)
    assert len(text.splitlines()) == 1
    assert json.loads(text.removeprefix("- "))["quote"] == claims[0].quote
