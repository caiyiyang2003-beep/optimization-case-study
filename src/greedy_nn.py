import json
import os
import sys
from itertools import accumulate

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from instance_tools import InstanceError, load_instance  # noqa: E402

# ====================================================================== choose here
# 01_toy_2pl, 02_small_easy_8pl, 03_medium_35pl, 04_district_50pl, 05_suburban_52pl,
# 06_micro_hubs_18ds, 07_regional_58pl, 08_legacy_crm_60pl, 09_urban_64pl, 10_metropolis_75pl
INSTANCE = "06_micro_hubs_18ds"


class Infeasible(Exception):
    pass


class Solver:
    def __init__(self, inst):
        self.I = inst
        self.group1 = len(inst.hubs) > 1          # the evaluator applies Group 1 rules then
        # earliest time a hub can hold stock: a truck going straight there at DP opening
        self.ready = {h: max(inst.open(inst.dp) + inst.tt(inst.dp, h), inst.open(h)) + inst.service(h)
                      for h in inst.hubs}

    # ------------------------------------------------------------------ one van route
    def load_ok(self, seq):
        """Capacity when leaving the hub and after every stop (pickups take space)."""
        start = sum(self.I.demand(c) for c in seq)
        changes = (self.I.pickup(c) - self.I.demand(c) for c in seq)
        return max(accumulate(changes, initial=start)) <= self.I.cap_v

    def latest_departure(self, hub, seq):
        """Latest time to leave `hub` and still reach every customer of `seq` before its window closes"""
        I, latest, nxt = self.I, self.I.close(hub), hub
        for c in reversed(seq):
            latest = min(I.close(c), latest - I.tt(c, nxt) - I.service(c))   # latest arrival at c
            nxt = c
        return latest - I.tt(hub, nxt)

    def simulate(self, hub, seq, dep):
        """[(node, arrival, departure)] when leaving `hub` at `dep` and coming back, or None if
        a window fails (arrival after tw_close; service may end later). Used for van routes
        (hub = DS) and truck trips (hub = DP)."""
        I, t, prev, stops = self.I, dep, hub, [(hub, dep, dep)]
        for c in seq:
            arrival = t + I.tt(prev, c)
            if arrival > I.close(c):
                return None
            t = max(arrival, I.open(c)) + I.service(c)
            stops.append((c, arrival, t))
            prev = c
        back = t + I.tt(prev, hub)
        if back > I.close(hub):
            return None
        return stops + [(hub, back, back)]

    def schedule(self, hub, seq):
        """Feasible schedule of a van route, leaving as late as possible (no useless waiting),
        but not before stock can be at the hub (self.ready)."""
        if not seq or not self.load_ok(seq):
            return None
        dep = min(self.latest_departure(hub, seq), self.I.close(hub))
        if dep < max(self.ready[hub], self.I.open(hub)):
            return None
        stops = self.simulate(hub, seq, dep)
        if stops is None or stops[-1][1] - dep > self.I.dmax_v:
            return None
        return stops

    def route_cost(self, hub, seq):
        return self.I.fixed_v + self.I.min_v * self.I.path_min([hub] + seq + [hub])

    def total_cost(self, routes):
        return sum(self.route_cost(h, s) for h, s in routes)

    # 1. nearest neighbour
    def nearest_neighbor(self):
        I = self.I
        todo = list(I.customers)
        routes = []
        while todo:
            # a new van starts at the hub-customer pair that is closest (driving time) and feasible
            pairs = [(I.tt(h, c), h, c) for h in I.hubs for c in todo if self.schedule(h, [c])]
            if not pairs:
                raise Infeasible(f"customers {todo} cannot be served even by a dedicated van")
            _, hub, c = min(pairs)
            seq = [c]
            todo.remove(c)
            # it keeps going to the nearest customer that still fits in the route
            while True:
                nxt = [(I.tt(seq[-1], c), c) for c in todo if self.schedule(hub, seq + [c])]
                if not nxt:
                    break
                c = min(nxt)[1]
                seq.append(c)
                todo.remove(c)
            routes.append([hub, seq])
        return routes

    # 2. Group 1 rules
    def group1_ok(self, routes):
        """At least 2 van routes per hub, at most ceil(t/2) of the t van routes (model 36-37)."""
        if not self.group1:
            return True
        n = [sum(h == g for h, _ in routes) for g in self.I.hubs]
        return all(k >= 2 and 2 * k <= len(routes) + 1 for k in n)

    def violation(self, routes):
        # a missing van counts double, so opening a van at a short hub is always progress
        n = [sum(h == g for h, _ in routes) for g in self.I.hubs]
        return sum(2 * max(0, 2 - k) + max(0, 2 * k - len(routes) - 1) for k in n)

    def repair_group1(self, routes):
        """Until both rules hold, apply the cheapest move that reduces the violation: take one
        customer out of a route and serve it alone, from any hub."""
        while not self.group1_ok(routes):
            v0, best = self.violation(routes), None
            for r, (h, seq) in enumerate(routes):
                for i, c in enumerate(seq if len(seq) > 1 else []):
                    rest = seq[:i] + seq[i + 1:]
                    for g in self.I.hubs:
                        if not self.schedule(g, [c]) or not self.schedule(h, rest):
                            continue
                        cand = [list(x) for x in routes]
                        cand[r][1] = rest
                        cand.append([g, [c]])
                        if self.violation(cand) < v0:
                            cost = self.total_cost(cand)
                            if best is None or cost < best[0]:
                                best = (cost, cand)
            if best is None:
                raise Infeasible("Group 1 rules cannot be met")
            routes = best[1]
        return routes

    # 3. trucks
    def truck_trip(self, order):
        """One truck trip DP -> hubs in `order` -> DP, or None if it breaks a window or the shift."""
        I = self.I
        dep = max(I.open(I.dp), I.open(order[0]) - I.tt(I.dp, order[0]))   # no early waiting
        stops = self.simulate(I.dp, order, dep)
        if stops is None or stops[-1][1] - dep > I.dmax_t:
            return None
        return {"hubs": list(order), "dep": dep, "visits": stops[1:-1], "ret": stops[-1][1],
                "cost": I.fixed_t + I.min_t * I.path_min([I.dp] + list(order) + [I.dp])}

    def plan_trucks(self, vans):
        """Demand above a full truckload goes first in direct trips; the rest by nearest
        neighbour. A hub that runs short of stock gets its own trip, and we try again."""
        I = self.I
        need = {h: 0 for h in I.hubs}
        for h, st in vans:
            need[h] += sum(I.demand(c) for c, _, _ in st[1:-1])
        full, todo = [], {}
        for h, d in need.items():
            while d > I.cap_t:
                full.append(self.direct_trip(h, I.cap_t))
                d -= I.cap_t
            if d:
                todo[h] = d
        alone = set()                                     # hubs served by their own trip
        while True:
            trips = full + [self.direct_trip(h, todo[h]) for h in alone] + \
                self.nearest_trucks({h: d for h, d in todo.items() if h not in alone})
            short = self.short_hubs(trips, vans)
            if not short:
                return trips
            if short <= alone:
                raise Infeasible(f"not enough stock at {sorted(short)} when the vans leave")
            alone |= short

    def direct_trip(self, h, load):
        trip = self.truck_trip([h])
        if trip is None:
            raise Infeasible(f"no truck can reach {h} in its time window")
        trip["unload"] = {h: load}
        return trip

    def nearest_trucks(self, todo):
        """Nearest neighbour for the trucks: from the DP, go to the closest hub (driving time) whose demand
        still fits in the truck and whose window can still be met; back to the DP when none."""
        I, todo, trips = self.I, dict(todo), []
        while todo:
            order, unload = [], {}
            while True:
                last = order[-1] if order else I.dp
                nxt = [(I.tt(last, h), h) for h in todo
                       if sum(unload.values()) + todo[h] <= I.cap_t and self.truck_trip(order + [h])]
                if not nxt:
                    break
                h = min(nxt)[1]
                order.append(h)
                unload[h] = todo.pop(h)
            if not order:
                raise Infeasible(f"no truck can reach {sorted(todo)} in their time windows")
            trip = self.truck_trip(order)
            trip["unload"] = unload
            trips.append(trip)
        return trips

    def short_hubs(self, trips, vans):
        """Hubs where a van would leave before the trucks have unloaded enough stock: at each
        van departure, stock unloaded so far >= goods taken by the vans gone so far."""
        I, short = self.I, set()
        for h in I.hubs:
            unloaded = [(fin, t["unload"][h]) for t in trips for g, _, fin in t["visits"] if g == h]
            departures = sorted((st[0][2], sum(I.demand(c) for c, _, _ in st[1:-1]))
                                for g, st in vans if g == h)
            taken = 0
            for dep, load in departures:
                taken += load
                if taken > sum(q for fin, q in unloaded if fin <= dep):
                    short.add(h)
                    break
        return short

    # all steps
    def solve(self):
        routes = self.repair_group1(self.nearest_neighbor())
        vans = [(h, self.schedule(h, seq)) for h, seq in routes]
        trips = self.plan_trucks(vans)
        return trips, vans


