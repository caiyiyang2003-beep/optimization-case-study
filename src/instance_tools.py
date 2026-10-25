import json
import math
import os
from dataclasses import dataclass


class InstanceError(Exception):


@dataclass
class Instance:
    name: str
    nodes: dict          # id -> node dict from the JSON
    dp: str              # main depot id
    hubs: list           # DS ids
    customers: list      # PL ids
    durations: dict      # duration_matrix_min (may be incomplete)
    cap_t: int           # truck capacity (packages)
    cap_v: int           # van capacity
    fixed_t: int         # fixed cost per truck trip (cents)
    fixed_v: int         # fixed cost per van trip (cents)
    km_t: int            # truck cost per km (cents)
    km_v: int            # van cost per km (cents)
    dmax_t: int          # max truck shift (min)
    dmax_v: int          # max van shift (min)
    nmax_t: object       # max number of truck trips, None when the instance gives none
    nmax_v: object       # max number of van trips, None when the instance gives none

    # Geometry: Euclidean distance rounded to whole km, as in evaluate_solution.py
    def dist(self, u, v):
        a, b = self.nodes[u], self.nodes[v]
        return round(math.hypot(a["x"] - b["x"], a["y"] - b["y"]))

    # Travel time from the duration matrix; same fallback as the validator
    def tt(self, u, v):
        row = self.durations.get(u)
        if row is not None and v in row:
            return round(row[v])
        return round(self.dist(u, v) * 1.33)

    def open(self, u):
        return self.nodes[u]["tw_open"]

    def close(self, u):
        return self.nodes[u]["tw_close"]

    def service(self, u):
        return self.nodes[u]["service_time"]

    def demand(self, u):
        return self.nodes[u]["demand"]

    def pickup(self, u):
        return self.nodes[u]["pickup"]

    def path_km(self, path):
        return sum(self.dist(path[i], path[i + 1]) for i in range(len(path) - 1))


def _read_json(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        lines = e.doc.splitlines()
        bad = lines[e.lineno - 1].strip() if 0 < e.lineno <= len(lines) else ""
        raise InstanceError(f"invalid JSON at line {e.lineno}, column {e.colno}: {e.msg} -> '{bad}'") from None


def load_instance(path):
    data = _read_json(path)
    stem = os.path.splitext(os.path.basename(path))[0]
    try:
        raw_nodes, fleet = data["nodes"], data["fleet"]
        e1, e2 = fleet["echelon_1"], fleet["echelon_2"]
    except (KeyError, TypeError) as e:
        raise InstanceError(f"missing section {e}") from None

    nodes, problems = {}, []
    numeric = ("x", "y", "demand", "pickup", "tw_open", "tw_close", "service_time")
    for n in raw_nodes:
        nid = n.get("id")
        if nid in nodes:
            problems.append(f"duplicate node id {nid}")
        for k in numeric:
            v = n.get(k, 0 if k in ("demand", "pickup", "service_time") else None)
            if isinstance(v, bool) or not isinstance(v, (int, float)):
                problems.append(f"{nid}: field '{k}' is not a number ({v!r})")
        nodes[nid] = dict(n)
        for k in ("demand", "pickup", "service_time"):
            nodes[nid].setdefault(k, 0)
    if problems:
        raise InstanceError("; ".join(problems))

    def cents(e, key, eur, default):
        return e.get(key, round(e.get(eur, default) * 100))

    by_type = lambda t: [i for i, n in nodes.items() if n.get("type") == t]
    dps = by_type("DP")
    inst = Instance(
        name=data.get("metadata", {}).get("name") or data.get("metadata", {}).get("benchmark_name") or stem,
        nodes=nodes, dp=dps[0] if dps else None, hubs=by_type("DS"), customers=by_type("PL"),
        durations=data.get("duration_matrix_min", {}),
        cap_t=e1.get("capacity", 350), cap_v=e2.get("capacity", 65),
        fixed_t=cents(e1, "fixed_cost_cents", "fixed_cost", 280.0),
        fixed_v=cents(e2, "fixed_cost_cents", "fixed_cost", 85.0),
        km_t=cents(e1, "cost_per_km_cents", "cost_per_km", 1.75),
        km_v=cents(e2, "cost_per_km_cents", "cost_per_km", 0.80),
        dmax_t=e1.get("max_duration", 600), dmax_v=e2.get("max_duration", 480),
        nmax_t=e1.get("max_available"), nmax_v=e2.get("max_available"),
    )

    # Structural and physical checks: an instance failing them has no feasible solution.
    if len(dps) != 1:
        problems.append(f"expected exactly one DP, found {len(dps)}")
    if not inst.hubs:
        problems.append("no DS hub")
    for c in inst.customers:
        n = nodes[c]
        if n["demand"] < 0 or n["pickup"] < 0:
            problems.append(f"{c}: negative demand or pickup")
        if n["demand"] > inst.cap_v or n["pickup"] > inst.cap_v:
            problems.append(f"{c}: order of {n['demand']} delivered / {n['pickup']} collected exceeds the "
                            f"van capacity {inst.cap_v}, and orders cannot be split")
        if n["tw_open"] + n["service_time"] > n["tw_close"]:
            problems.append(f"{c}: time window [{n['tw_open']}, {n['tw_close']}] shorter than its service time")
    if problems:
        raise InstanceError("; ".join(problems))

    return inst


# bounds
def simple_lower_bound(inst, min_vans_per_hub=0):
    D = sum(inst.demand(c) for c in inst.customers)
    k_t = max(1, math.ceil(D / inst.cap_t))
    k_v = max(math.ceil(D / inst.cap_v), len(inst.hubs) * min_vans_per_hub)
    origins = inst.hubs + inst.customers
    van_km = sum(min(inst.dist(i, c) for i in origins if i != c) for c in inst.customers)
    truck_km = k_t * 2 * min(inst.dist(inst.dp, h) for h in inst.hubs)
    return k_t * inst.fixed_t + k_v * inst.fixed_v + van_km * inst.km_v + truck_km * inst.km_t
