"""Greedy constructive solver for the two-echelon routing problem (Sprint 1 prototype).

The solver follows the single-trip baseline of our model: every route is one trip of one
vehicle, fixed costs are paid per trip, hubs start empty and vans leave only once the stock
they carry has been unloaded at their hub.

Pipeline
  1. Van routes   customers sorted by closing time, each inserted at the cheapest feasible
                  position of an existing route, or in a new route from the cheapest hub.
  2. Group 1      every hub dispatches at least 2 vans and no hub more than half of them
                  (used when the instance has several hubs, as the online evaluator does).
  3. Improvement  relocate single customers while the cost decreases (time limited).
  4. Trucks       choose truck trips (hub subsets and visiting order) whose unloadings can
                  supply every van in time; checked exactly with a max flow (model 29-33).
                  Exhaustive search when there are few hubs, savings heuristic otherwise.
  5. Vehicles     chain trips onto physical vehicles (multi-trip extension of the model):
                  trips of one vehicle do not overlap, a truck reloads at the DP between
                  trips, a van always works from the same hub (carrier binding), and the
                  whole day stays within the shift limit. max_available bounds the number of
                  physical vehicles; fixed costs stay per trip, as in the validator.

Usage
  python3 src/greedy.py -i data/instances/instance_03_medium_35pl.json -o solutions/03.json
"""
import argparse
import itertools
import json
import math
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import InstanceError, allocate_stock, load_instance  # noqa: E402

INF = float("inf")


class Infeasible(Exception):
    """The rules cannot all be met; the message says which ones conflict."""


