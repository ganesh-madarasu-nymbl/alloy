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

    sub.add_parser("check", help="show configuration")

    args = parser.parse_args()
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
