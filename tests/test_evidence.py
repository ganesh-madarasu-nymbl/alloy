from dataclasses import asdict
from pathlib import Path
from unittest.mock import Mock

import pytest

from alloy.knowledge import conditions, extract
from alloy.knowledge.bond import Paper
from alloy.knowledge.presentation import evidence_label, paper_url

APP = str(Path(__file__).resolve().parents[1] / 'ui' / 'app.py')


@pytest.mark.parametrize('changes', [
    {'conditions': {'noise': 0.2}},
    {'conditions': {'system': 'lorenz', 'noise': None}},
    {'conditions': {'system': 'other', 'noise': 0.2}},
    {'conditions': {'system': 'lorenz', 'noise': 0.2, 'dt': 0.01}},
    {'unit': 'seconds'},
    {'method': 'other'},
    {'value': 0.2},
])
def test_incomplete_or_incompatible_claims_are_blocked(seed_claims, changes):
    a, b = seed_claims
    assert not conditions.check(a, b.model_copy(update=changes), ('noise',)).comparable


def test_multiple_differences_are_available_to_controlled_investigation(seed_claims):
    a, b = seed_claims
    a.conditions['dt'] = 0.01
    b.conditions['dt'] = 0.1
    report = conditions.check(a, b, ('noise', 'dt'))
    assert report.comparable
    assert set(report.differing) == {'noise', 'dt'}
    assert set(report.reproducible) == {'noise', 'dt'}
    assert any('interactions' in note for note in report.notes)


@pytest.mark.parametrize('quote,value,valid', [
    ('Error is 0.2.', '0.2', True),
    ('Error  is\n0.2.', '0.2', True),
    ('Invented sentence.', '0.2', False),
    ('', '0.2', False),
    ('Error is 0.2.', 'nan', False),
    ('Error is 0.2.', 'inf', False),
    ('Error is 0.2.', '999', False),
])
def test_extraction_requires_passage_and_finite_number(monkeypatch, quote, value, valid):
    paper = Paper(id='p', title='Paper', passages=['Error is 0.2.'])
    response = extract.ExtractedClaims(claims=[extract.ExtractedClaim(
        method='sindy', quantity='error', value=value, quote=quote,
    )])
    monkeypatch.setattr(extract.llm, 'parse', Mock(return_value=response))
    if valid:
        assert extract.extract_claims(paper, ())[0].value == 0.2
    else:
        with pytest.raises(ValueError):
            extract.extract_claims(paper, ())


def test_empty_passages_do_not_call_model(monkeypatch):
    parse = Mock()
    monkeypatch.setattr(extract.llm, 'parse', parse)
    with pytest.raises(ValueError):
        extract.extract_claims(Paper(id='p', title='Paper', passages=['  ']), ())
    parse.assert_not_called()


def test_literal_number_check_does_not_match_part_of_thousands():
    assert not extract.number_in_quote(1, "Only 1,000 measurements were used.")
    assert extract.number_in_quote(1000, "Only 1,000 measurements were used.")
    assert not extract.number_in_quote(1, "Only 1,5 measurements were used.")
    assert extract.number_in_quote(0.002, "Error 2e-3.")


def test_source_links_and_placeholder_labels(seed_claims):
    assert paper_url('doi:10.1234/example') == 'https://doi.org/10.1234/example'
    assert paper_url('arxiv:2409.13740') == 'https://arxiv.org/abs/2409.13740'
    assert paper_url('2111.10992v1') == 'https://arxiv.org/abs/2111.10992v1'
    assert paper_url('javascript:alert(1)') is None
    assert 'placeholder' in evidence_label(seed_claims[0]).lower()


def test_ui_evidence_preview_and_results(seed_claims):
    from streamlit.testing.v1 import AppTest

    from alloy.agent.loop import Investigation
    from alloy.contracts import Goal

    app = AppTest.from_file(APP, default_timeout=30)

    app.query_params["demo"] = "1"

    app.run()
    assert not app.exception
    assert any('placeholders' in w.value for w in app.warning)
    assert app.toggle[0].value is False
    assert len(app.dataframe[0].value) == 2
    inv = Investigation(id='ui-test', goal=Goal(question='Test'))
    inv.claims = seed_claims
    inv.condition_report = asdict(conditions.check(*seed_claims, ('noise',)))
    app.session_state['inv'] = inv
    app.run()
    assert not app.exception
    assert any('Demo evidence' in w.value for w in app.warning)
    assert any(s.value == 'Condition Check' for s in app.subheader)