class Solver:
    def __init__(self, inst, group1=True, fleet_limits=True, time_limit=30.0, multi_trip=True):
        self.I = inst
        self.group1 = group1 and len(inst.hubs) > 1
        self.fleet_limits = fleet_limits
        self.multi_trip = multi_trip
        # With multi-trip, max_available limits physical vehicles (checked after chaining),
        # not trips; in the single-trip baseline it limits trips directly.
        self.nmax_v = inst.nmax_v if fleet_limits and not multi_trip else None
        self.nmax_t = inst.nmax_t if fleet_limits and not multi_trip else None
        self.time_limit = time_limit
        # Earliest time a hub can hold stock: a direct truck leaving the DP at opening.
        self.ready = {}
        for h in inst.hubs:
            arrival = inst.open(inst.dp) + inst.tt(inst.dp, h)
            self.ready[h] = max(arrival, inst.open(h)) + inst.service(h)

    # ================================================================ van routes
    def load_ok(self, seq):
        """Van capacity at departure and after every stop (pickups take space)."""
        I = self.I
        load = sum(I.demand(c) for c in seq)
        if load > I.cap_v:
            return False
        for c in seq:
            load += I.pickup(c) - I.demand(c)
            if load > I.cap_v:
                return False
        return True

    def latest_departure(self, hub, seq):
        """Latest departure from `hub` that still serves `seq` inside every time window and
        returns before the hub closes (backward pass). Leaving as late as possible removes
        useless waiting, so it also gives the shortest shift."""
        I = self.I
        latest_end = I.close(hub)                     # latest return to the hub
        nxt = hub
        for c in reversed(seq):
            # service at c must end before c closes and early enough to reach the next stop
            latest_start = min(I.close(c), latest_end - I.tt(c, nxt)) - I.service(c)
            latest_end, nxt = latest_start, c        # latest_end now means "latest start at c"
        return latest_end - I.tt(hub, nxt)

    def simulate(self, hub, seq, dep):
        """Forward pass: [(node, arrival, departure)] leaving `hub` at `dep`, or None."""
        I = self.I
        t, prev, stops = dep, hub, [(hub, dep, dep)]
        for c in seq:
            arrival = t + I.tt(prev, c)
            start = max(arrival, I.open(c))
            if start + I.service(c) > I.close(c):
                return None
            t = start + I.service(c)
            stops.append((c, arrival, t))
            prev = c
        back = t + I.tt(prev, hub)
        if back > I.close(hub):
            return None
        stops.append((hub, back, back))
        return stops

    def schedule(self, hub, seq):
        """Feasible van schedule for `seq` from `hub`, or None. Checks capacity, windows,
        hub opening hours, stock availability (ready time) and the shift limit."""
        if not seq or not self.load_ok(seq):
            return None
        I = self.I
        dep = min(self.latest_departure(hub, seq), I.close(hub))
        if dep < max(self.ready[hub], I.open(hub)):
            return None
        stops = self.simulate(hub, seq, dep)
        if stops is None or stops[-1][1] - dep > I.dmax_v:
            return None
        return stops

    def departure_window(self, hub, seq):
        """[earliest, latest] departures for which `seq` is feasible from `hub`, or None.
        Time windows only bound the latest departure; leaving earlier adds waiting, so the
        shift limit bounds the earliest one (shift length never grows with later departures)."""
        if self.schedule(hub, seq) is None:
            return None
        I = self.I
        late = min(self.latest_departure(hub, seq), I.close(hub))
        lo, hi = max(self.ready[hub], I.open(hub)), late
        while lo < hi:
            mid = (lo + hi) // 2
            st = self.simulate(hub, seq, mid)
            if st is not None and st[-1][1] - mid <= I.dmax_v:
                hi = mid
            else:
                lo = mid + 1
        return lo, late

    def km(self, hub, seq):
        return self.I.path_km([hub] + list(seq) + [hub])

    def route_cost(self, hub, seq):
        return self.I.fixed_v + self.I.km_v * self.km(hub, seq) if seq else 0

    def total_cost(self, routes):
        return sum(self.route_cost(h, s) for h, s in routes)

    def best_insertion(self, routes, c, allow_new=True):
        """Cheapest feasible way to add customer c.
        Returns (extra cost, target, new sequence); target is a route index or ('new', hub)."""
        best = (INF, None, None)
        for r, (h, seq) in enumerate(routes):
            base = self.km(h, seq)
            for pos in range(len(seq) + 1):
                new = seq[:pos] + [c] + seq[pos:]
                delta = self.I.km_v * (self.km(h, new) - base)
                if delta < best[0] and self.schedule(h, new) is not None:
                    best = (delta, r, new)
        if allow_new and (self.nmax_v is None or len(routes) < self.nmax_v):
            for h in self.I.hubs:
                delta = self.route_cost(h, [c])
                if delta < best[0] and self.schedule(h, [c]) is not None:
                    best = (delta, ("new", h), [c])
        return best

    @staticmethod
    def apply(routes, target, seq):
        if isinstance(target, tuple):
            routes.append([target[1], seq])
        else:
            routes[target][1] = seq

    def construct(self):
        """Cheapest insertion, most urgent customers first."""
        I = self.I
        for c in I.customers:
            if all(self.schedule(h, [c]) is None for h in I.hubs):
                raise Infeasible(f"customer {c} cannot be served even by a dedicated van "
                                 f"(window {I.open(c)}-{I.close(c)} too early or too far from every hub)")
        routes = []
        for c in sorted(I.customers, key=lambda c: (I.close(c), -I.demand(c))):
            _, target, seq = self.best_insertion(routes, c)
            if target is None:
                raise Infeasible(f"customer {c} fits in no route and the van limit ({self.nmax_v}) is reached")
            self.apply(routes, target, seq)
        return routes

    # ================================================================ Group 1 rules
    def counts(self, routes):
        cnt = {h: 0 for h in self.I.hubs}
        for h, _ in routes:
            cnt[h] += 1
        return cnt

    def group1_ok(self, routes):
        """At least 2 vans at every hub and no hub above half of the vans (model 36-37)."""
        if not self.group1:
            return True
        cnt, t = self.counts(routes), len(routes)
        return all(n >= 2 and 2 * n <= t for n in cnt.values())

    def fleet_ok(self, routes):
        return self.nmax_v is None or len(routes) <= self.nmax_v

    def repair_group1(self, routes, max_iter=500):
        """Move whole routes to another hub, or serve one customer alone from another hub,
        until both Group 1 rules hold. Each step takes the cheapest move that lowers the
        violation measure."""
        if not self.group1:
            return routes
        need = 2 * len(self.I.hubs)
        if self.nmax_v is not None and need > self.nmax_v:
            raise Infeasible(f"Group 1 needs at least 2 vans at each of the {len(self.I.hubs)} hubs "
                             f"({need} vans) but the fleet has {self.nmax_v}")

        def violation(rs):
            # a missing van counts double: opening a van at an under-served hub is progress
            # even if it briefly pushes another hub above half of the fleet
            cnt, t = self.counts(rs), len(rs)
            return sum(2 * max(0, 2 - n) + max(0, 2 * n - t) for n in cnt.values())

        for _ in range(max_iter):
            if self.group1_ok(routes):
                return routes
            v0, base = violation(routes), self.total_cost(routes)
            best = (INF, None)
            # move A: give a whole route to another hub
            for r, (h, seq) in enumerate(routes):
                for g in self.I.hubs:
                    if g != h and self.schedule(g, seq) is not None:
                        cand = [list(x) for x in routes]
                        cand[r][0] = g
                        if violation(cand) < v0:
                            d = self.total_cost(cand) - base
                            if d < best[0]:
                                best = (d, cand)
            # move B: take one customer out of a route and serve it alone from a hub
            for r, (h, seq) in enumerate(routes):
                if len(seq) < 2:
                    continue
                for i, c in enumerate(seq):
                    rest = seq[:i] + seq[i + 1:]
                    if self.schedule(h, rest) is None:
                        continue
                    for g in self.I.hubs:
                        if self.schedule(g, [c]) is None:
                            continue
                        cand = [list(x) for x in routes]
                        cand[r][1] = rest
                        cand.append([g, [c]])
                        if self.fleet_ok(cand) and violation(cand) < v0:
                            d = self.total_cost(cand) - base
                            if d < best[0]:
                                best = (d, cand)
            if best[1] is None:
                raise Infeasible("Group 1 rules cannot be met with route moves (try more vans or hubs)")
            routes = best[1]
        raise Infeasible("Group 1 repair did not converge")

    # ================================================================ improvement
    def improve(self, routes, deadline):
        """Relocate one customer at a time (first improvement) while the cost decreases and
        every rule still holds. A route left empty disappears, saving its fixed cost."""
        improved = True
        while improved and time.time() < deadline:
            improved = False
            for r in range(len(routes)):
                if improved or time.time() > deadline:
                    break
                h, seq = routes[r]
                for i, c in enumerate(seq):
                    rest = seq[:i] + seq[i + 1:]
                    if rest and self.schedule(h, rest) is None:
                        continue
                    others = [list(x) for k, x in enumerate(routes) if k != r]
                    if rest:
                        others.append([h, rest])
                    _, target, new = self.best_insertion(others, c, allow_new=False)
                    if target is None:
                        continue
                    cand = [list(x) for x in others]
                    self.apply(cand, target, new)
                    if self.total_cost(cand) < self.total_cost(routes) and self.group1_ok(cand):
                        routes, improved = cand, True
                        break
        return routes

    # ================================================================ trucks
    def truck_trip(self, order):
        """Timing of one truck trip visiting hubs in `order`, or None if infeasible.
        The truck leaves the DP as late as possible without delaying the first unloading."""
        I = self.I
        first = order[0]
        dep = max(I.open(I.dp), I.open(first) - I.tt(I.dp, first))
        t, prev, visits = dep, I.dp, []
        for h in order:
            arrival = t + I.tt(prev, h)
            start = max(arrival, I.open(h))
            done = start + I.service(h)
            if done > I.close(h):
                return None
            visits.append((h, arrival, done))
            t, prev = done, h
        back = t + I.tt(prev, I.dp)
        if back > I.close(I.dp) or back - dep > I.dmax_t:
            return None
        km = I.path_km([I.dp] + list(order) + [I.dp])
        return {"hubs": list(order), "dep": dep, "visits": visits, "ret": back,
                "cost": I.fixed_t + I.km_t * km}

    def stock_ok(self, trips, needs):
        visits = [[(h, done) for h, _, done in tr["visits"]] for tr in trips]
        return allocate_stock(self.I.cap_t, visits, needs)

    def plan_trucks_exhaustive(self, needs, active, kmin, kmax, limit=300000):
        """All multisets of trips over ordered hub subsets, cheapest first."""
        options = [tr for k in range(1, len(active) + 1)
                   for order in itertools.permutations(active, k)
                   if (tr := self.truck_trip(order))]
        structures = []
        for k in range(kmin, kmax + 1):
            for combo in itertools.combinations_with_replacement(range(len(options)), k):
                if {h for i in combo for h in options[i]["hubs"]} >= set(active):
                    structures.append((sum(options[i]["cost"] for i in combo), combo))
                    if len(structures) > limit:
                        return None                    # too many: let the heuristic decide
        for _, combo in sorted(structures):
            trips = [options[i] for i in combo]
            ok, q = self.stock_ok(trips, needs)
            if ok:
                return trips, q
        return None

    def best_order(self, hubs):
        """Cheapest feasible visiting order of a small hub set (all orders up to 6 hubs)."""
        orders = itertools.permutations(hubs) if len(hubs) <= 6 else [tuple(hubs)]
        best = None
        for o in orders:
            tr = self.truck_trip(o)
            if tr and (best is None or tr["cost"] < best["cost"]):
                best = tr
        return best

    def plan_trucks_savings(self, needs, active):
        """Clarke-Wright savings on hubs: start with direct trips (several for a hub whose
        demand exceeds a truck), merge the pair of trips with the largest saving while the
        load fits and the timing allows, then split merged trips again if the stock check
        fails."""
        I = self.I
        demand = {h: sum(l for vh, _, l in needs if vh == h) for h in active}
        groups = []                                    # [hubs, load]
        for h in active:
            full, rest = divmod(demand[h], I.cap_t)
            groups += [[[h], I.cap_t] for _ in range(full)]
            if rest:
                groups.append([[h], rest])
        while True:
            best = None
            for a, b in itertools.combinations(range(len(groups)), 2):
                ha, hb = groups[a][0], groups[b][0]
                if set(ha) & set(hb) or groups[a][1] + groups[b][1] > I.cap_t:
                    continue
                merged = self.best_order(ha + hb)
                if merged is None:
                    continue
                saving = self.best_order(ha)["cost"] + self.best_order(hb)["cost"] - merged["cost"]
                if saving > 0 and (best is None or saving > best[0]):
                    best = (saving, a, b)
            if best is None:
                break
            _, a, b = best
            groups[a] = [groups[a][0] + groups[b][0], groups[a][1] + groups[b][1]]
            del groups[b]
        trips = [self.best_order(g[0]) for g in groups]
        ok, q = self.stock_ok(trips, needs)
        while not ok and any(len(t["hubs"]) > 1 for t in trips):
            # split the multi-hub trip whose last unloading is the latest
            k = max((i for i, t in enumerate(trips) if len(t["hubs"]) > 1),
                    key=lambda i: trips[i]["visits"][-1][2])
            trips = trips[:k] + [self.truck_trip([h]) for h in trips[k]["hubs"]] + trips[k + 1:]
            ok, q = self.stock_ok(trips, needs)
        return (trips, q) if ok else None

    def plan_trucks(self, van_scheds):
        I = self.I
        needs = [(h, st[0][2], sum(I.demand(c) for c, _, _ in st[1:-1])) for h, st in van_scheds]
        active = sorted({h for h, _, l in needs if l > 0})
        total = sum(l for _, _, l in needs)
        kmin = max(1, math.ceil(total / I.cap_t))
        kmax = kmin + 2 if self.nmax_t is None else min(self.nmax_t, kmin + 2)
        if self.nmax_t is not None and kmin > self.nmax_t:
            raise Infeasible(f"demand {total} needs {kmin} truck trips, the fleet has {self.nmax_t}")
        plan = None
        if len(active) <= 3:
            plan = self.plan_trucks_exhaustive(needs, active, kmin, kmax)
        if plan is None:
            plan = self.plan_trucks_savings(needs, active)
        if plan is None:
            raise Infeasible("no truck plan supplies every van before it leaves")
        trips, q = plan
        if self.nmax_t is not None and len(trips) > self.nmax_t:
            raise Infeasible(f"truck plan needs {len(trips)} trips, the fleet has {self.nmax_t}")
        return trips, q

    # ================================================================ vehicles
    @staticmethod
    def chain(trips, gap, dmax):
        """Assign trips (key, group, dep, ret) to physical vehicles, best fit by start time.
        A vehicle takes trips of one group only (a van stays at its hub), leaves again at
        least `gap` minutes after its previous return, and its day (first departure to
        last return) lasts at most `dmax`. Returns a list of vehicles, each a list of keys."""
        vehicles = []                                  # [group, first_dep, last_ret, keys]
        for key, group, dep, ret in sorted(trips, key=lambda x: x[2]):
            fits = [v for v in vehicles
                    if v[0] == group and v[2] + gap <= dep and ret - v[1] <= dmax]
            if fits:
                v = max(fits, key=lambda v: v[2])      # the one that has been idle the least
                v[2], v[3] = ret, v[3] + [key]
            else:
                vehicles.append([group, dep, ret, [key]])
        return [v[3] for v in vehicles]

    def chain_vans_flexible(self, routes):
        """Chain van trips when departures may move inside their feasible window. Trips of a
        hub are taken by earliest possible departure; each one goes to the vehicle of that hub
        that is back the latest but still in time, leaving at max(vehicle back, earliest);
        its day must stay within the shift limit. Returns (vehicles, van schedules) or None."""
        I = self.I
        items = []
        for k, (h, seq) in enumerate(routes):
            win = self.departure_window(h, seq)
            if win is None:
                return None
            items.append((win[0], k, h, seq, win[1]))
        vehicles, scheds = [], {}                       # vehicle: [hub, first_dep, last_ret, keys]
        for early, k, h, seq, late in sorted(items):
            best = None
            for v in vehicles:
                if v[0] != h:
                    continue
                dep = max(v[2], early)
                if dep > late:
                    continue
                st = self.simulate(h, seq, dep)
                if st and st[-1][1] - dep <= I.dmax_v and st[-1][1] - v[1] <= I.dmax_v:
                    if best is None or v[2] > best[0][2]:
                        best = (v, st)
            if best:
                v, st = best
                v[2], v[3] = st[-1][1], v[3] + [k]
            else:
                st = self.simulate(h, seq, early)
                vehicles.append([h, early, st[-1][1], [k]])
            scheds[k] = (h, st)
        # a vehicle with a single trip goes back to its latest departure (less waiting,
        # more time for the stock to arrive)
        for v in vehicles:
            if len(v[3]) == 1:
                k = v[3][0]
                scheds[k] = (routes[k][0], self.schedule(*routes[k]))
        return [v[3] for v in vehicles], [scheds[k] for k in range(len(routes))]

    def solve_vehicles(self, routes):
        """Van schedules, truck plan and vehicle assignment.
        1. Vans leave as late as possible (best for stock) and the trucks are planned.
        2. If the van fleet is too small, departures may move so that one van chains several
           trips. The truck plan is kept; a van may not leave before the first (then the
           last) unloading of that plan at its hub, and the stock check is run again."""
        I = self.I
        van_scheds = [(h, self.schedule(h, seq)) for h, seq in routes]
        trips, q = self.plan_trucks(van_scheds)
        if self.multi_trip:
            vans = self.chain([(k, h, st[0][2], st[-1][1]) for k, (h, st) in enumerate(van_scheds)], 0, I.dmax_v)
        else:
            vans = [[k] for k in range(len(van_scheds))]

        if self.fleet_limits and I.nmax_v is not None and len(vans) > I.nmax_v:
            fixed = False
            if self.multi_trip:
                base_ready = dict(self.ready)
                done = {}
                for tr in trips:
                    for h, _, fin in tr["visits"]:
                        done.setdefault(h, []).append(fin)
                for pick in (min, max):                       # first unloading, then last one
                    self.ready = {h: max(base_ready[h], pick(done.get(h, [base_ready[h]])))
                                  for h in I.hubs}
                    flexible = self.chain_vans_flexible(routes)
                    self.ready = base_ready
                    if flexible and len(flexible[0]) <= I.nmax_v:
                        visits = [[(h, fin) for h, _, fin in tr["visits"]] for tr in trips]
                        needs = [(h, st[0][2], sum(I.demand(c) for c, _, _ in st[1:-1])) for h, st in flexible[1]]
                        ok, q2 = allocate_stock(I.cap_t, visits, needs)
                        if ok:
                            vans, van_scheds, q, fixed = flexible[0], flexible[1], q2, True
                            break
            if not fixed:
                raise Infeasible(f"{len(van_scheds)} van trips need {len(vans)} vans, the fleet has {I.nmax_v}")
        if self.multi_trip:
            trucks = self.chain([(k, None, t["dep"], t["ret"]) for k, t in enumerate(trips)],
                                I.service(I.dp), I.dmax_t)
        else:
            trucks = [[k] for k in range(len(trips))]
        if self.fleet_limits and I.nmax_t is not None and len(trucks) > I.nmax_t:
            raise Infeasible(f"{len(trips)} truck trips need {len(trucks)} trucks, the fleet has {I.nmax_t}")
        return trips, q, van_scheds, trucks, vans

    # ================================================================ main
    def solve(self):
        deadline = time.time() + self.time_limit
        routes = self.construct()
        routes = self.repair_group1(routes)
        routes = self.improve(routes, deadline)
        if not (self.group1_ok(routes) and self.fleet_ok(routes)):
            raise Infeasible("internal: rules broken after improvement")
        return self.solve_vehicles(routes)


