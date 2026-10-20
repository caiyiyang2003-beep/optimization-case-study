"""Solve every instance in a folder, check each solution, and write a summary table.

For each instance file:
  1. load and validate it (broken files are reported, not solved);
  2. run the greedy solver;
  3. check the solution against our model (src/checker.py) and the course validator;
  4. compare the cost with a simple lower bound.
If the fleet limits make the Group 1 rules impossible, a second run without the limits is
made, because the online evaluator does not check max_available.

Usage
  python3 src/run_all.py --instances data/instances --out solutions
"""
import argparse
import glob
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
from checker import check  # noqa: E402
from common import InstanceError, load_instance, simple_lower_bound  # noqa: E402
from evaluate_solution import evaluate_solution  # noqa: E402
from greedy import Infeasible, solve_file  # noqa: E402


def euros(cents):
    return f"{cents / 100:,.2f}".replace(",", " ")


def run_one(path, out_dir, time_limit):
    stem = os.path.splitext(os.path.basename(path))[0].replace("instance_", "")
    row = {"instance": stem, "status": "", "trucks": "", "vans": "", "cost": "", "lb": "", "gap": "",
           "model": "", "validator": "", "note": ""}
    try:
        inst = load_instance(path)
    except InstanceError as e:
        row.update(status="invalid instance", note=str(e))
        return row
    lb = simple_lower_bound(inst, 2 if len(inst.hubs) > 1 else 0)
    row["lb"] = euros(lb)

    out = os.path.join(out_dir, f"{stem}_greedy.json")
    t0 = time.time()
    try:
        res = solve_file(path, out, time_limit=time_limit)
    except Infeasible as e:
        row["note"] = f"with fleet limits: {e}"
        try:                                   # what the online evaluator would accept
            res = solve_file(path, out, fleet_limits=False, time_limit=time_limit)
            row["note"] += "; solved again ignoring max_available"
        except Infeasible as e2:
            row.update(status="infeasible", note=row["note"] + f"; without limits: {e2}")
            return row

    sol = res["solution"]
    errs, cost, _, _ = check(inst, sol)
    with open(path, encoding="utf-8") as f:
        val = evaluate_solution(json.load(f), sol)
    row.update(
        status="solved" if not errs else "solved, model violations",
        trucks=f"{res['truck_trips']} on {res['trucks']}", vans=f"{res['van_trips']} on {res['vans']}",
        cost=euros(cost),
        gap=f"{100 * (cost - lb) / lb:.0f}%",
        model="OK" if not errs else f"{len(errs)} issue(s): " + "; ".join(errs[:3]),
        validator="OK" if val["isValid"] else f"{len(val['violations'])} violation(s)",
    )
    row["note"] = (row["note"] + f" ({time.time() - t0:.1f}s)").strip()
    return row


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--instances", default=os.path.join(HERE, "..", "data", "instances"))
    ap.add_argument("--out", default=os.path.join(HERE, "..", "solutions"))
    ap.add_argument("--time-limit", type=float, default=30.0)
    args = ap.parse_args()

    rows = [run_one(p, args.out, args.time_limit) for p in sorted(glob.glob(os.path.join(args.instances, "*.json")))]
    cols = [("instance", "Instance"), ("status", "Status"), ("trucks", "Truck trips on trucks"), ("vans", "Van trips on vans"),
            ("cost", "Cost (EUR)"), ("lb", "Lower bound (EUR)"), ("gap", "Gap"), ("model", "Model check"),
            ("validator", "Course validator"), ("note", "Note")]
    lines = ["| " + " | ".join(c[1] for c in cols) + " |", "|" + "---|" * len(cols)]
    lines += ["| " + " | ".join(str(r[k]).replace("|", "/") for k, _ in cols) + " |" for r in rows]
    table = "\n".join(lines)
    print(table)
    os.makedirs(args.out, exist_ok=True)
    with open(os.path.join(args.out, "summary.md"), "w", encoding="utf-8") as f:
        f.write("# Greedy results on all instances\n\n"
                "Lower bound: simple instance-independent bound (fixed costs from fleet sizes, cheapest "
                "incoming arc per customer, one out-and-back to the nearest hub per truck trip).\n\n"
                + table + "\n")


if __name__ == "__main__":
    main()
