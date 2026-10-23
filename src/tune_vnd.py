"""Which two neighbourhoods should the VND use, with first or best improvement?

Tests the 10 pairs of the 5 neighbourhoods x {first, best} improvement = 20 configurations
on every solvable instance, in two stages:
  A. VND alone from the nearest-neighbour solution (deterministic, fast);
  B. the full ILS with a 60 s time limit (same seed for every configuration).
Runs 4 processes at a time and writes solutions/vnd_comparison.md.

Usage
  python3 src/tune_vnd.py [--time-limit 60] [--workers 4]
"""
import argparse
import itertools
import os
import sys
import time
from multiprocessing import Pool

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from instance_tools import load_instance  # noqa: E402
from greedy_nn import Solver  # noqa: E402
from ils import ILS, NEIGHBOURHOODS, VND  # noqa: E402

INSTANCES = ["01_toy_2pl", "02_small_easy_8pl", "03_medium_35pl", "04_district_50pl",
             "06_micro_hubs_18ds", "10_metropolis_75pl"]
CONFIGS = [(pair, strat) for pair in itertools.combinations(NEIGHBOURHOODS, 2) for strat in ("first", "best")]


def path(name):
    return os.path.join(HERE, "..", "data", "instances", f"instance_{name}.json")


def stage_a(job):
    """VND alone: total cost after one descent from the nearest-neighbour solution."""
    name, (pair, strat) = job
    inst = load_instance(path(name))
    ils = ILS(inst, neighbourhoods=pair, strategy=strat)
    t0 = time.time()
    routes, _ = VND(ils.solver, pair, strat).improve(ils.solver.repair_group1(ils.solver.nearest_neighbor()))
    cost, _ = ils.evaluate(routes)
    return name, pair, strat, cost, time.time() - t0


def stage_b(job):
    """Full ILS with a time limit."""
    name, (pair, strat), limit = job
    inst = load_instance(path(name))
    cost, _, iterations = ILS(inst, limit, 0, pair, strat).solve()
    return name, pair, strat, cost, iterations


def table(results, value_name):
    """Rows = configurations, columns = instances, plus the average rank of each configuration."""
    by = {(n, p, s): v for n, p, s, v, _ in results}
    ranks = {cfg: [] for cfg in CONFIGS}
    for n in INSTANCES:
        ordered = sorted(CONFIGS, key=lambda c: by[(n, c[0], c[1])])
        for cfg in CONFIGS:                          # ties share the best rank
            ranks[cfg].append(1 + sum(by[(n, *o)] < by[(n, *cfg)] for o in ordered))
    head = ["Neighbourhoods", "Improvement"] + INSTANCES + ["Average rank"]
    rows = sorted(CONFIGS, key=lambda c: sum(ranks[c]) / len(INSTANCES))
    lines = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    for p, s in rows:
        cells = [f"{by[(n, p, s)] / 100:.2f}" for n in INSTANCES]
        lines.append(f"| {' + '.join(p)} | {s} | " + " | ".join(cells) + f" | {sum(ranks[(p, s)]) / len(INSTANCES):.1f} |")
    return f"### {value_name}\n\n" + "\n".join(lines) + "\n"


def stage_seed(job):
    name, pair, limit, seed = job
    cost, _, _ = ILS(load_instance(path(name)), limit, seed, pair, "best").solve()
    return name, pair, seed, cost


def stability(limit, workers, seeds=(1, 2, 3, 4, 5)):
    """Stage C: the most promising pairs (best improvement) with several seeds, as the TSP lab
    stability test. Reports mean and best cost per instance."""
    pairs = [("two_opt", "swap"), ("relocate", "swap"), ("swap", "two_opt_star"), ("two_opt", "or_opt"),
             ("or_opt", "two_opt_star"), ("or_opt", "relocate"), ("two_opt", "relocate")]
    names = ["03_medium_35pl", "04_district_50pl", "06_micro_hubs_18ds", "10_metropolis_75pl"]
    with Pool(workers) as pool:
        res = pool.map(stage_seed, [(n, p, limit, s) for n in names for p in pairs for s in seeds])
    head = ["Neighbourhoods (best improvement)"] + [f"{n} mean / best" for n in names] + ["Mean gap to best mean"]
    lines = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    mean = {(n, p): sum(c for m, q, _, c in res if (m, q) == (n, p)) / len(seeds) for n in names for p in pairs}
    low = {(n, p): min(c for m, q, _, c in res if (m, q) == (n, p)) for n in names for p in pairs}
    ref = {n: min(mean[(n, p)] for p in pairs) for n in names}
    gap = {p: sum((mean[(n, p)] - ref[n]) / ref[n] for n in names) / len(names) for p in pairs}
    for p in sorted(pairs, key=gap.get):
        cells = [f"{mean[(n, p)] / 100:.2f} / {low[(n, p)] / 100:.2f}" for n in names]
        lines.append(f"| {' + '.join(p)} | " + " | ".join(cells) + f" | {100 * gap[p]:.2f}% |")
    text = (f"### Stage C: stability, {len(seeds)} seeds x {limit:.0f} s, best improvement\n\n"
            "Mean gap: average over instances of (mean cost - best mean cost) / best mean cost.\n\n"
            + "\n".join(lines) + "\n")
    with open(os.path.join(HERE, "..", "solutions", "vnd_comparison.md"), "a", encoding="utf-8") as f:
        f.write("\n" + text)
    print(text)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--time-limit", type=float, default=60.0)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--stability", action="store_true", help="run stage C only (several seeds)")
    args = ap.parse_args()
    if args.stability:
        return stability(args.time_limit, args.workers)
    with Pool(args.workers) as pool:
        a = pool.map(stage_a, [(n, c) for n in INSTANCES for c in CONFIGS])
        b = pool.map(stage_b, [(n, c, args.time_limit) for n in INSTANCES for c in CONFIGS])
    text = ("# VND configuration comparison\n\nCosts in EUR (vans + trucks). Rank 1 = cheapest on that "
            "instance.\n\n" + table(a, "Stage A: VND alone from the nearest-neighbour solution") + "\n"
            + table(b, f"Stage B: ILS, {args.time_limit:.0f} s, seed 0") + "\n")
    times = {}
    for n, p, s, _, t in a:
        times.setdefault((p, s), []).append(t)
    text += "### Stage A time per descent (s, mean over instances)\n\n" + "\n".join(
        f"- {' + '.join(p)} / {s}: {sum(v) / len(v):.2f}" for (p, s), v in times.items()) + "\n"
    with open(os.path.join(HERE, "..", "solutions", "vnd_comparison.md"), "w", encoding="utf-8") as f:
        f.write(text)
    print(text)


if __name__ == "__main__":
    main()
