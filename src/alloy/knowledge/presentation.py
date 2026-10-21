"""Evidence presentation without asserting that a retrieved passage is independently verified."""

from urllib.parse import quote

from alloy.contracts import Claim


def paper_url(identifier: str) -> str | None:
    value = identifier.strip()
    for prefix in ("doi:", "https://doi.org/", "http://doi.org/"):
        if value.startswith(prefix):
            value = value[len(prefix):]
            break
    if value.startswith("10.") and "/" in value:
        return "https://doi.org/" + quote(value, safe="/().-_")
    for prefix in ("arxiv:", "arXiv:", "https://arxiv.org/abs/"):
        if value.startswith(prefix):
            return "https://arxiv.org/abs/" + quote(value[len(prefix):], safe="/.-_")
    return None


def evidence_label(claim: Claim) -> str:
    if claim.source == "seed" or (claim.quote and "placeholder" in claim.quote.lower()):
        return "Demo placeholder — not published evidence"
    if not claim.quote or not claim.quote.strip():
        return "Missing supporting passage"
    return f"{claim.source.title()} passage — source verification required"


def condition_rows(a: Claim, b: Claim) -> list[dict[str, str]]:
    rows = []
    for key in sorted(set(a.conditions) | set(b.conditions) | {"system"}):
        left, right = a.conditions.get(key), b.conditions.get(key)
        missing = left is None or right is None or left == "" or right == ""
        rows.append({
            "Condition": key,
            a.id: "Not stated" if left is None or left == "" else str(left),
            b.id: "Not stated" if right is None or right == "" else str(right),
            "Assessment": "Missing evidence" if missing else "Same" if left == right else "Differs",
        })
    return rows
