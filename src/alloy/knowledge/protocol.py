"""Turn a paper's full text into an adapter protocol, keeping every value traceable.

The model only extracts settings the text states, each with a quote. Code checks the quote is in
the text and the number is in the quote, fills gaps by fixed rules, and expands ambiguous noise
definitions into labelled readings. Nothing here guesses a value.
"""

import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from alloy import llm
from alloy.config import settings
from alloy.experiments.adapters.pysindy_adapter import DEFAULT_RIDGE, DEFAULT_X0, protocol_issue
from alloy.knowledge.extract import anchor_quote, number_in_quote
from alloy.knowledge.fulltext import Document, relevant_text

SettingKey = Literal[
    "noise",
    "noise_scale",
    "noise_location",
    "noise_type",
    "derivative",
    "x0",
    "dt",
    "t_end",
    "poly_degree",
    "threshold",
    "ridge",
]
LITERATURE = Path(__file__).resolve().parents[3] / "data" / "literature"
REVIEWED_OUTCOMES = LITERATURE / "reviewed_outcomes.json"
# Verified settings a person has checked against the paper: short quotes only, never full text.
# Committed so judges can rerun an audit with no model key and no network.
COMMITTED_PROTOCOLS = LITERATURE / "protocols"

# Adapter defaults, used only when neither paper states a setting.
DEFAULTS: dict[str, Any] = {
    "noise_type": "gaussian",
    "noise_location": "state",
    "derivative": "numeric",
    "x0": list(DEFAULT_X0),
    "dt": 0.002,
    "t_end": 10.0,
    "poly_degree": 2,
    "ridge": DEFAULT_RIDGE,
}
SHARED_KEYS = ("noise_type", "noise_location", "derivative", "x0", "dt", "t_end", "poly_degree", "ridge")
# Never copied from the other paper: they are the likeliest causes of a disagreement, so borrowing
# them could hide the answer. Unstated, they take the labelled adapter default.
PER_PAPER_KEYS = ("noise_location", "derivative")


class StatedSetting(BaseModel):
    key: SettingKey
    value: str = Field(description="The value as the paper writes it, e.g. '0.01', '8%', '[5, 5, 25]', 'variance'")
    quote: str = Field(description="The exact sentence from the text that states it")


class ReportedOutcome(BaseModel):
    result: Literal["recovers", "fails"]
    noise_as_written: str = Field(description="The noise level this result is reported at, as written")
    quote: str


class ProtocolExtraction(BaseModel):
    system: str = Field(description="The dynamical system of the experiment, e.g. lorenz")
    settings: list[StatedSetting] = Field(default_factory=list)
    outcomes: list[ReportedOutcome] = Field(default_factory=list)


SYSTEM = """You read the methods of a sparse-regression (SINDy) paper and record the experimental
settings it states for its chaotic Lorenz (1963) example. Only record what the text states. Never
infer or assume a value. Copy each quote exactly from the text.

Setting keys:
- noise: the noise level, as written (a number or a percentage)
- noise_scale: how the level is defined: "variance" (it is the noise variance), "absolute" (it is the
  noise standard deviation), "state_std" (std relative to the signal std), "variance_ratio"
  (var(noise)/var(signal))
- noise_location: "state" if noise is added to measured states, "derivative" if added to derivatives
- noise_type: "gaussian" or "outliers"
- derivative: "exact" if derivatives come from the equations, "numeric" if from finite differences
- x0: initial condition; dt: time step; t_end: end time of the trajectory
- poly_degree: highest polynomial degree in the library
- threshold: the sparsity threshold (lambda); ridge: "0" if the paper uses plain least squares

Outcomes: only results of the standard SINDy algorithm (sequential thresholded least squares) on
the Lorenz system, not of modified or new methods. "recovers" if it identifies the correct equations,
"fails" if it does not."""


class Setting(BaseModel):
    value: Any
    source: Literal["stated", "other_paper", "default", "rule", "reading"]
    quote: str | None = None
    note: str | None = None


class Protocol(BaseModel):
    paper: str
    system: str
    settings: dict[str, Setting]
    outcome: ReportedOutcome | None = None
    outcome_source: Literal["text", "reviewed", "none"] = "none"
    outcome_note: str | None = None
    rejected: list[str] = Field(default_factory=list)


