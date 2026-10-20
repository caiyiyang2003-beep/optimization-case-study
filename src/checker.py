"""Check a solution JSON against our mathematical model (stricter than the course validator)
and also run the course validator (scripts/evaluate_solution.py).

Model checks
  - route structure: trucks DP -> hubs -> DP, vans hub -> customers -> same hub
  - every customer served exactly once
  - recorded times consistent with travel times; service inside the window (start >= open,
    end <= close); vans back before the hub closes; shift limits
  - van load after every stop (pickups included) and truck load per trip
  - hub stock: an allocation of truck unloadings to vans exists (constraints 29-33),
    using each truck's recorded departure from the hub as the time the stock is ready
  - physical vehicles (trips named X and X_T2, X_T3... share one vehicle): no overlap,
    trucks reload at the DP between trips, a van keeps its hub, day within the shift
    limit, and at most max_available vehicles of each type
  - Group 1 rules, counted on van trips (ours: >= 2 per hub and <= half of them;
    the evaluator's: >= 2 per hub and <= ceil(t/2))
  - claimed cost equals the recomputed cost

Usage
  python3 src/checker.py --instance data/medium_35pl/instance_medium_35pl.json \
                         --solution solutions/medium_35pl_greedy.json
"""
import argparse
import json
import math
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
from common import load_instance, allocate_stock  # noqa: E402
from evaluate_solution import evaluate_solution  # noqa: E402