def vehicle_ids(prefix, vehicles):
    """Route key -> vehicle id. A vehicle's second trip is named e.g. Delivery_Van_3_T2."""
    ids = {}
    for v, keys in enumerate(vehicles, 1):
        for r, key in enumerate(keys, 1):
            ids[key] = f"{prefix}_{v}" + (f"_T{r}" if r > 1 else "")
    return ids


def to_json(inst, trips, van_scheds, trucks, vans, team, key):
    """Solution in the official submission format, one route per trip. The claimed cost is
    computed exactly as the validator does (fixed cost per route + rounded km x cost/km)."""
    routes, cost = [], 0
    truck_id, van_id = vehicle_ids("Heavy_Truck", trucks), vehicle_ids("Delivery_Van", vans)
    for k, tr in sorted(enumerate(trips), key=lambda x: truck_id[x[0]]):
        stops = [{"node": inst.dp, "arrival": tr["dep"], "departure": tr["dep"]}]
        stops += [{"node": h, "arrival": a, "departure": d} for h, a, d in tr["visits"]]
        stops.append({"node": inst.dp, "arrival": tr["ret"], "departure": tr["ret"]})
        routes.append({"vehicle_id": truck_id[k], "stops": stops})
        cost += inst.fixed_t + inst.km_t * inst.path_km([s["node"] for s in stops])
    for k, (_, st) in sorted(enumerate(van_scheds), key=lambda x: van_id[x[0]]):
        stops = [{"node": n, "arrival": a, "departure": d} for n, a, d in st]
        routes.append({"vehicle_id": van_id[k], "stops": stops})
        cost += inst.fixed_v + inst.km_v * inst.path_km([s["node"] for s in stops])
    return {"team_name": team, "api_key": key, "instance_id": inst.name,
            "claimed_cost_cents": cost, "routes": routes}


