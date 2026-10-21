from alloy import bench


def test_score_checks_cause_and_answer_against_oracle():
    scenario = bench.load_scenarios(["short_record"])[0]
    truth = bench.Oracle(hard_conditions={}, means={"a": 0.1, "b": 0.5}, acceptable=["a"])
    good = bench.score("x", scenario, truth, cause="t_end", answer="a", runs=10)
    bad = bench.score("x", scenario, truth, cause="noise", answer="b", runs=10)
    assert good.cause_correct and good.answer_correct and good.answer_oracle_error == 0.1
    assert not bad.cause_correct and not bad.answer_correct
