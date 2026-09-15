"""
Minimal example for loading and inspecting an instance.
For students to get started with Python 3.
"""

import json
import math
import sys
import os

def load_instance(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data

if __name__ == "__main__":
    try:
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

    path = os.path.join(os.path.dirname(__file__), "..", "data", "toy_2pl", "instance_toy_2pl.json")
    instance = load_instance(path)
    
    meta = instance["metadata"]
    print(f"=== {meta.get('title', 'Instance')} ===")
    print(f"Nodes: {meta['counts']['num_dp']} DP, {meta['counts']['num_ds']} DS, {meta['counts']['num_pl']} PL")
    print(f"Total delivery demand: {meta['total_delivery_demand']} packages")
    print(f"Total pickups: {meta['total_pickup_demand']} packages\n")
    
    # 1. Inspect first 3 nodes
    print("--- First 3 nodes ---")
    for node in instance["nodes"][:3]:
        tw_start = f"{node['tw_open'] // 60:02d}h{node['tw_open'] % 60:02d}"
        tw_end = f"{node['tw_close'] // 60:02d}h{node['tw_close'] % 60:02d}"
        print(f"[{node['type']}] {node['id']:<6} ({node['x']:>5.1f}, {node['y']:>5.1f}) | Deliv: {node['demand']:>2} | Pickup: {node['pickup']:>2} | Window: {tw_start} - {tw_end}")

    # 2. Inspect Euclidean Distance & Travel Time between DP_1 and DS_1
    print("\n--- Euclidean Distance & Travel Time between DP_1 and DS_1 ---")
    nodes_map = {n["id"]: n for n in instance["nodes"]}
    dp1, ds1 = nodes_map["DP_1"], nodes_map["DS_1"]
    dist_dp_ds = math.hypot(dp1["x"] - ds1["x"], dp1["y"] - ds1["y"])
    time_dp_ds = instance["duration_matrix_min"]["DP_1"]["DS_1"]
    time_ds_dp = instance["duration_matrix_min"]["DS_1"]["DP_1"]
    print(f"Euclidean distance : {dist_dp_ds:.2f} km")
    print(f"DP_1 -> DS_1 travel time : {time_dp_ds} min")
    print(f"DS_1 -> DP_1 travel time : {time_ds_dp} min  <-- asymmetric traffic!")

    # 3. Available fleet
    print("\n--- Available Fleet ---")
    for ech, info in instance["fleet"].items():
        vtype = info.get('type') or info.get('vehicle_type', 'Vehicle')
        print(f"{ech.upper()} : {vtype} | Capacity: {info['capacity']} | Fixed: €{info['fixed_cost']} | Cost/km: €{info['cost_per_km']} | Max Duration: {info['max_duration']} min")
