"""Make cleaned copies of the 4 broken instances (05, 07, 08, 09) in data/cleaned/.

The original files are not touched. Each fix is the smallest change that makes the instance
usable, and every fix is written into the file itself (metadata -> cleaning_log), so anyone who
opens the cleaned instance can see what we changed and why. These are OUR assumptions, not
corrections confirmed by the instructor.
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..", "data", "instances")
DST = os.path.join(HERE, "..", "data", "cleaned")

# (instance, node, field, old value, new value, reason)
FIXES = [
    ("05_suburban_52pl", "PL_1", "tw_close", 450, 480,
     "Window 420-450 cannot be met: the earliest a van can arrive is 465 (truck leaves the DP at 360, "
     "reaches DS_1 at 421, unloads until 446, van drives 19 min). Closing time moved to 480 (08:00), "
     "the next half hour, since every window in this instance is on the half-hour grid."),
    ("07_regional_58pl", "PL_14", "demand", 74, 65,
     "Order of 74 exceeds the van capacity 65 and Group 1 forbids splitting an order. Capped at 65, "
     "the largest order one van can carry; the other customers order 18-32. The 9 missing packages "
     "would have to be delivered another day."),
    ("08_legacy_crm_60pl", "PL_18", "demand", 10000000, 20,
     "Order of 10 000 000 is a data-entry error (the other 59 customers order 15-26). Replaced by the "
     "median order of the other customers, 20."),
    ("09_urban_64pl", "PL_22", "demand", "23A", 23,
     'Invalid JSON: "demand": 23A. Read as 23; with 23 the demand total equals '
     "metadata.total_delivery_demand (1440), which confirms it."),
]


def clean(name, fixes):
    with open(os.path.join(SRC, f"instance_{name}.json"), encoding="utf-8") as f:
        text = f.read()
    for _, node, field, old, new, _ in fixes:
        if isinstance(old, str):                 # not a number: the file cannot be parsed as it is
            text = text.replace(f'"{field}": {old}', f'"{field}": {new}')
    data = json.loads(text)

    nodes = {n["id"]: n for n in data["nodes"]}
    log = []
    for _, node, field, old, new, reason in fixes:
        nodes[node][field] = new
        log.append({"node": node, "field": field, "old": old, "new": new, "reason": reason})

    meta = data["metadata"]
    customers = [n for n in data["nodes"] if n["type"] == "PL"]
    meta["total_delivery_demand"] = sum(n["demand"] for n in customers)
    meta["total_pickup_demand"] = sum(n["pickup"] for n in customers)
    meta["benchmark_name"] = f"instance_{name}_clean"
    meta["cleaning_log"] = log

    os.makedirs(DST, exist_ok=True)
    out = os.path.join(DST, f"instance_{name}_clean.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return out


def main():
    for name in sorted({f[0] for f in FIXES}):
        out = clean(name, [f for f in FIXES if f[0] == name])
        print(f"{name}: written to {os.path.relpath(out, os.path.join(HERE, '..'))}")


if __name__ == "__main__":
    main()
