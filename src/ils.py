"""Iterated Local Search, built like the TSP lab (v2): initial solution, VND local search,
perturbation, acceptance criterion.

  Initial solution  nearest neighbour + Group 1 repair (greedy.py)
  Local search      VND: 2-opt then Or-opt, best improvement (chosen by src/tune_vnd.py, see
                    solutions/vnd_comparison.md)
  Perturbation      remove k random customers, put each back at its cheapest feasible place
  Acceptance        accept if the cost is below tolerance x best cost (BestBasedThreshold)
  Stop              time limit

A solution is a list of van routes [hub, [customers]]. The trucks and the assignment of trips
to vehicles are computed from the van routes (greedy.Solver) whenever a total cost is needed.
Local search works on the van cost (fast); acceptance uses the total cost (vans + trucks).

Usage
  python3 src/ils.py -i data/instances/instance_03_medium_35pl.json -o solutions/03_ils.json
"""
import argparse
import csv
import json
import os
import random
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import load_instance  # noqa: E402
from greedy import Infeasible, Solver, to_json  # noqa: E402


# ====================================================================== neighbourhoods
# Each neighbourhood yields candidate moves as (delta van cost, new routes). Moves are only
# yielded when every changed route is feasible and the Group 1 rules still hold.

class Neighbourhoods:
    def __init__(self, solver):
        self.s = solver

    def _ok(self, routes, changed):
        return all(self.s.schedule(h, seq) for h, seq in (routes[r] for r in changed) if seq) \
            and self.s.group1_ok([r for r in routes if r[1]])

    def _delta(self, old, new):
        return self.s.total_cost([r for r in new if r[1]]) - self.s.total_cost([r for r in old if r[1]])

    def _moves(self, routes, changes):
        """changes: iterable of {route index: new sequence}; yields feasible (delta, routes)."""
        for change in changes:
            old = [routes[r] for r in change]
            new = [[routes[r][0], seq] for r, seq in change.items()]
            delta = self._delta(old, new)
            if delta >= 0:
                continue
            cand = [list(x) for x in routes]
            for r, seq in change.items():
                cand[r][1] = seq
            if self._ok(cand, change):
                yield delta, [x for x in cand if x[1]]

    def two_opt(self, routes):
        """Inside one route: reverse the segment seq[i..j] (as in the TSP lab)."""
        def changes():
            for r, (_, seq) in enumerate(routes):
                for i in range(len(seq) - 1):
                    for j in range(i + 1, len(seq)):
                        yield {r: seq[:i] + seq[i:j + 1][::-1] + seq[j + 1:]}
        return self._moves(routes, changes())

    def or_opt(self, routes):
        """Inside one route: move a segment of 1 to 3 consecutive customers elsewhere."""
        def changes():
            for r, (_, seq) in enumerate(routes):
                for k in (1, 2, 3):
                    for i in range(len(seq) - k + 1):
                        seg, rest = seq[i:i + k], seq[:i] + seq[i + k:]
                        for p in range(len(rest) + 1):
                            if p != i:
                                yield {r: rest[:p] + seg + rest[p:]}
        return self._moves(routes, changes())

    def relocate(self, routes):
        """Between routes: move one customer into another route (an emptied route is closed)."""
        def changes():
            for r1, (_, s1) in enumerate(routes):
                for i, c in enumerate(s1):
                    rest = s1[:i] + s1[i + 1:]
                    for r2, (_, s2) in enumerate(routes):
                        if r2 != r1:
                            for p in range(len(s2) + 1):
                                yield {r1: rest, r2: s2[:p] + [c] + s2[p:]}
        return self._moves(routes, changes())

    def swap(self, routes):
        """Between routes: exchange two customers."""
        def changes():
            for r1, (_, s1) in enumerate(routes):
                for r2 in range(r1 + 1, len(routes)):
                    s2 = routes[r2][1]
                    for i in range(len(s1)):
                        for j in range(len(s2)):
                            yield {r1: s1[:i] + [s2[j]] + s1[i + 1:], r2: s2[:j] + [s1[i]] + s2[j + 1:]}
        return self._moves(routes, changes())

    def two_opt_star(self, routes):
        """Between routes: exchange the ends of two routes (A1+B2 and B1+A2)."""
        def changes():
            for r1, (_, s1) in enumerate(routes):
                for r2 in range(r1 + 1, len(routes)):
                    s2 = routes[r2][1]
                    for i in range(len(s1) + 1):
                        for j in range(len(s2) + 1):
                            if (i, j) not in ((0, 0), (len(s1), len(s2))):
                                yield {r1: s1[:i] + s2[j:], r2: s2[:j] + s1[i:]}
        return self._moves(routes, changes())


NEIGHBOURHOODS = ("two_opt", "or_opt", "relocate", "swap", "two_opt_star")


# ====================================================================== ILS components

class VND:
    """Variable Neighbourhood Descent: after an improvement go back to the first
    neighbourhood; stop when none of them improves the van cost."""

    def __init__(self, solver, names=("two_opt", "or_opt"), strategy="best"):
        hood = Neighbourhoods(solver)
        self.hoods = [getattr(hood, n) for n in names]
        self.strategy = strategy

    def improve(self, routes, deadline=None):
        steps, k = 0, 0
        while k < len(self.hoods) and (deadline is None or time.time() < deadline):
            moves = self.hoods[k](routes)
            if self.strategy == "first":
                move = next(moves, None)                       # first improving move
            else:
                move = min(moves, key=lambda m: m[0], default=None)   # best improving move
            if move:
                routes, steps, k = move[1], steps + 1, 0
            else:
                k += 1
        return routes, steps


