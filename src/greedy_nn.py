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
        """Latest time to leave `hub` and still serve `seq` in their windows """
        I, latest, nxt = self.I, self.I.close(hub), hub
        for c in reversed(seq):
            latest = min(I.close(c), latest - I.tt(c, nxt)) - I.service(c)   # latest start at c
            nxt = c
        return latest - I.tt(hub, nxt)

    def simulate(self, hub, seq, dep):
        """[(node, arrival, departure)] when leaving `hub` at `dep` and coming back, or None if
        a window fails. Used for van routes (hub = DS) and truck trips (hub = DP)."""
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

    # 1. nearest neighbour
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

    # 2. Group 1 rules
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
                "cost": I.fixed_t + I.km_t * I.path_km([I.dp] + list(order) + [I.dp])}

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
        """Nearest neighbour for the trucks: from the DP, go to the closest hub whose demand
        still fits in the truck and whose window can still be met; back to the DP when none."""
        I, todo, trips = self.I, dict(todo), []
        while todo:
            order, unload = [], {}
            while True:
                last = order[-1] if order else I.dp
                nxt = [(I.dist(last, h), h) for h in todo
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

    # 4. vehicles
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
        so that the next trip of the same van fits in its working day. None if a trip cannot
        leave that late."""
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
                if st is None:
                    return None
                vehicles.append([h, st[0][2], st[-1][1], [k]])
                scheds[k] = (h, st)
        return [v[3] for v in vehicles], [scheds[k] for k in range(len(routes))]

    def assign_vehicles(self, routes, vans, trips):
        """Chain the trips onto physical vehicles and check the fleet limits (max_available)."""
        I = self.I
        van_ids = self.chain([(k, h, st[0][2], st[-1][1]) for k, (h, st) in enumerate(vans)], 0, I.dmax_v)
        if I.nmax_v and len(van_ids) > I.nmax_v:
            # Too many vans: let trips leave as early as possible, so that one van can run
            # several of them, but not before the last truck has unloaded at the hub (the hub
            # then holds all its stock, so the stock check still holds).
            last = {h: max([f for t in trips for g, _, f in t["visits"] if g == h], default=self.ready[h])
                    for h in I.hubs}
            chained = self.chain_vans(routes, last)
            if chained is None or len(chained[0]) > I.nmax_v:
                raise Infeasible(f"{len(vans)} van trips need more than the {I.nmax_v} vans of the fleet")
            van_ids, vans = chained
        truck_ids = self.chain([(k, 0, t["dep"], t["ret"]) for k, t in enumerate(trips)],
                               I.service(I.dp), I.dmax_t)
        if I.nmax_t and len(truck_ids) > I.nmax_t:
            raise Infeasible(f"{len(trips)} truck trips need {len(truck_ids)} trucks, the fleet has {I.nmax_t}")
        return vans, truck_ids, van_ids

    # all steps
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


def solve_file(path, out):
    """Solve one instance file, write the solution and return a short summary."""
    inst = load_instance(path)
    trips, vans, truck_ids, van_ids = Solver(inst).solve()
    sol = to_json(inst, trips, vans, truck_ids, van_ids)
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(sol, f, indent=2)
    return {"instance": inst, "solution": sol, "truck_trips": len(trips), "van_trips": len(vans),
            "trucks": len(truck_ids), "vans": len(van_ids)}


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
    print(f"{r['instance'].name}: {r['truck_trips']} truck trips on {r['trucks']} trucks, "
          f"{r['van_trips']} van trips on {r['vans']} vans, "
          f"cost {r['solution']['claimed_cost_cents'] / 100:.2f} EUR -> solutions/{INSTANCE}_greedy.json")
    with open(path, encoding="utf-8") as f:
        res = evaluate_solution(json.load(f), r["solution"])
    print("Validator:", "OK" if res["isValid"] else "\n  ".join(["NOT VALID"] + res["violations"]))


if __name__ == "__main__":
    main()