def to_json(inst, trips, vans, team="team1", key="sk-most-2026-titan-g1"):
    """Official submission format, one vehicle per route (max_available is only indicative).
    The cost is computed as the validator does with "version": "2": fixed cost per route +
    driving minutes (duration matrix) x cost per minute."""
    routes = [(f"Heavy_Truck_{k}", [(inst.dp, t["dep"], t["dep"])] + t["visits"] + [(inst.dp, t["ret"], t["ret"])],
               inst.fixed_t, inst.min_t) for k, t in enumerate(trips, 1)]
    routes += [(f"Delivery_Van_{k}", stops, inst.fixed_v, inst.min_v) for k, (_, stops) in enumerate(vans, 1)]
    out, cost = [], 0
    for name, stops, fixed, per_min in routes:
        out.append({"vehicle_id": name,
                    "stops": [{"node": n, "arrival": a, "departure": d} for n, a, d in stops]})
        cost += fixed + per_min * inst.path_min([s[0] for s in stops])
    return {"team_name": team, "api_key": key, "instance_id": inst.name, "version": "2",
            "claimed_cost_cents": cost, "routes": out}


def solve_file(path, out):
    """Solve one instance file, write the solution and return a short summary."""
    inst = load_instance(path)
    trips, vans = Solver(inst).solve()
    sol = to_json(inst, trips, vans)
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(sol, f, indent=2)
    return {"instance": inst, "solution": sol, "truck_trips": len(trips), "van_trips": len(vans)}


def main():
    sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
    from evaluate_solution import evaluate_solution
    path = os.path.join(HERE, "..", "data", "instances", f"instance_{INSTANCE}.json")
    out = os.path.join(HERE, "..", "solutions", f"{INSTANCE}_greedy.json")
    try:
        r = solve_file(path, out)
    except InstanceError as e:
        sys.exit(f"Invalid instance: {e}")
    except Infeasible as e:
        sys.exit(f"No feasible solution: {e}")
    print(f"{r['instance'].name}: {r['truck_trips']} truck routes, {r['van_trips']} van routes, "
          f"cost {r['solution']['claimed_cost_cents'] / 100:.2f} EUR -> solutions/{INSTANCE}_greedy.json")
    with open(path, encoding="utf-8") as f:
        res = evaluate_solution(json.load(f), r["solution"])
    print("Validator:", "OK" if res["isValid"] else "\n  ".join(["NOT VALID"] + res["violations"]))


if __name__ == "__main__":
    main()
