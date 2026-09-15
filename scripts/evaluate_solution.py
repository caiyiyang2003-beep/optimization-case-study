import json
import math
import argparse
import sys
from pathlib import Path

AUTHORIZED_TEAMS = {
    "team1": ["sk-team1-8f3a9e2c4b"],
    "team2": ["sk-team2-7d1e5c3a8f", "sk-team2-5c7d1e9a3f"],
    "team3": ["sk-team3-4b9a2e6f1c", "sk-team3-2b4e8a1d7c"],
    "team4": ["sk-team4-3c8f1a5e9d", "sk-team4-9a3c5f7e1b"],
    "team5": ["sk-team5-1a7c5e9d3f", "sk-team5-4d8e2a6f0c"]
}

def format_minutes(minutes):
    if minutes is None:
        return "--h--"
    m_int = round(minutes)
    h = m_int // 60
    m = m_int % 60
    return f"{h:02d}h{m:02d}"

def evaluate_solution(instance, solution, require_auth=False):
    violations = []
    def add_v(code, msg):
        violations.append(f"[{code}] {msg}")

    if not isinstance(instance, dict):
        return {"isValid": False, "status": "REJECTED", "violations": ["[BAD_INSTANCE] Invalid instance"]}
    if not isinstance(solution, dict):
        return {"isValid": False, "status": "REJECTED", "violations": ["[BAD_JSON] Invalid solution JSON"]}

    nodes = instance.get("nodes", [])
    nodes_map = {n["id"]: n for n in nodes}
    durations = instance.get("duration_matrix_min", {})
    fleet = instance.get("fleet", {})

    # Auth check
    team_name = (solution.get("team_name") or "").lower().strip()
    token = solution.get("api_key") or solution.get("token")
    if require_auth:
        if not team_name:
            add_v("AUTH_ERROR", "Missing 'team_name' field.")
        elif team_name not in AUTHORIZED_TEAMS:
            add_v("AUTH_ERROR", f"Unknown team '{team_name}'.")
        elif token:
            clean_tok = token.replace("Bearer ", "").strip()
            if clean_tok not in AUTHORIZED_TEAMS[team_name]:
                add_v("AUTH_ERROR", f"Token does not match team '{team_name}'.")

    # Claimed cost in cents
    claimed_cost_cents = solution.get("claimed_cost_cents")
    if claimed_cost_cents is None:
        if "claimed_cost" in solution:
            claimed_cost_cents = round(float(solution["claimed_cost"]) * 100)
        else:
            add_v("BAD_JSON", "Missing 'claimed_cost_cents' (or 'claimed_cost') field.")

    # Routes
    routes_list = solution.get("routes")
    if not isinstance(routes_list, list):
        e1 = solution.get("echelon_1_tours", [])
        e2 = solution.get("echelon_2_tours", [])
        if isinstance(e1, list) and isinstance(e2, list) and (e1 or e2):
            routes_list = e1 + e2

    if not isinstance(routes_list, list) or len(routes_list) == 0:
        add_v("BAD_JSON", "The 'routes' field must be a non-empty list.")
        return {"isValid": False, "status": "REJECTED", "violations": violations}

    def get_dist_km(u, v):
        nu, nv = nodes_map.get(u), nodes_map.get(v)
        if not nu or not nv:
            return 0
        return round(math.hypot(nu["x"] - nv["x"], nu["y"] - nv["y"]))

    def get_travel_time(u, v):
        if u in durations and v in durations[u]:
            return round(durations[u][v])
        return round(get_dist_km(u, v) * 1.33)

    parsed_routes = []
    for r_idx, r in enumerate(routes_list):
        route_id = r.get("vehicle_id", f"Route_{r_idx + 1}")
        stops = []
        if "stops" in r and isinstance(r["stops"], list):
            for s_idx, s in enumerate(r["stops"]):
                node_id = s if isinstance(s, str) else s.get("node")
                arr = s.get("arrival") if isinstance(s, dict) else None
                dep = s.get("departure") if isinstance(s, dict) else None
                stops.append({"node": node_id, "arrival": arr, "departure": dep})
        elif "route" in r and isinstance(r["route"], list):
            start_dep = r.get("departure_time")
            for s_idx, node_id in enumerate(r["route"]):
                stops.append({
                    "node": node_id,
                    "arrival": start_dep if s_idx == 0 else None,
                    "departure": start_dep if s_idx == 0 else None
                })
        else:
            add_v("BAD_JSON", f"[{route_id}] Route must define 'stops' or 'route'.")
            continue

        if len(stops) < 2:
            add_v("ROUTE_INVALID", f"[{route_id}] Route must contain at least 2 stops.")
            continue
        parsed_routes.append({"route_id": route_id, "raw": r, "stops": stops})

    e1_routes = []
    e2_routes = []
    for r in parsed_routes:
        start_node = nodes_map.get(r["stops"][0]["node"])
        if not start_node:
            add_v("ROUTE_INVALID", f"[{r['route_id']}] Unknown start stop '{r['stops'][0]['node']}'.")
            continue
        if start_node["type"] == "DP":
            e1_routes.append(r)
        elif start_node["type"] == "DS":
            e2_routes.append(r)
        else:
            add_v("ROUTE_INVALID", f"[{r['route_id']}] Cannot start from client '{start_node['id']}'.")

    e1_fixed = fleet.get("echelon_1", {}).get("fixed_cost_cents", round(fleet.get("echelon_1", {}).get("fixed_cost", 280.0) * 100))
    e1_km_cost = fleet.get("echelon_1", {}).get("cost_per_km_cents", round(fleet.get("echelon_1", {}).get("cost_per_km", 1.75) * 100))
    e1_cap = fleet.get("echelon_1", {}).get("capacity", 350)
    e1_max_dur = fleet.get("echelon_1", {}).get("max_duration", 600)

    e2_fixed = fleet.get("echelon_2", {}).get("fixed_cost_cents", round(fleet.get("echelon_2", {}).get("fixed_cost", 85.0) * 100))
    e2_km_cost = fleet.get("echelon_2", {}).get("cost_per_km_cents", round(fleet.get("echelon_2", {}).get("cost_per_km", 0.80) * 100))
    e2_cap = fleet.get("echelon_2", {}).get("capacity", 65)
    e2_max_dur = fleet.get("echelon_2", {}).get("max_duration", 480)

    total_calc_cost_cents = 0
    total_dist_km = 0
    ds_supply_times = {}

    # Tier 1
    for r in e1_routes:
        route_id = r["route_id"]
        stops = r["stops"]
        final_node = stops[-1]["node"]
        if nodes_map.get(final_node, {}).get("type") != "DP":
            add_v("ROUTE_INVALID", f"[{route_id}] Heavy truck must return to DP. Ended at '{final_node}'.")

        total_calc_cost_cents += e1_fixed
        for i in range(1, len(stops) - 1):
            if nodes_map.get(stops[i]["node"], {}).get("type") == "PL":
                add_v("ROUTE_INVALID", f"[{route_id}] Heavy truck cannot visit customer '{stops[i]['node']}' directly.")

        dep0 = stops[0]["departure"] if stops[0]["departure"] is not None else nodes_map[stops[0]["node"]].get("tw_open", 360)
        start_shift = dep0
        curr_dep = dep0
        tour_dist = 0

        for i in range(len(stops) - 1):
            u = stops[i]["node"]
            v = stops[i+1]["node"]
            nv = nodes_map.get(v)
            if not nv:
                add_v("ROUTE_INVALID", f"[{route_id}] Unknown stop '{v}'.")
                continue
            tt = get_travel_time(u, v)
            dist = get_dist_km(u, v)
            tour_dist += dist

            min_arr = curr_dep + tt
            exp_arr = stops[i+1]["arrival"]
            actual_arr = min_arr
            if exp_arr is not None:
                if exp_arr < min_arr:
                    add_v("TIMELINE_ERROR", f"[{route_id}] Early arrival at '{v}': {format_minutes(exp_arr)} < min {format_minutes(min_arr)}.")
                actual_arr = exp_arr

            if actual_arr > nv.get("tw_close", 1440):
                add_v("TW_VIOLATION", f"[{route_id}] Late arrival at '{v}': {format_minutes(actual_arr)} > close {format_minutes(nv['tw_close'])}.")

            serv_start = max(actual_arr, nv.get("tw_open", 0))
            serv_time = nv.get("service_time", 0)
            min_dep = serv_start + serv_time

            exp_dep = stops[i+1]["departure"]
            actual_dep = min_dep
            if i + 1 < len(stops) - 1:
                if exp_dep is not None:
                    if exp_dep < min_dep:
                        add_v("TIMELINE_ERROR", f"[{route_id}] Departure from '{v}' {format_minutes(exp_dep)} < end of service {format_minutes(min_dep)}.")
                    actual_dep = exp_dep
            else:
                actual_dep = actual_arr

            if nv.get("type") == "DS":
                ds_supply_times[v] = min(ds_supply_times.get(v, float("inf")), actual_dep)
            curr_dep = actual_dep

        dur = curr_dep - start_shift
        if dur > e1_max_dur:
            add_v("DURATION_EXCEEDED", f"[{route_id}] Heavy truck shift {dur}m > max {e1_max_dur}m.")
        total_dist_km += tour_dist
        total_calc_cost_cents += tour_dist * e1_km_cost

    # Tier 2
    served_customers = {}
    all_customers = {n["id"] for n in nodes if n["type"] == "PL"}
    ds_demands = {}

    for r in e2_routes:
        route_id = r["route_id"]
        stops = r["stops"]
        origin_ds = stops[0]["node"]
        if stops[-1]["node"] != origin_ds:
            add_v("ROUTE_INVALID", f"[{route_id}] Van must return to '{origin_ds}'.")

        total_calc_cost_cents += e2_fixed
        cust_stops = [nodes_map[s["node"]] for s in stops[1:-1] if nodes_map.get(s["node"], {}).get("type") == "PL"]
        total_del = sum(c.get("demand", 0) for c in cust_stops)
        ds_demands[origin_ds] = ds_demands.get(origin_ds, 0) + total_del

        # 3a. Initial load check
        curr_load = total_del
        if curr_load > e2_cap:
            add_v("CAPACITY_OVERLOAD", f"[{route_id}] Departure load ({curr_load} pkgs) > van capacity ({e2_cap} pkgs).")

        dep0 = stops[0]["departure"] if stops[0]["departure"] is not None else 480
        sup_time = ds_supply_times.get(origin_ds)
        if sup_time is not None and dep0 < sup_time:
            add_v("SYNCHRONIZATION_VIOLATION", f"[{route_id}] Van departs '{origin_ds}' at {format_minutes(dep0)} BEFORE truck delivery at {format_minutes(sup_time)}.")

        start_shift = dep0
        curr_dep = dep0
        tour_dist = 0

        for i in range(len(stops) - 1):
            u = stops[i]["node"]
            v = stops[i+1]["node"]
            nv = nodes_map.get(v)
            if not nv:
                add_v("ROUTE_INVALID", f"[{route_id}] Unknown stop '{v}'.")
                continue
            tt = get_travel_time(u, v)
            dist = get_dist_km(u, v)
            tour_dist += dist

            min_arr = curr_dep + tt
            exp_arr = stops[i+1]["arrival"]
            actual_arr = min_arr
            if exp_arr is not None:
                if exp_arr < min_arr:
                    add_v("TIMELINE_ERROR", f"[{route_id}] Early arrival at '{v}': {format_minutes(exp_arr)} < min {format_minutes(min_arr)}.")
                actual_arr = exp_arr

            if actual_arr > nv.get("tw_close", 1440):
                add_v("TW_VIOLATION", f"[{route_id}] Late arrival at customer '{v}': {format_minutes(actual_arr)} > close {format_minutes(nv['tw_close'])}.")

            serv_start = max(actual_arr, nv.get("tw_open", 0))
            serv_time = nv.get("service_time", 0)
            min_dep = serv_start + serv_time

            exp_dep = stops[i+1]["departure"]
            actual_dep = min_dep
            if i + 1 < len(stops) - 1:
                if exp_dep is not None:
                    if exp_dep < min_dep:
                        add_v("TIMELINE_ERROR", f"[{route_id}] Departure from '{v}' {format_minutes(exp_dep)} < end of service {format_minutes(min_dep)}.")
                    actual_dep = exp_dep

                # 3b. Dynamic load update
                if nv.get("type") == "PL":
                    served_customers[v] = served_customers.get(v, 0) + 1
                    curr_load = curr_load - nv.get("demand", 0) + nv.get("pickup", 0)
                    if curr_load > e2_cap:
                        add_v("CAPACITY_OVERLOAD", f"[{route_id}] Van overloaded at '{v}': current load {curr_load} > capacity {e2_cap}.")
            else:
                actual_dep = actual_arr

            curr_dep = actual_dep

        dur = curr_dep - start_shift
        if dur > e2_max_dur:
            add_v("DURATION_EXCEEDED", f"[{route_id}] Van shift {dur}m > max {e2_max_dur}m.")
        total_dist_km += tour_dist
        total_calc_cost_cents += tour_dist * e2_km_cost

    # Customer coverage
    unserved = [c for c in all_customers if c not in served_customers]
    if unserved:
        add_v("UNSERVED_CUSTOMERS", f"Unserved customers ({len(unserved)}): {', '.join(unserved)}.")

    for c, cnt in served_customers.items():
        if cnt > 1:
            add_v("DUPLICATE_VISIT", f"Customer '{c}' visited {cnt} times.")

    # Cost check
    if claimed_cost_cents is not None and claimed_cost_cents != total_calc_cost_cents:
        add_v("COST_MISMATCH", f"Claimed cost ({claimed_cost_cents} cts) != verified cost ({total_calc_cost_cents} cts). Delta = {abs(claimed_cost_cents - total_calc_cost_cents)} cts.")

    is_valid = len(violations) == 0
    return {
        "isValid": is_valid,
        "status": "OK" if is_valid else "REJECTED",
        "instanceId": solution.get("instance_id", instance.get("metadata", {}).get("name")),
        "claimedCostCents": claimed_cost_cents,
        "calculatedCostCents": total_calc_cost_cents,
        "calculatedCostEur": total_calc_cost_cents / 100.0,
        "totalDistanceKm": total_dist_km,
        "violations": violations
    }

def main():
    parser = argparse.ArgumentParser(description="Evaluate Logistics Solution Offline")
    parser.add_argument("--instance", "-i", required=True, help="Path to instance JSON")
    parser.add_argument("--solution", "-s", required=True, help="Path to solution JSON")
    args = parser.parse_args()

    with open(args.instance, "r", encoding="utf-8") as f:
        instance = json.load(f)
    with open(args.solution, "r", encoding="utf-8") as f:
        solution = json.load(f)

    res = evaluate_solution(instance, solution)
    print("\n" + "="*50)
    print(f"EVALUATION RESULT: {res['status']}")
    print(f"Verified Cost: {res.get('calculatedCostCents')} cts ({res.get('calculatedCostEur', 0):.2f} €)")
    print(f"Total Distance: {res.get('totalDistanceKm')} km")
    print("="*50)
    if not res["isValid"]:
        print(f"\nDetected {len(res['violations'])} violation(s):")
        for v in res["violations"]:
            print(f" - {v}")
        sys.exit(1)
    else:
        print("\nAll operational rules and constraints satisfied 100%!")
        sys.exit(0)

if __name__ == "__main__":
    main()
