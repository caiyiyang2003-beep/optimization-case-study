"""
2D Visualizer for distribution network instances (Main Warehouses, Secondary Hubs, Customer Delivery Points).
Displays node map, coordinates, time windows, and package demands.
"""
from pathlib import Path
import json
import argparse
import os
import matplotlib.pyplot as plt

def plot_instance(json_path, output_image_path=None, show=False):
    # Project root: optimization-case-study/
    project_root = Path(__file__).resolve().parent.parent

    # Convert the input path into a Path object
    json_path = Path(json_path)

    # If a relative path is given, resolve it from the project root
    if not json_path.is_absolute():
        json_path = project_root / json_path

    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    nodes = data["nodes"]
    meta = data.get("metadata", {})

    # Split nodes by type
    dps = [n for n in nodes if n["type"] == "DP"]
    dss = [n for n in nodes if n["type"] == "DS"]
    pls = [n for n in nodes if n["type"] == "PL"]

    # Modern plot styling
    plt.figure(figsize=(13, 9), facecolor="#0F1320")
    ax = plt.subplot(111)
    ax.set_facecolor("#161B2E")

    # Subtle grid
    ax.grid(True, linestyle="--", alpha=0.25, color="#5B647F")
    ax.spines['bottom'].set_color('#2A3150')
    ax.spines['top'].set_color('#2A3150')
    ax.spines['right'].set_color('#2A3150')
    ax.spines['left'].set_color('#2A3150')
    ax.tick_params(colors='#8C95B0', labelsize=10)

    # 1. Customer Points (PL)
    pls_with_pickup = [n for n in pls if n["pickup"] > 0]
    pls_no_pickup = [n for n in pls if n["pickup"] == 0]

    if pls_no_pickup:
        ax.scatter(
            [n["x"] for n in pls_no_pickup], 
            [n["y"] for n in pls_no_pickup],
            s=[max(50, n["demand"] * 6.5) for n in pls_no_pickup],
            c="#EAB308", 
            alpha=0.85, 
            edgecolors="#FFFFFF", 
            linewidths=1.2,
            label=f"Customers PL (Delivery only : {len(pls_no_pickup)})",
            zorder=3
        )

    if pls_with_pickup:
        ax.scatter(
            [n["x"] for n in pls_with_pickup], 
            [n["y"] for n in pls_with_pickup],
            s=[max(60, n["demand"] * 7.5) for n in pls_with_pickup],
            c="#F97316", 
            alpha=0.95, 
            edgecolors="#22C55E", 
            linewidths=2.2,
            label=f"Customers PL (Delivery + Pickup : {len(pls_with_pickup)})",
            zorder=4
        )

    # Annotations for PL customers
    for n in pls:
        tw_str = f"{n['tw_open']//60:02d}h-{n['tw_close']//60:02d}h"
        info_str = f"{n['id']}\nL:{n['demand']}" + (f" | R:{n['pickup']}" if n['pickup'] > 0 else "")
        ax.annotate(
            f"{info_str}\n[{tw_str}]",
            (n["x"], n["y"]),
            textcoords="offset points",
            xytext=(0, 10),
            ha='center',
            fontsize=7.5,
            color="#E7EAF3",
            fontfamily="monospace",
            bbox=dict(boxstyle="round,pad=0.2", fc="#0B0E18", ec="#2A3150", alpha=0.85),
            zorder=6
        )

    # 2. Secondary Hubs (DS) - Cyan squares with cross
    for ds in dss:
        ax.scatter(
            ds["x"], ds["y"],
            s=280,
            marker="s",
            c="#14B8A6",
            edgecolors="#FFFFFF",
            linewidths=2,
            zorder=5
        )
        ax.scatter(
            ds["x"], ds["y"],
            s=100,
            marker="+",
            c="#FFFFFF",
            linewidths=2.5,
            zorder=6
        )
        tw_ds = f"{ds['tw_open']//60:02d}h-{ds['tw_close']//60:02d}h"
        ax.annotate(
            f"★ {ds['id']} (Secondary Hub)\n[{tw_ds}]",
            (ds["x"], ds["y"]),
            textcoords="offset points",
            xytext=(0, -22),
            ha='center',
            fontsize=9.5,
            fontweight="bold",
            color="#14B8A6",
            fontfamily="monospace",
            bbox=dict(boxstyle="round,pad=0.3", fc="#0B0E18", ec="#14B8A6", alpha=0.95),
            zorder=7
        )

    # 3. Main Warehouses (DP) - Purple square with white cross
    for dp in dps:
        ax.scatter(
            dp["x"], dp["y"],
            s=450,
            marker="s",
            c="#8B5CF6",
            edgecolors="#FFFFFF",
            linewidths=2.5,
            zorder=5
        )
        ax.scatter(
            dp["x"], dp["y"],
            s=180,
            marker="P",
            c="#FFFFFF",
            linewidths=2.5,
            zorder=6
        )
        tw_dp = f"{dp['tw_open']//60:02d}h-{dp['tw_close']//60:02d}h"
        ax.annotate(
            f"⊞ {dp['id']} (MAIN WAREHOUSE)\n[{tw_dp}]",
            (dp["x"], dp["y"]),
            textcoords="offset points",
            xytext=(0, 22),
            ha='center',
            fontsize=10.5,
            fontweight="bold",
            color="#A78BFA",
            fontfamily="monospace",
            bbox=dict(boxstyle="round,pad=0.4", fc="#0B0E18", ec="#8B5CF6", alpha=0.95),
            zorder=7
        )

    # Dummy elements for legend
    ax.scatter([], [], s=120, marker="s", c="#8B5CF6", edgecolors="#FFF", label=f"Main Warehouse DP ({len(dps)})")
    ax.scatter([], [], s=90, marker="s", c="#14B8A6", edgecolors="#FFF", label=f"Secondary Hub DS ({len(dss)})")

    # Titles & Legends
    title_text = f"Distribution Network Topology : {meta.get('title', 'Instance')}"
    subtitle_text = f"Nodes : {len(dps)} DP | {len(dss)} DS | {len(pls)} PL  —  Delivery Demand : {meta.get('total_delivery_demand', '?')} units  —  Pickups : {meta.get('total_pickup_demand', '?')} units"
    
    plt.title(f"{title_text}\n{subtitle_text}", fontsize=13, fontweight="bold", color="#E7EAF3", pad=15, fontfamily="sans-serif")
    plt.xlabel("X Coordinates (km)", fontsize=11, color="#8C95B0", labelpad=8)
    plt.ylabel("Y Coordinates (km)", fontsize=11, color="#8C95B0", labelpad=8)

    leg = ax.legend(loc="upper right", facecolor="#0B0E18", edgecolor="#2A3150", fontsize=9.5)
    for text in leg.get_texts():
        text.set_color("#E7EAF3")

    plt.tight_layout()

    # Save image
    if not output_image_path:
        base_name = os.path.splitext(os.path.basename(json_path))[0]
        output_image_path = os.path.join(os.path.dirname(json_path), f"plot_{base_name}.png")

    plt.savefig(output_image_path, dpi=200, bbox_inches="tight")
    print(f"[OK] Node map saved to: {output_image_path}")

    if show:
        plt.show()

    plt.close()
    return output_image_path

if __name__ == "__main__":
    import sys
    try:
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
    
    parser = argparse.ArgumentParser(description="Render 2D node map for a distribution network instance")
    parser.add_argument(
        "instance",
        type=str,
        nargs="?",
        default="data/toy_2pl/instance_toy_2pl.json",
        help="Path to instance JSON file"
    )
    parser.add_argument("--output", type=str, default=None, help="Save path for PNG image")
    parser.add_argument("--show", action="store_true", help="Open interactive matplotlib window")

    args = parser.parse_args()
    plot_instance(args.instance, args.output, args.show)
