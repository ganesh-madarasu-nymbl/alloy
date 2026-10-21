import argparse
import json

from alloy.config import settings
from alloy.contracts import Budget, Goal

DEFAULT_QUESTION = "Why do published SINDy results on the Lorenz system disagree, and what fixes it?"


def main() -> None:
    parser = argparse.ArgumentParser(prog="alloy")
    sub = parser.add_subparsers(dest="command", required=True)

    demo = sub.add_parser("demo", help="run one full investigation")
    demo.add_argument("--question", default=DEFAULT_QUESTION)
    demo.add_argument("--online", action="store_true", help="use Bond and Claude instead of seed claims")
    demo.add_argument("--referee", action="store_true", help="run the referee agent (online only)")
    demo.add_argument("--runs", type=int, default=60)
    demo.add_argument("--minutes", type=float, default=5.0)

    bench = sub.add_parser("bench", help="score Alloy and the plain agent on the benchmark scenarios")
    bench.add_argument("--runs", type=int, default=60)
    bench.add_argument("--scenario", action="append", help="limit to these scenario names")
    bench.add_argument("--alloy-only", action="store_true", help="skip the plain agent (no API calls)")
    bench.add_argument(
        "--repeat", type=int, default=1, help="plain-agent runs per scenario (Alloy offline is deterministic)"
    )

    sub.add_parser("check", help="show configuration")
    sub.add_parser("bond-check", help="discover Valency tools using saved Codex OAuth; no model call")
    bond_search = sub.add_parser("bond-search", help="search Bond through Codex OAuth; no model call")
    bond_search.add_argument("query")
    bond_search.add_argument("--limit", type=int, default=5)

    args = parser.parse_args()
    if args.command in {"bond-check", "bond-search"}:
        from alloy.knowledge.bond import cache_mcp_result
        from alloy.knowledge.codex_bond import BondConnectionError, inspect_connection, search_raw

        try:
            if args.command == "bond-check":
                server = inspect_connection()
                print(json.dumps({
                    "server": server["name"], "auth_status": server.get("authStatus"),
                    "runtime_status": server.get("runtimeStatus"), "tools": server["tools"],
                }, indent=2))
            else:
                if not args.query.strip() or not 1 <= args.limit <= 100:
                    parser.error("Provide a nonempty query and a limit from 1 to 100")
                result = search_raw(args.query, args.limit)
                path, papers = cache_mcp_result(args.query, args.limit, result)
                print(json.dumps({"cache": str(path), "papers": [p.model_dump() for p in papers]}, indent=2))
        except (BondConnectionError, OSError, ValueError) as exc:
            parser.exit(1, f"Bond connection unverified: {exc}\n")
        return
    if args.command == "check":
        print(json.dumps({
            "model": settings.model,
            "bond_backend": settings.bond_backend,
            "bond_configured": settings.bond_configured,
            "run_dir": str(settings.run_dir),
        }, indent=2))
        return
    if args.command == "bench":
        run_bench(args.runs, args.scenario, args.alloy_only, args.repeat)
    else:
        run_demo(args)


def run_demo(args) -> None:
    from alloy.agent.loop import investigate

    goal = Goal(question=args.question, budget=Budget(runs=args.runs, minutes=args.minutes))
    inv = investigate(goal, offline=not args.online, referee=args.referee)
    print(f"investigation {inv.id}: {inv.runs_used} runs, stopped at stage '{inv.stage}'")
    if inv.attribution:
        print(
            "  error added by each differing condition: "
            + ", ".join(f"{k} +{v:.3f}" for k, v in inv.attribution.items())
        )
    for method, s in inv.comparison.items():
        print(f"  {method:26s} mean {s['mean']:.3f}  worst {s['worst']:.3f}")
    if inv.verdict:
        print(f"\n[{inv.verdict.status}] {inv.verdict.explanation}")
    for line in inv.referee:
        print(f"  - {line}")
    print(f"\nreplay notebook: {inv.notebook}")


def run_bench(runs: int, names: list[str] | None, alloy_only: bool, repeat: int = 1) -> None:
    from alloy import bench
    from alloy.agent.loop import investigate

    scores: list[bench.Score] = []
    for scenario in bench.load_scenarios(names):
        truth = bench.oracle(scenario)
        print(
            f"\n{scenario.name}: truth = {scenario.truth['deciding_condition']}, "
            f"acceptable answers = {truth.acceptable}"
        )
        goal = Goal(question=scenario.question, budget=Budget(runs=runs, minutes=10))

        inv = investigate(goal, offline=True, claims=scenario.claims)
        cause = inv.verdict.deciding_conditions[0] if inv.verdict and inv.verdict.deciding_conditions else None
        answer = inv.verdict.best_method if inv.verdict else None
        scores.append(bench.score("alloy", scenario, truth, cause, answer, inv.runs_used))

        if not alloy_only:
            from alloy.agent.baseline import run_baseline

            for i in range(repeat):
                base = run_baseline(goal, scenario.claims, settings.run_dir / inv.id / f"baseline-{i}")
                scores.append(
                    bench.score("plain-agent", scenario, truth, base.deciding_condition, base.method, base.runs_used)
                )
                print(
                    f"  plain agent {i + 1}/{repeat}: {base.input_tokens} in / {base.output_tokens} out tokens, "
                    f"{base.turns} turns. Reason: {base.reason}",
                    flush=True,
                )

    print(f"\n{'scenario':20s} {'system':12s} {'cause':>14s} {'answer':>26s} {'oracle err':>10s} {'runs':>5s}")
    for s in scores:
        cause = f"{s.cause}{' ok' if s.cause_correct else ' X'}"
        mark = {True: " ok", False: " X", None: " n/a"}[s.answer_correct]
        answer = f"{s.answer}{mark}"
        err = f"{s.answer_oracle_error:.3f}" if s.answer_oracle_error is not None else "-"
        print(f"{s.scenario:20s} {s.system:12s} {cause:>14s} {answer:>26s} {err:>10s} {s.runs_used:>5d}")
    print(f"\n{'scenario':20s} {'system':12s} {'n':>3s} {'cause ok':>9s} {'answer ok':>10s} {'mean runs':>10s}")
    for row in bench.aggregate(scores):
        answer = "n/a" if row["answer_ok"] is None else f"{row['answer_ok']}/{row['n']}"
        print(
            f"{row['scenario']:20s} {row['system']:12s} {row['n']:>3d} {row['cause_ok']:>7d}/{row['n']} "
            f"{answer:>10s} {row['mean_runs']:>10.1f}"
        )
    record = {"model": settings.model, "repeat": repeat, "scores": [s.model_dump() for s in scores]}
    (settings.run_dir / "bench.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