def check(inst, sol, group1=True):
    errs = []
    err = errs.append
    I = inst
    trucks, vans = [], []
    for r in sol.get("routes", []):
        vid, stops = r.get("vehicle_id", "?"), r.get("stops", [])
        if not stops and r.get("route"):        # legacy format: node list + departure time
            ids = r["route"]
            t = r.get("departure_time", I.open(ids[0]))
            stops = [{"node": ids[0], "arrival": t, "departure": t}]
            for a, b in zip(ids, ids[1:]):
                arr = t + I.tt(a, b)
                t = max(arr, I.open(b)) + I.service(b) if b != ids[-1] else arr
                stops.append({"node": b, "arrival": arr, "departure": t})
        if len(stops) < 2:
            err(f"[{vid}] fewer than 2 stops")
            continue
        start = stops[0]["node"]
        if start not in I.nodes:
            err(f"[{vid}] unknown start node {start}")
            continue
        (trucks if I.nodes[start]["type"] == "DP" else vans).append((vid, stops))

    def timeline(vid, stops, kind):
        """Check times along a route; returns (departure, return) or None."""
        ok = True
        for i in range(len(stops) - 1):
            u, v = stops[i]["node"], stops[i + 1]["node"]
            if v not in I.nodes:
                err(f"[{vid}] unknown node {v}")
                return None
            if stops[i + 1]["arrival"] < stops[i]["departure"] + I.tt(u, v):
                err(f"[{vid}] arrives at {v} at {stops[i + 1]['arrival']}, earlier than possible")
                ok = False
            if i + 1 < len(stops) - 1:
                begin = max(stops[i + 1]["arrival"], I.open(v))
                end = begin + I.service(v)
                if stops[i + 1]["departure"] < end:
                    err(f"[{vid}] leaves {v} at {stops[i + 1]['departure']} before service ends ({end})")
                    ok = False
                if end > I.close(v):
                    err(f"[{vid}] service at {v} ends at {end} > close {I.close(v)}")
                    ok = False
        last = stops[-1]
        if last["arrival"] > I.close(last["node"]):
            err(f"[{vid}] returns to {last['node']} at {last['arrival']} > close {I.close(last['node'])}")
            ok = False
        if stops[0]["departure"] < I.open(stops[0]["node"]):
            err(f"[{vid}] leaves {stops[0]['node']} before it opens")
            ok = False
        dmax = I.dmax_t if kind == "truck" else I.dmax_v
        if last["arrival"] - stops[0]["departure"] > dmax:
            err(f"[{vid}] shift {last['arrival'] - stops[0]['departure']} min > {dmax}")
            ok = False
        return (stops[0]["departure"], last["arrival"]) if ok else None

    cost = 0
    truck_visits = []
    for vid, stops in trucks:
        nodes = [s["node"] for s in stops]
        if nodes[-1] != I.dp:
            err(f"[{vid}] truck does not return to the DP")
        mids = nodes[1:-1]
        if any(I.nodes[n]["type"] != "DS" for n in mids):
            err(f"[{vid}] truck visits a node that is not a hub")
        if len(set(mids)) != len(mids):
            err(f"[{vid}] truck visits a hub twice in one trip")
        timeline(vid, stops, "truck")
        truck_visits.append([(s["node"], s["departure"]) for s in stops[1:-1]])
        cost += I.fixed_t + I.km_t * I.path_km(nodes)

    served, needs, per_hub = {}, [], {h: 0 for h in I.hubs}
    for vid, stops in vans:
        nodes = [s["node"] for s in stops]
        hub = nodes[0]
        if I.nodes[hub]["type"] != "DS" or nodes[-1] != hub:
            err(f"[{vid}] van must start and end at the same hub")
            continue
        per_hub[hub] += 1
        custs = nodes[1:-1]
        if any(I.nodes[c]["type"] != "PL" for c in custs):
            err(f"[{vid}] van visits a node that is not a customer")
        load = sum(I.demand(c) for c in custs)
        if load > I.cap_v:
            err(f"[{vid}] departure load {load} > {I.cap_v}")
        for c in custs:
            served[c] = served.get(c, 0) + 1
            load += I.pickup(c) - I.demand(c)
            if load > I.cap_v:
                err(f"[{vid}] load {load} after {c} > {I.cap_v}")
        timeline(vid, stops, "van")
        needs.append((hub, stops[0]["departure"], sum(I.demand(c) for c in custs)))
        cost += I.fixed_v + I.km_v * I.path_km(nodes)

    for c in I.customers:
        if served.get(c, 0) != 1:
            err(f"customer {c} served {served.get(c, 0)} times")

    ok, q = allocate_stock(I.cap_t, truck_visits, needs)
    if not ok:
        err("hub stock: no allocation of truck loads (<= capacity) can supply every van before it leaves")

    # Physical vehicles (multi-trip extension): trips sharing a base id, e.g. Delivery_Van_3
    # and Delivery_Van_3_T2, belong to one vehicle.
    def physical(routes, kind):
        groups = {}
        for vid, stops in routes:
            groups.setdefault(re.sub(r"_T\d+$", "", vid), []).append(stops)
        gap = I.service(I.dp) if kind == "truck" else 0
        dmax = I.dmax_t if kind == "truck" else I.dmax_v
        for base, trips in groups.items():
            trips.sort(key=lambda s: s[0]["departure"])
            if kind == "van" and len({s[0]["node"] for s in trips}) > 1:
                err(f"[{base}] van works from several hubs (carrier binding)")
            for a, b in zip(trips, trips[1:]):
                if b[0]["departure"] < a[-1]["arrival"] + gap:
                    err(f"[{base}] next trip leaves at {b[0]['departure']} before the previous one "
                        f"is back and reloaded ({a[-1]['arrival']} + {gap})")
            if trips[-1][-1]["arrival"] - trips[0][0]["departure"] > dmax:
                err(f"[{base}] working day {trips[-1][-1]['arrival'] - trips[0][0]['departure']} min > {dmax}")
        return len(groups)

    n_trucks, n_vans = physical(trucks, "truck"), physical(vans, "van")
    if I.nmax_t is not None and n_trucks > I.nmax_t:
        err(f"{n_trucks} trucks > {I.nmax_t} available")
    if I.nmax_v is not None and n_vans > I.nmax_v:
        err(f"{n_vans} vans > {I.nmax_v} available")

    if group1 and len(I.hubs) > 1:
        t = len(vans)
        for h, n in per_hub.items():
            if n < 2:
                err(f"Group 1: hub {h} dispatches {n} van(s) < 2")
            if 2 * n > t:
                err(f"Group 1 (model): hub {h} dispatches {n}/{t} vans > half")
            if n > math.ceil(t / 2):
                err(f"Group 1 (evaluator): hub {h} dispatches {n}/{t} vans > ceil(t/2)")

    claimed = sol.get("claimed_cost_cents")
    if claimed is None and "claimed_cost" in sol:          # legacy files give euros
        claimed = round(float(sol["claimed_cost"]) * 100)
    if claimed != cost:
        err(f"claimed cost {claimed} != recomputed {cost}")
    loads = [sum(x.values()) for x in q] if ok else []
    return errs, cost, per_hub, loads


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--instance", "-i", required=True)
    ap.add_argument("--solution", "-s", required=True)
    ap.add_argument("--no-group1", action="store_true")
    args = ap.parse_args()
    inst = load_instance(args.instance)
    with open(args.solution, encoding="utf-8") as f:
        sol = json.load(f)

    errs, cost, per_hub, loads = check(inst, sol, group1=not args.no_group1)
    print(f"Model check ({inst.name}): {'OK' if not errs else f'{len(errs)} violation(s)'}")
    print(f"  cost {cost / 100:.2f} EUR, vans per hub {per_hub}, truck loads {loads}")
    for e in errs:
        print("  -", e)

    with open(args.instance, encoding="utf-8") as f:
        raw = json.load(f)
    res = evaluate_solution(raw, sol)
    print(f"Course validator: {res['status']}, {len(res['violations'])} violation(s)")
    for v in res["violations"]:
        print("  -", v)
    sys.exit(0 if not errs and res["isValid"] else 1)


if __name__ == "__main__":
    main()