def solve_file(path, out, team="team1", key="sk-most-2026-titan-g1",
               group1=True, fleet_limits=True, time_limit=30.0, multi_trip=True):
    """Solve one instance file and write the solution. Returns a summary dict."""
    inst = load_instance(path)
    trips, _, van_scheds, trucks, vans = Solver(inst, group1, fleet_limits, time_limit, multi_trip).solve()
    sol = to_json(inst, trips, van_scheds, trucks, vans, team, key)
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(sol, f, indent=2)
    per_hub = {}
    for h, _ in van_scheds:
        per_hub[h] = per_hub.get(h, 0) + 1
    return {"instance": inst, "solution": sol, "truck_trips": len(trips), "van_trips": len(van_scheds),
            "trucks": len(trucks), "vans": len(vans), "per_hub": per_hub}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--instance", "-i", required=True)
    ap.add_argument("--out", "-o", required=True)
    ap.add_argument("--team", default="team1")
    ap.add_argument("--api-key", default="sk-most-2026-titan-g1")
    ap.add_argument("--no-group1", action="store_true", help="disable the Group 1 carrier rules")
    ap.add_argument("--ignore-fleet-limits", action="store_true",
                    help="ignore max_available (the online evaluator does not check it)")
    ap.add_argument("--time-limit", type=float, default=30.0, help="seconds for the improvement phase")
    ap.add_argument("--single-trip", action="store_true",
                    help="single-trip baseline: every vehicle runs at most one trip")
    args = ap.parse_args()
    try:
        res = solve_file(args.instance, args.out, args.team, args.api_key, not args.no_group1,
                         not args.ignore_fleet_limits, args.time_limit, not args.single_trip)
    except InstanceError as e:
        sys.exit(f"Invalid instance: {e}")
    except Infeasible as e:
        sys.exit(f"No feasible solution: {e}")
    for w in res["instance"].warnings:
        print("warning:", w)
    print(f"{res['instance'].name}: {res['truck_trips']} truck trips on {res['trucks']} trucks, "
          f"{res['van_trips']} van trips on {res['vans']} vans {res['per_hub']}, "
          f"cost {res['solution']['claimed_cost_cents'] / 100:.2f} EUR -> {args.out}")


if __name__ == "__main__":
    main()
