"""Radiative cooling coatings with the transfer-matrix method (stretch task).

Starting point: https://github.com/zaman13/Photonic-Radiative-Cooler and the `tmm` package.
"""

from typing import Any

from alloy.contracts import ExperimentSpec
from alloy.experiments.adapters.base import register


class TMMAdapter:
    name = "tmm"
    task = "cooling-coatings"
    methods = ("baseline-stack",)
    condition_keys = ("layers", "thickness_tolerance_nm", "ambient_k")

    def run(self, spec: ExperimentSpec) -> tuple[dict[str, float], dict[str, Any]]:
        # TODO(santosh, hour 20): layer stack -> tmm.coh_tmm over solar + 8-13 um bands,
        # report net cooling power and its sensitivity to thickness errors.
        raise NotImplementedError("cooling-coatings adapter is the stretch task")


register(TMMAdapter())
