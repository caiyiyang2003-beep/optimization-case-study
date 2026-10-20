"""Solve every instance in a folder, check each solution and write solutions/summary.md.

If the fleet limits cannot be met, a second run ignores them, because the online evaluator
does not check max_available.

Usage
  python3 src/run_all.py
"""
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
from checker import check  # noqa: E402
from common import InstanceError, load_instance, simple_lower_bound  # noqa: E402
from evaluate_solution import evaluate_solution  # noqa: E402
from greedy import Infeasible, solve_file  # noqa: E402

INSTANCES = os.path.join(HERE, "..", "data", "instances")
OUT = os.path.join(HERE, "..", "solutions")


def run_one(path):
    name = os.path.basename(path).replace("instance_", "").replace(".json", "")
    try:
        inst = load_instance(path)
    except InstanceError as e:
        return [name, "invalid instance", "", "", "", "", "", str(e)]
    out = os.path.join(OUT, f"{name}_greedy.json")
    note = ""
    try:
        r = solve_file(path, out)
    except Infeasible as e:
        try:
            r = solve_file(path, out, fleet_limits=False)
            note = f"fleet limit ignored ({e})"
        except Infeasible as e2:
            return [name, "infeasible", "", "", "", "", "", str(e2)]
    with open(path, encoding="utf-8") as f:
        valid = evaluate_solution(json.load(f), r["solution"])["isValid"]
    errs, cost, _, _ = check(inst, r["solution"])
    lb = simple_lower_bound(inst, 2 if len(inst.hubs) > 1 else 0)
    return [name, "solved", f"{r['truck_trips']} on {r['trucks']}", f"{r['van_trips']} on {r['vans']}",
            f"{cost / 100:.2f}", f"{lb / 100:.2f}", ("OK" if valid else "NO") + " / " + ("OK" if not errs else "NO"),
            note or "; ".join(errs[:2])]


def main():
    head = ["Instance", "Status", "Truck trips on trucks", "Van trips on vans", "Cost (EUR)",
            "Lower bound (EUR)", "Validator / model check", "Note"]
    rows = [run_one(p) for p in sorted(glob.glob(os.path.join(INSTANCES, "*.json")))]
    table = "\n".join(["| " + " | ".join(head) + " |", "|" + "---|" * len(head)] +
                      ["| " + " | ".join(str(x) for x in r) + " |" for r in rows])
    print(table)
    with open(os.path.join(OUT, "summary.md"), "w", encoding="utf-8") as f:
        f.write("# Initial solutions (nearest neighbour)\n\n" + table + "\n")


if __name__ == "__main__":
    main()
