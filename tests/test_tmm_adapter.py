from alloy.contracts import ExperimentSpec
from alloy.experiments.adapters import get_adapter
from alloy.experiments.adapters.tmm_adapter import performance


def test_bare_silver_reflects_sun_but_does_not_emit():
    bare = performance([], [])
    assert bare["solar_absorptance"] < 0.05
    assert bare["window_emissivity"] < 0.05


def test_thicker_sio2_emits_more_in_the_window():
    assert performance(["SiO2"], [2000])["window_emissivity"] > performance(["SiO2"], [500])["window_emissivity"]


def test_search_methods_report_tolerance_metric():
    spec = ExperimentSpec(
        task="cooling-coatings",
        adapter="tmm",
        method="robust-search",
        conditions={"n_layers": 3, "thickness_tolerance_nm": 20},
        params={"candidates": 4},
    )
    metrics, artifacts = get_adapter("tmm").run(spec)
    assert 0 < metrics["perturbed_cooling_error"] < 1
    assert [layer["material"] for layer in artifacts["layers"]] == ["SiO2", "TiO2", "SiO2"]
