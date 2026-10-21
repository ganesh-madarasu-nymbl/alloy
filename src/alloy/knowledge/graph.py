"""Evidence graph: papers, claims, methods and conditions, plus the conflicts between claims."""

import json
from itertools import combinations
from pathlib import Path

import networkx as nx

from alloy.contracts import Claim


class EvidenceGraph:
    def __init__(self):
        self.g = nx.MultiDiGraph()

    def add_claim(self, claim: Claim) -> None:
        paper, method, node = f"paper:{claim.paper}", f"method:{claim.method}", f"claim:{claim.id}"
        self.g.add_node(paper, kind="paper", title=claim.title)
        self.g.add_node(method, kind="method")
        self.g.add_node(node, kind="claim", data=claim.model_dump())
        self.g.add_edge(paper, node, rel="reports")
        self.g.add_edge(node, method, rel="uses")
        for key, value in claim.conditions.items():
            cond = f"cond:{key}={value}"
            self.g.add_node(cond, kind="condition", key=key, value=value)
            self.g.add_edge(node, cond, rel="under")

    def add_claims(self, claims: list[Claim]) -> None:
        for claim in claims:
            self.add_claim(claim)

    @property
    def claims(self) -> list[Claim]:
        return [Claim(**d["data"]) for _, d in self.g.nodes(data=True) if d["kind"] == "claim"]

    def conflicts(self, rel_tol: float = 0.25) -> list[tuple[Claim, Claim]]:
        """Pairs that measure the same quantity with the same method but report different results."""
        pairs = []
        for a, b in combinations(self.claims, 2):
            if (a.quantity, a.method) != (b.quantity, b.method):
                continue
            if a.value is not None and b.value is not None:
                scale = max(abs(a.value), abs(b.value), 1e-12)
                if abs(a.value - b.value) / scale > rel_tol:
                    pairs.append((a, b))
            elif a.outcome and b.outcome and a.outcome.lower() != b.outcome.lower():
                pairs.append((a, b))
        return pairs

    def methods(self) -> list[str]:
        return [n.removeprefix("method:") for n, d in self.g.nodes(data=True) if d["kind"] == "method"]

    def save(self, path: Path) -> Path:
        Path(path).write_text(
            json.dumps(nx.node_link_data(self.g, edges="links"), indent=2, default=str), encoding="utf-8"
        )
        return Path(path)

    @classmethod
    def load(cls, path: Path) -> "EvidenceGraph":
        graph = cls()
        graph.g = nx.node_link_graph(
            json.loads(Path(path).read_text(encoding="utf-8")), directed=True, multigraph=True, edges="links"
        )
        return graph
