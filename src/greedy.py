"""Initial solution: nearest neighbour for the vans, savings for the trucks.

Steps
  1. Vans     nearest neighbour: a van leaves a hub, keeps driving to the closest customer it
              can still serve (capacity with pickups, time windows, shift limit), and returns
              when no customer fits; then the next van starts.
  2. Group 1  every hub sends at least 2 vans and no hub more than half of them.
  3. Trucks   savings heuristic on the hubs; a max flow checks that every van finds its
              stock unloaded before it leaves (model constraints 29-33).
  4. Vehicles trips are chained onto physical vehicles (multi-trip model, constraints 39-45).

Usage
  python3 src/greedy.py -i data/instances/instance_03_medium_35pl.json -o solutions/03.json
"""
import argparse
import itertools
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import InstanceError, allocate_stock, load_instance  # noqa: E402


class Infeasible(Exception):
    """The rules cannot all be met; the message says why."""


class Solver:
    def __init__(self, inst, fleet_limits=True):
        self.I = inst
        self.fleet_limits = fleet_limits
        self.group1 = len(inst.hubs) > 1          # the evaluator applies Group 1 rules then
        # earliest time a hub can hold stock: a truck going straight there at DP opening
        self.ready = {h: max(inst.open(inst.dp) + inst.tt(inst.dp, h), inst.open(h)) + inst.service(h)
                      for h in inst.hubs}

    # ------------------------------------------------------------------ one van route
    def load_ok(self, seq):
        """Capacity when leaving the hub and after every stop (pickups take space)."""
        load = sum(self.I.demand(c) for c in seq)
        if load > self.I.cap_v:
            return False
        for c in seq:
            load += self.I.pickup(c) - self.I.demand(c)
            if load > self.I.cap_v:
                return False
        return True

    def latest_departure(self, hub, seq):
        """Latest time to leave `hub` and still serve `seq` in their windows (backward pass)."""
        I, latest, nxt = self.I, self.I.close(hub), hub
        for c in reversed(seq):
            latest = min(I.close(c), latest - I.tt(c, nxt)) - I.service(c)   # latest start at c
            nxt = c
        return latest - I.tt(hub, nxt)

    def simulate(self, hub, seq, dep):
        """[(node, arrival, departure)] when leaving `hub` at `dep`, or None if a window fails."""
        I, t, prev, stops = self.I, dep, hub, [(hub, dep, dep)]
        for c in seq:
            arrival = t + I.tt(prev, c)
            t = max(arrival, I.open(c)) + I.service(c)
            if t > I.close(c):
                return None
            stops.append((c, arrival, t))
            prev = c
        back = t + I.tt(prev, hub)
        if back > I.close(hub):
            return None
        return stops + [(hub, back, back)]

    def schedule(self, hub, seq, earliest=None):
        """Feasible schedule of a van route, leaving as late as possible (no useless waiting).
        `earliest` is the time stock is available at the hub (default: self.ready)."""
        if not seq or not self.load_ok(seq):
            return None
        earliest = max(self.ready[hub] if earliest is None else earliest, self.I.open(hub))
        dep = min(self.latest_departure(hub, seq), self.I.close(hub))
        if dep < earliest:
            return None
        stops = self.simulate(hub, seq, dep)
        if stops is None or stops[-1][1] - dep > self.I.dmax_v:
            return None
        return stops

    def schedule_early(self, hub, seq, earliest):
        """Feasible schedule leaving as EARLY as possible from `earliest` on (used to chain
        several trips on one van). Leaving earlier only adds waiting, so binary search the
        first departure whose shift still fits in the limit."""
        late = self.schedule(hub, seq, earliest)
        if late is None:
            return None
        lo, hi = max(earliest, self.I.open(hub)), late[0][2]
        while lo < hi:
            mid = (lo + hi) // 2
            st = self.simulate(hub, seq, mid)
            if st and st[-1][1] - mid <= self.I.dmax_v:
                hi = mid
            else:
                lo = mid + 1
        return self.simulate(hub, seq, lo)

    def route_cost(self, hub, seq):
        return self.I.fixed_v + self.I.km_v * self.I.path_km([hub] + seq + [hub])

    def total_cost(self, routes):
        return sum(self.route_cost(h, s) for h, s in routes)

    # ------------------------------------------------------------------ 1. nearest neighbour
    def nearest_neighbor(self):
        I = self.I
        todo = list(I.customers)
        routes = []
        while todo:
            # a new van starts at the hub-customer pair that is closest and feasible
            pairs = [(I.dist(h, c), h, c) for h in I.hubs for c in todo if self.schedule(h, [c])]
            if not pairs:
                raise Infeasible(f"customers {todo} cannot be served even by a dedicated van")
            _, hub, c = min(pairs)
            seq = [c]
            todo.remove(c)
            # it keeps going to the nearest customer that still fits in the route
            while True:
                nxt = [(I.dist(seq[-1], c), c) for c in todo if self.schedule(hub, seq + [c])]
                if not nxt:
                    break
                c = min(nxt)[1]
                seq.append(c)
                todo.remove(c)
            routes.append([hub, seq])
        return routes

    # ------------------------------------------------------------------ 2. Group 1 rules
    def group1_ok(self, routes):
        """At least 2 vans per hub, no hub above half of the vans (model 36-37)."""
        if not self.group1:
            return True
        n = [sum(h == g for h, _ in routes) for g in self.I.hubs]
        return all(k >= 2 and 2 * k <= len(routes) for k in n)

    def violation(self, routes):
        # a missing van counts double, so opening a van at a short hub is always progress
        n = [sum(h == g for h, _ in routes) for g in self.I.hubs]
        return sum(2 * max(0, 2 - k) + max(0, 2 * k - len(routes)) for k in n)

    def repair_group1(self, routes):
        """Cheapest move that reduces the violation, until both rules hold:
        A. give a whole route to another hub, or B. serve one customer alone from a hub."""
        while not self.group1_ok(routes):
            v0, best = self.violation(routes), None
            for r, (h, seq) in enumerate(routes):
                options = [(g, seq, None) for g in self.I.hubs if g != h]                    # move A
                if len(seq) > 1:                                                              # move B
                    options += [(g, [c], i) for i, c in enumerate(seq) for g in self.I.hubs]
                for g, new, i in options:
                    rest = seq if i is None else seq[:i] + seq[i + 1:]
                    if not self.schedule(g, new) or (i is not None and not self.schedule(h, rest)):
                        continue
                    cand = [list(x) for x in routes]
                    if i is None:
                        cand[r][0] = g
                    else:
                        cand[r][1] = rest
                        cand.append([g, new])
                    if self.violation(cand) < v0:
                        cost = self.total_cost(cand)
                        if best is None or cost < best[0]:
                            best = (cost, cand)
            if best is None:
                raise Infeasible("Group 1 rules cannot be met")
            routes = best[1]
        return routes

    # ------------------------------------------------------------------ 3. trucks
    def truck_trip(self, order):
        """One truck trip DP -> hubs in `order` -> DP, or None if it breaks a window or the shift."""
        I = self.I
        dep = max(I.open(I.dp), I.open(order[0]) - I.tt(I.dp, order[0]))   # no early waiting
        t, prev, visits = dep, I.dp, []
        for h in order:
            arrival = t + I.tt(prev, h)
            t = max(arrival, I.open(h)) + I.service(h)                      # end of unloading
            if t > I.close(h):
                return None
            visits.append((h, arrival, t))
            prev = h
        back = t + I.tt(prev, I.dp)
        if back > I.close(I.dp) or back - dep > I.dmax_t:
            return None
        return {"hubs": list(order), "dep": dep, "visits": visits, "ret": back,
                "cost": I.fixed_t + I.km_t * I.path_km([I.dp] + list(order) + [I.dp])}

    def best_trip(self, hubs):
        """Cheapest feasible visiting order of a few hubs."""
        orders = itertools.permutations(hubs) if len(hubs) <= 6 else [hubs]
        trips = [t for t in map(self.truck_trip, orders) if t]
        return min(trips, key=lambda t: t["cost"]) if trips else None

    def plan_trucks(self, vans):
        """Clarke-Wright savings: start from direct trips, merge the pair that saves the most
        while the load fits; if the stock check fails, split the latest merged trip again."""
        I = self.I
        needs = [(h, st[0][2], sum(I.demand(c) for c, _, _ in st[1:-1])) for h, st in vans]
        groups = []                                       # [hubs, load]
        for h in I.hubs:
            demand = sum(l for g, _, l in needs if g == h)
            groups += [[[h], I.cap_t]] * (demand // I.cap_t)
            if demand % I.cap_t:
                groups.append([[h], demand % I.cap_t])
        while True:
            best = None
            for a, b in itertools.combinations(range(len(groups)), 2):
                (ha, la), (hb, lb) = groups[a], groups[b]
                if set(ha) & set(hb) or la + lb > I.cap_t:
                    continue
                merged = self.best_trip(ha + hb)
                if merged:
                    saving = self.best_trip(ha)["cost"] + self.best_trip(hb)["cost"] - merged["cost"]
                    if saving > 0 and (best is None or saving > best[0]):
                        best = (saving, a, b)
            if best is None:
                break
            _, a, b = best
            groups[a] = [groups[a][0] + groups[b][0], groups[a][1] + groups[b][1]]
            del groups[b]
        trips = [self.best_trip(g[0]) for g in groups]
        while True:
            ok, _ = allocate_stock(I.cap_t, [[(h, fin) for h, _, fin in t["visits"]] for t in trips], needs)
            if ok:
                return trips
            multi = [k for k, t in enumerate(trips) if len(t["hubs"]) > 1]
            if not multi:
                raise Infeasible("no truck plan supplies every van before it leaves")
            k = max(multi, key=lambda k: trips[k]["visits"][-1][2])
            trips[k:k + 1] = [self.truck_trip([h]) for h in trips[k]["hubs"]]

    # ------------------------------------------------------------------ 4. vehicles
    @staticmethod
    def chain(trips, gap, dmax):
        """Put trips (key, group, dep, ret) on vehicles: same group, `gap` minutes between two
        trips, whole day within `dmax`. Returns one list of keys per vehicle."""
        vehicles = []                                     # [group, first dep, last return, keys]
        for key, group, dep, ret in sorted(trips, key=lambda x: x[2]):
            fits = [v for v in vehicles if v[0] == group and v[2] + gap <= dep and ret - v[1] <= dmax]
            if fits:
                v = max(fits, key=lambda v: v[2])
                v[2], v[3] = ret, v[3] + [key]
            else:
                vehicles.append([group, dep, ret, [key]])
        return [v[3] for v in vehicles]

    def chain_vans(self, routes, earliest):
        """Like chain, but van trips leave as early as possible (not before `earliest[hub]`),
        so that the next trip of the same van fits in its working day."""
        I, vehicles, scheds = self.I, [], {}
        for _, k, h, seq in sorted((earliest[h], k, h, seq) for k, (h, seq) in enumerate(routes)):
            placed = False
            for v in sorted((v for v in vehicles if v[0] == h), key=lambda v: -v[2]):
                st = self.schedule_early(h, seq, max(earliest[h], v[2]))
                if st and st[-1][1] - v[1] <= I.dmax_v:
                    v[2], v[3] = st[-1][1], v[3] + [k]
                    scheds[k], placed = (h, st), True
                    break
            if not placed:
                st = self.schedule_early(h, seq, earliest[h])
                vehicles.append([h, st[0][2], st[-1][1], [k]])
                scheds[k] = (h, st)
        return [v[3] for v in vehicles], [scheds[k] for k in range(len(routes))]

    def assign_vehicles(self, routes, vans, trips):
        I = self.I
        van_ids = self.chain([(k, h, st[0][2], st[-1][1]) for k, (h, st) in enumerate(vans)], 0, I.dmax_v)
        if self.fleet_limits and I.nmax_v and len(van_ids) > I.nmax_v:
            # Too many vans: let trips leave earlier so one van can run several of them.
            # Try "after the first truck has unloaded at the hub" (stock checked again by max
            # flow), then "after the last one" (the hub then holds all its stock: always fine).
            unload = {h: [f for t in trips for g, _, f in t["visits"] if g == h] or [self.ready[h]]
                      for h in I.hubs}
            visits = [[(h, f) for h, _, f in t["visits"]] for t in trips]
            for pick in (min, max):
                ids, scheds = self.chain_vans(routes, {h: pick(unload[h]) for h in I.hubs})
                needs = [(h, st[0][2], sum(I.demand(c) for c, _, _ in st[1:-1])) for h, st in scheds]
                if len(ids) <= I.nmax_v and allocate_stock(I.cap_t, visits, needs)[0]:
                    van_ids, vans = ids, scheds
                    break
            else:
                raise Infeasible(f"{len(vans)} van trips need {len(van_ids)} vans, the fleet has {I.nmax_v}")
        truck_ids = self.chain([(k, 0, t["dep"], t["ret"]) for k, t in enumerate(trips)],
                               I.service(I.dp), I.dmax_t)
        if self.fleet_limits and I.nmax_t and len(truck_ids) > I.nmax_t:
            raise Infeasible(f"{len(trips)} truck trips need {len(truck_ids)} trucks, the fleet has {I.nmax_t}")
        return vans, truck_ids, van_ids

    # ------------------------------------------------------------------ all steps
    def solve(self):
        routes = self.repair_group1(self.nearest_neighbor())
        vans = [(h, self.schedule(h, seq)) for h, seq in routes]
        trips = self.plan_trucks(vans)
        vans, truck_ids, van_ids = self.assign_vehicles(routes, vans, trips)
        return trips, vans, truck_ids, van_ids


def to_json(inst, trips, vans, truck_ids, van_ids, team="team1", key="sk-most-2026-titan-g1"):
    """Official submission format, one route per trip; a vehicle's 2nd trip is named X_T2.
    The cost is computed as the validator does: fixed cost per route + rounded km x cost/km."""
    def names(prefix, vehicles):
        return {k: f"{prefix}_{v}" + (f"_T{r}" if r > 1 else "")
                for v, keys in enumerate(vehicles, 1) for r, k in enumerate(keys, 1)}

    tid, vid = names("Heavy_Truck", truck_ids), names("Delivery_Van", van_ids)
    routes = [(tid[k], [(inst.dp, t["dep"], t["dep"])] + t["visits"] + [(inst.dp, t["ret"], t["ret"])],
               inst.fixed_t, inst.km_t) for k, t in enumerate(trips)]
    routes += [(vid[k], stops, inst.fixed_v, inst.km_v) for k, (_, stops) in enumerate(vans)]
    out, cost = [], 0
    for name, stops, fixed, per_km in routes:
        out.append({"vehicle_id": name,
                    "stops": [{"node": n, "arrival": a, "departure": d} for n, a, d in stops]})
        cost += fixed + per_km * inst.path_km([s[0] for s in stops])
    return {"team_name": team, "api_key": key, "instance_id": inst.name,
            "claimed_cost_cents": cost, "routes": out}


def solve_file(path, out, fleet_limits=True):
    """Solve one instance file, write the solution and return a short summary."""
    inst = load_instance(path)
    trips, vans, truck_ids, van_ids = Solver(inst, fleet_limits).solve()
    sol = to_json(inst, trips, vans, truck_ids, van_ids)
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(sol, f, indent=2)
    return {"instance": inst, "solution": sol, "truck_trips": len(trips), "van_trips": len(vans),
            "trucks": len(truck_ids), "vans": len(van_ids)}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--instance", "-i", required=True)
    ap.add_argument("--out", "-o", required=True)
    ap.add_argument("--ignore-fleet-limits", action="store_true",
                    help="ignore max_available (the online evaluator does not check it)")
    args = ap.parse_args()
    try:
        r = solve_file(args.instance, args.out, not args.ignore_fleet_limits)
    except InstanceError as e:
        sys.exit(f"Invalid instance: {e}")
    except Infeasible as e:
        sys.exit(f"No feasible solution: {e}")
    print(f"{r['instance'].name}: {r['truck_trips']} truck trips on {r['trucks']} trucks, "
          f"{r['van_trips']} van trips on {r['vans']} vans, "
          f"cost {r['solution']['claimed_cost_cents'] / 100:.2f} EUR -> {args.out}")


if __name__ == "__main__":
    main()