def _numbers(text: str) -> list[float]:
    text = text.replace("\\times 10^{", "e").replace("10^{", "1e").replace("}", " ")
    out = []
    for token in re.findall(r"[+-]?(?:\d+\.?\d*|\.\d+)(?:e[+-]?\d+)?", text, re.I):
        try:
            out.append(float(token))
        except ValueError:
            continue
    return [n for n in out if math.isfinite(n)]


ENUMS = {
    "noise_scale": {
        "variance_ratio": ("variance_ratio", "ratio of variance", "var(noise)", "var(signal)"),
        "variance": ("variance",),
        "absolute": ("absolute", "standard deviation", "std"),
        "state_std": ("state_std", "relative", "signal std"),
    },
    "noise_location": {"derivative": ("derivative",), "state": ("state", "measure", "observ", "trajector")},
    "noise_type": {"gaussian": ("gauss", "normal"), "outliers": ("outlier", "spike")},
    "derivative": {"exact": ("exact", "analytic", "true", "clean"), "numeric": ("numeric", "finite", "differenc")},
}


def _plain(text: str) -> str:
    """Lowercase text with LaTeX wrappers removed, so a quote of Eq. 19 reads var(noise)/var(signal)."""
    for wrapper in ("\\mbox{", "\\text{", "\\mathrm{", "\\operatorname{"):
        text = text.replace(wrapper, "")
    return text.replace("}", "").lower()


def parse_value(key: str, text: str) -> Any:
    """Parse a stated value. Returns None when the text does not give a usable value."""
    low = text.lower()
    if key in ENUMS:
        for value, words in ENUMS[key].items():
            if any(w in low for w in words):
                return value
        return None
    nums = _numbers(text)
    if key == "x0":
        return nums[:3] if len(nums) >= 3 else None
    if not nums:
        return None
    if key == "t_end":
        return max(nums)
    if key == "poly_degree":
        return int(nums[0]) if float(nums[0]).is_integer() else None
    if key == "noise":
        return nums[0] / 100 if "%" in text else nums[0]
    return nums[0]


def extract(
    doc: Document, budget_chars: int = 12000, use_cache: bool = True, cache_dir: Path | None = None
) -> tuple[ProtocolExtraction, str]:
    """One model call per paper, cached by paper, text and model, so a rerun gives the same
    extraction and spends no quota. Delete the cache file to extract again."""
    text = relevant_text(doc, budget_chars)
    key = hashlib.sha1(f"{settings.model}|{SYSTEM}|{text}".encode()).hexdigest()[:12]
    path = Path(cache_dir or settings.cache_dir) / "protocols" / f"{doc.paper_id}-{key}.json"
    if use_cache and path.exists():
        return ProtocolExtraction.model_validate_json(path.read_text(encoding="utf-8")), text
    prompt = f"Paper {doc.paper_id}. Methods and results text:\n\n{text}"
    raw = llm.parse(prompt, ProtocolExtraction, system=SYSTEM)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(raw.model_dump_json(indent=1), encoding="utf-8")
    return raw, text


def verify(raw: ProtocolExtraction, text: str, paper: str) -> Protocol:
    """Keep only settings whose quote is in the text and, for numbers, whose value is in the quote."""
    settings, rejected = {}, []
    for s in raw.settings:
        quote = anchor_quote(s.quote, [text])
        value = parse_value(s.key, s.value)
        if quote is None:
            rejected.append(f"{s.key}={s.value}: quote not found in the paper text")
        elif value is None:
            rejected.append(f"{s.key}={s.value}: value not parseable")
        elif isinstance(value, float) and s.key != "noise" and not number_in_quote(value, quote):
            rejected.append(f"{s.key}={s.value}: number not in its quote")
        elif s.key in ENUMS and not any(w in _plain(quote) for w in ENUMS[s.key][value]):
            rejected.append(f"{s.key}={s.value}: the quote does not say this")
        elif s.key not in settings:
            settings[s.key] = Setting(value=value, source="stated", quote=quote, note=s.value)
    outcome = None
    for o in raw.outcomes:
        if anchor_quote(o.quote, [text]) is not None:
            outcome = o
            break
        rejected.append(f"outcome {o.result}: quote not found in the paper text")
    return Protocol(
        paper=paper,
        system=raw.system.lower(),
        settings=settings,
        outcome=outcome,
        outcome_source="text" if outcome else "none",
        rejected=rejected,
    )