class RandomRemovalPerturbation:
    """Remove k random customers, then put them back one by one (random order) at the
    cheapest feasible position, or in a new route from the cheapest hub."""

    def __init__(self, solver, rng, k):
        self.s, self.rng, self.k = solver, rng, k

    def perturb(self, routes):
        s = self.s
        removed = self.rng.sample(s.I.customers, min(self.k, len(s.I.customers)))
        routes = [[h, [c for c in seq if c not in removed]] for h, seq in routes]
        routes = [r for r in routes if r[1]]
        self.rng.shuffle(removed)
        for c in removed:
            best = None
            for r, (h, seq) in enumerate(routes):
                base = s.route_cost(h, seq)
                for p in range(len(seq) + 1):
                    new = seq[:p] + [c] + seq[p:]
                    d = s.route_cost(h, new) - base
                    if (best is None or d < best[0]) and s.schedule(h, new):
                        best = (d, r, new)
            for h in s.I.hubs:                                 # or a new van
                d = s.route_cost(h, [c])
                if (best is None or d < best[0]) and s.schedule(h, [c]):
                    best = (d, None, [h, [c]])
            if best[1] is None:
                routes.append(best[2])
            else:
                routes[best[1]][1] = best[2]
        return s.repair_group1(routes)


class BestBasedThresholdAcceptance:
    """Accept a candidate whose cost is below tolerance x best cost (TSP lab v2)."""

    def __init__(self, tolerance=1.02):
        self.tolerance = tolerance

    def accept(self, cost, best_cost):
        return cost < self.tolerance * best_cost


# ====================================================================== ILS

class ILS:
    def __init__(self, inst, time_limit=60.0, seed=0, neighbourhoods=("two_opt", "or_opt"),
                 strategy="best", k=None, tolerance=1.02, fleet_limits=True):
        self.solver = Solver(inst, fleet_limits)
        self.rng = random.Random(seed)
        self.time_limit = time_limit
        self.vnd = VND(self.solver, neighbourhoods, strategy)
        k = k or max(2, round(0.1 * len(inst.customers)))      # 10% of the customers
        self.perturbation = RandomRemovalPerturbation(self.solver, self.rng, k)
        self.acceptance = BestBasedThresholdAcceptance(tolerance)
        self.log = []

    def evaluate(self, routes):
        """Total cost (vans + trucks) and the full plan, or (inf, None) if trucks/fleet fail."""
        s = self.solver
        try:
            vans = [(h, s.schedule(h, seq)) for h, seq in routes]
            trips = s.plan_trucks(vans)
            vans, truck_ids, van_ids = s.assign_vehicles(routes, vans, trips)
        except Infeasible:
            return float("inf"), None
        cost = s.total_cost(routes) + sum(t["cost"] for t in trips)
        return cost, (trips, vans, truck_ids, van_ids)

    def solve(self):
        start = time.time()
        deadline = start + self.time_limit
        current, _ = self.vnd.improve(self.solver.repair_group1(self.solver.nearest_neighbor()), deadline)
        cur_cost, plan = self.evaluate(current)
        best, best_cost, best_plan = current, cur_cost, plan
        it = 0
        while time.time() < deadline:
            it += 1
            try:
                cand, steps = self.vnd.improve(self.perturbation.perturb(current), deadline)
            except Infeasible:                     # Group 1 repair failed: skip this iteration
                continue
            cost, plan = self.evaluate(cand)
            accepted = self.acceptance.accept(cost, best_cost)
            if accepted:
                current, cur_cost = cand, cost
                if cost < best_cost:
                    best, best_cost, best_plan = cand, cost, plan
            self.log.append((it, round(time.time() - start, 2), cur_cost, cost, best_cost, int(accepted), steps))
        return best_cost, best_plan, it


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--instance", "-i", required=True)
    ap.add_argument("--out", "-o", required=True)
    ap.add_argument("--time-limit", type=float, default=60.0)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--neighbourhoods", nargs=2, choices=NEIGHBOURHOODS, default=["two_opt", "or_opt"])
    ap.add_argument("--strategy", choices=("first", "best"), default="best")
    ap.add_argument("--ignore-fleet-limits", action="store_true")
    args = ap.parse_args()

    inst = load_instance(args.instance)
    ils = ILS(inst, args.time_limit, args.seed, args.neighbourhoods, args.strategy,
              fleet_limits=not args.ignore_fleet_limits)
    cost, plan, iterations = ils.solve()
    if plan is None:
        sys.exit("No feasible solution found")
    sol = to_json(inst, *plan)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(sol, f, indent=2)
    with open(os.path.splitext(args.out)[0] + "_progress.csv", "w", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["iter", "elapsed", "current", "candidate", "best", "accepted", "vnd_steps"])
        w.writerows(ils.log)
    print(f"{inst.name}: best {cost / 100:.2f} EUR after {iterations} iterations -> {args.out}")


if __name__ == "__main__":
    main()
