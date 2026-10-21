import pytest

from alloy.knowledge.conditions import check


def test_identical_stated_settings_enable_only_a_hidden_setting_hypothesis(seed_claims):
    a, b = seed_claims
    b.conditions = dict(a.conditions)
    report = check(a, b, ("noise", "threshold"))
    assert report.comparable
    assert report.assessment == "unstated_settings_hypothesis"
    assert any("assumptions" in n for n in report.notes)


@pytest.mark.parametrize("value", [None, "", float("nan"), float("inf")])
def test_unknown_settings_never_become_simulation_defaults(seed_claims, value):
    a, b = seed_claims
    b.conditions["noise"] = value
    report = check(a, b, ("noise",))
    assert not report.comparable
    assert report.assessment == "insufficient_evidence"
    assert "noise" in report.missing


def test_unsupported_condition_difference_is_explained(seed_claims):
    a, b = seed_claims
    a.conditions["laboratory"] = "one"
    b.conditions["laboratory"] = "two"
    report = check(a, b, ("noise",))
    assert not report.comparable
    assert any("cannot vary: laboratory" in n for n in report.notes)


def test_nonfinite_reported_values_are_rejected(seed_claims):
    a, b = seed_claims
    a.value = float("nan")
    a.unit = b.unit = "dimensionless"
    assert not check(a, b).comparable