def apply_reviewed_outcome(protocol: Protocol, path: Path = REVIEWED_OUTCOMES) -> Protocol:
    """Use a human-read outcome when the result is only in a figure or table image. Labelled as such."""
    try:
        reviewed = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return protocol
    entry = reviewed.get(protocol.paper)
    if entry:
        protocol.outcome = ReportedOutcome(
            result=entry["result"], noise_as_written=entry["noise_as_written"], quote=entry["locator"]
        )
        protocol.outcome_source = "reviewed"
        protocol.outcome_note = entry.get("note")
        for key, reason in entry.get("unstated", {}).items():
            if protocol.settings.pop(key, None) is not None:
                protocol.rejected.append(f"{key}: dropped by reviewer ({reason})")
    return protocol


class Reading(BaseModel):
    label: str
    noise: float
    noise_scale: str


def readings(protocol: Protocol) -> list[Reading]:
    """Interpretations of the reported noise level. The paper's own definition comes first."""
    if protocol.outcome is None:
        return []
    written = protocol.outcome.noise_as_written
    nums = _numbers(written)
    if not nums:
        return []
    level, percent = nums[0], "%" in written
    stated = protocol.settings.get("noise_scale")
    scale = stated.value if stated else None
    out = []
    if percent:
        ratio = level / 100
        options = [
            (
                "variance_ratio",
                Reading(label=f"{written} as var(noise)/var(signal)", noise=math.sqrt(ratio), noise_scale="state_std"),
            ),
            ("state_std", Reading(label=f"{written} as std(noise)/std(signal)", noise=ratio, noise_scale="state_std")),
        ]
    else:
        options = [
            ("variance", Reading(label=f"{written} as noise variance", noise=level, noise_scale="variance")),
            ("absolute", Reading(label=f"{written} as noise std", noise=level, noise_scale="absolute")),
            ("state_std", Reading(label=f"{written} x signal std", noise=level, noise_scale="state_std")),
        ]
    options.sort(key=lambda kv: kv[0] != scale)  # the paper's stated definition first
    for _, reading in options:
        out.append(reading)
    return out


def fill(own: Protocol, other: Protocol) -> dict[str, Setting]:
    """Complete one paper's settings by rule: stated, else the other paper's stated value, else the
    adapter default. Noise level and threshold stay per paper and are handled by readings and sweeps."""
    filled = {k: v for k, v in own.settings.items() if k not in ("noise", "noise_scale", "threshold")}
    for key in SHARED_KEYS:
        if key in filled:
            continue
        if key == "derivative" and filled.get("noise_location", Setting(value=None, source="rule")).value == "state":
            filled[key] = Setting(value="numeric", source="rule", note="noisy states need numerical derivatives")
        elif key in other.settings and key not in PER_PAPER_KEYS:
            filled[key] = Setting(
                value=other.settings[key].value, source="other_paper", note=f"stated by {other.paper}"
            )
        else:
            filled[key] = Setting(value=DEFAULTS[key], source="default", note="adapter default")
    if "threshold" in own.settings:
        filled["threshold"] = own.settings["threshold"]
    return filled


def conditions(filled: dict[str, Setting], reading: Reading) -> dict[str, Any]:
    conds = {
        "system": "lorenz",
        **{k: s.value for k, s in filled.items()},
        "noise": reading.noise,
        "noise_scale": reading.noise_scale,
    }
    if issue := protocol_issue(conds):
        raise ValueError(issue)
    return conds


def load_committed(paper: str, directory: Path = COMMITTED_PROTOCOLS) -> Protocol | None:
    path = Path(directory) / f"{(paper.split(':')[-1])}.json"
    return Protocol.model_validate_json(path.read_text(encoding="utf-8")) if path.exists() else None


def save_committed(proto: Protocol, directory: Path = COMMITTED_PROTOCOLS) -> Path:
    path = Path(directory) / f"{proto.paper.split(':')[-1]}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(proto.model_dump_json(indent=1), encoding="utf-8")
    return path
