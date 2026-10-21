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

    versus = sub.add_parser("versus", help="Alloy vs a plain agent on the same claims and budget")
    versus.add_argument("--runs", type=int, default=60)

    sub.add_parser("check", help="show configuration")

    args = parser.parse_args()
    if args.command == "versus":
        versus_baseline(args.runs)
        return
    if args.command == "check":
        print(json.dumps({
            "model": settings.model,
            "bond_configured": settings.bond_configured,
            "run_dir": str(settings.run_dir),
        }, indent=2))
        return

    from alloy.agent.loop import investigate

    goal = Goal(question=args.question, budget=Budget(runs=args.runs, minutes=args.minutes))
    inv = investigate(goal, offline=not args.online, referee=args.referee)
    print(f"investigation {inv.id}: {inv.runs_used} runs, stopped at stage '{inv.stage}'")
    for method, by in inv.comparison.items():
        print(f"  {method:26s} " + "  ".join(f"{k}: {v:.3f}" for k, v in by.items()))
    if inv.verdict:
        print(f"\n[{inv.verdict.status}] {inv.verdict.explanation}")
    for line in inv.referee:
        print(f"  - {line}")
    print(f"\nreplay notebook: {inv.notebook}")


def versus_baseline(runs: int) -> None:
    from alloy.agent.baseline import run_baseline, runs_to_target
    from alloy.agent.loop import investigate
    from alloy.contracts import RunResult

    goal = Goal(question=DEFAULT_QUESTION, budget=Budget(runs=runs, minutes=10))
    inv = investigate(goal, offline=True)
    if not inv.verdict or inv.verdict.status != "resolved":
        print("Alloy did not resolve the question; nothing to compare against")
        return

    run_dir = settings.run_dir / inv.id
    key = inv.verdict.deciding_conditions[0]
    hard = max(inv.reproduction.values(), key=lambda r: r.metrics["coef_error"]).spec.conditions[key]
    target = inv.comparison[inv.verdict.best_method][str(hard)]
    alloy_runs = [RunResult(**r) for r in json.loads((run_dir / "manifest.json").read_text())]

    print(f"target: coef_error <= {target:.3f} at {key}={hard}; budget {runs} runs\n")
    base = run_baseline(goal, inv.claims, key, hard, target, run_dir / "baseline")
    rows = [
        ("Alloy", runs_to_target(alloy_runs, key, hard, target), inv.runs_used, inv.verdict.best_method),
        ("Plain agent", base.runs_to_target, base.runs_used, base.submitted_method),
    ]
    print(f"{'':12s} {'runs to target':>15s} {'runs used':>10s}  answer")
    for name, hit, used, answer in rows:
        print(f"{name:12s} {hit if hit is not None else 'never':>15} {used:>10d}  {answer}")
    print(f"\nplain agent reason: {base.submitted_reason}")
    print(f"plain agent tokens: {base.input_tokens} in / {base.output_tokens} out over {base.turns} turns")
