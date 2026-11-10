# Two-echelon delivery – Group 1 (team1)

Notes for the group. This file is not part of what we hand in.

Lab: https://albanderrien.fr/cours/most/lab/ – Group 1 rules: https://albanderrien.fr/cours/most/groupes/groupe-1/

The mathematical model lives in the "maths model" tab of our Google Doc; [math_model.md](math_model.md)
is a local copy. If they disagree, the Doc wins.

## How to run

Python 3 only, no packages needed (`scripts/plot_instance.py` needs matplotlib for the plots).

```bash
# solve all 10 instances, write the solutions to solutions/ and the table to solutions/summary.md
python3 src/run_all.py

# solve one instance: set INSTANCE at the top of src/greedy_nn.py, then run the file
# (or press Run in your editor); the solution is checked with the validator automatically
python3 src/greedy_nn.py

# check one solution with the course validator
python3 scripts/evaluate_solution.py --instance data/instances/instance_03_medium_35pl.json --solution solutions/03_medium_35pl_greedy.json
```

`scripts/evaluate_solution.py` and `data/instances/` are the current versions from the course website
(downloaded 2026-11-03): like the online evaluator, the validator checks the team name, the API key and
the Group 1 rules.

**Cost method "version 2" (official).** A route costs its fixed cost (280 € truck, 85 € van) plus its
driving time from `duration_matrix_min`, at 1.30 €/min for a truck and 0.60 €/min for a van. Service and
waiting time are not charged. A solution must contain `"version": "2"` at its root, otherwise the
validator falls back to the legacy version 1 (Euclidean km × €/km). Our solutions include it.

## Files

| File | Content |
|---|---|
| `src/instance_tools.py` | Reads an instance, rejects broken data, travel times (rounded as the validator does), a simple lower bound |
| `src/greedy_nn.py` | The solver, see "Algorithm" below |
| `src/run_all.py` | Solves every instance, checks it with the course validator, writes the summary table |
| `src/clean_instances.py` | Writes cleaned copies of the broken instances 05, 07, 08, 09 to `data/cleaned/` |
| `src/ils.py` | Iterated local search (work in progress, not handed in this week) |
| `src/tune_vnd.py` | Experiment used to choose the ILS neighbourhoods, results in `solutions/vnd_comparison.md` |
| `scripts/` | Scripts from the course: `evaluate_solution.py` (validator), `load_data.py`, `plot_instance.py` |
| `data/instances/` | The 10 instances from the course website |
| `data/cleaned/` | Our cleaned versions of 05, 07, 08, 09 (each file lists its changes in `metadata.cleaning_log`) |
| `data/medium_35pl/` etc. | The first 3 instances, the legacy solution and its classified violations |
| `solutions/*_greedy.json` | Our current solutions (team name and API key already filled in) |

Note: `scripts/validator_server.py` actually contains the HTML of the course web page, not Python code, so it cannot be run.

## Algorithm (`greedy_nn.py`)

Everything is read from the JSON file; nothing is tuned for a particular instance.

"Closest" always means the shortest driving time in the duration matrix, the quantity the cost uses.

1. **Vans: nearest neighbour.** A van leaves a hub and keeps driving to the closest customer it can
   still serve (capacity including pickups, time window, shift length); when none fits it returns
   and the next van starts. A van only has to arrive before the window closes; service may end later
   (instructor's reply).
2. **Group 1 repair.** Every hub sends at least 2 van routes and no hub sends more than ceil(t/2) of
   the t van routes (instructor's reply: 6 out of 11 is allowed).
   While a rule is broken, apply the cheapest move that reduces the violation:
   take one customer out of a route and serve it with its own van, from any hub.
3. **Trucks: nearest neighbour too.** Demand above a full truckload goes first in direct trips.
   For the remaining demand, a truck leaves the DP and keeps driving to the closest hub whose
   remaining demand still fits and whose time window can still be met.
4. **Stock check (model constraints 29–33).** Hub by hub: each time a van leaves, the stock unloaded
   so far must cover the goods taken by all vans gone so far. A hub that runs short gets its own
   truck trip and the trucks are planned again.
5. **One vehicle per route.** `max_available` is only indicative (instructor's reply: exceeding it is
   not rejected) and the fixed cost is paid per route, so every route gets its own vehicle
   (`Heavy_Truck_1`, `Delivery_Van_1`, ...) and the code does not check the fleet size.

When an instance cannot be solved, the code says why instead of crashing.

## Current results (cost method version 2)

| Instance | Result | Cost (€) |
|---|---|---|
| 01 toy | feasible | 494.00 |
| 02 small | feasible | 1029.00 |
| 03 medium | feasible | 3294.00 |
| 04 district | feasible | 3720.60 |
| 05 suburban | infeasible: PL_1's time window cannot be met even by a dedicated van | – |
| 06 micro hubs | feasible | 5363.40 |
| 07 regional | infeasible: PL_14 orders 74 > van capacity 65, and Group 1 forbids splitting orders | – |
| 08 legacy CRM | broken data: PL_18 orders 10 000 000 | – |
| 09 urban | broken data: invalid JSON (`"demand": 23A`) | – |
| 10 metropolis | feasible | 8073.50 |

All 6 feasible solutions pass the course validator with 0 violations. Relaxing the time windows
made the nearest neighbour slightly worse on 03 and 10 (it is greedy, so looser rules can lead it to
other choices); the ILS below removes most of that. Lower bounds are in
`solutions/summary.md` and in the Bounds section of the Doc.

## Cleaned instances (our assumptions)

The evaluator accepts a custom instance JSON. We found no corrected versions of 05, 07, 08 and 09 on
the course website or elsewhere, so `python3 src/clean_instances.py` makes the smallest change that
makes each one usable. The originals are not changed. These are our assumptions, not fixes confirmed
by the instructor.

| Instance | Change | Why | Greedy (€) | ILS 60 s (€) |
|---|---|---|---|---|
| 05 suburban | PL_1 tw_close 450 → 480 | earliest possible arrival is 465; 480 = next half hour | 4632.80 | 4251.00 |
| 07 regional | PL_14 demand 74 → 65 | one van carries at most 65 and orders cannot be split (9 packages left out) | 5938.00 | 5834.40 |
| 08 legacy CRM | PL_18 demand 10 000 000 → 20 | data-entry error; 20 = median of the other 59 customers | 4772.80 | 4643.80 |
| 09 urban | PL_22 demand "23A" → 23 | with 23 the total matches `metadata.total_delivery_demand` (1440) | 5476.70 | 5043.00 |

All 8 solutions (`solutions/*_clean_greedy.json`, `*_clean_ils.json`) pass the validator when it is
run on the cleaned instance. Their `instance_id` ends in `_clean`.

## Validator vs our code

The local validator and the online evaluator check the same rules.

| Check | Validator | Our code |
|---|---|---|
| Group 1 rules | at least 2 van routes per hub, at most ceil(t/2) | same |
| Time windows | arrival ≤ tw_close | same |
| `max_available` | not checked | not checked (only indicative) |
| Truck capacity | not checked | checked (stricter) |
| Stock quantity | only "van leaves after the first truck arrives" | quantities checked (stricter) |

## ILS results (work in progress, cost method version 2)

ILS: initial solution (the nearest neighbour above) → VND (2-opt + Or-opt, best improvement) →
remove k random customers and reinsert them → BestBasedThreshold acceptance. Seed 0, one run per
instance; results vary between random seeds.

| Instance | Time limit | Greedy (€) | ILS (€) | Saved | Lower bound (€) | Gap to lower bound |
|---|---|---|---|---|---|---|
| 01 toy | 60 s | 494.00 | 494.00 | 0 % | 476.00 | 3.8 % |
| 02 small | 60 s | 1029.00 | 959.40 | 6.8 % | 826.60 | 16.1 % |
| 03 medium | 60 s | 3294.00 | 2562.60 | 22.2 % | 2031.50* | 26.1 % |
| 04 district | 60 s | 3720.60 | 3341.90 | 10.2 % | 2840.20 | 17.7 % |
| 06 micro hubs | 300 s | 5363.40 | 5259.80 | 1.9 % | 4333.80 | 21.4 % |
| 10 metropolis | 60 s | 8073.50 | 7147.60 | 11.5 % | 5950.40 | 20.1 % |

Gap = (ILS − lower bound) / lower bound. The optimum lies between the lower bound and the ILS cost,
so the real gap to the optimum is smaller, but we cannot say by how much without an exact solver.
The lower bounds are weak (every customer gets its cheapest incoming arc, minimum number of routes).
\* For medium the hand-computed bound of the Doc; the simple bound of `run_all.py` is 1809.20 € (gap 41.6 %).

All six solutions pass the validator (`solutions/*_ils.json`, search logs in `*_ils_progress.csv`).
Instance 06 is slow (18 hubs: the trucks are recomputed for every cost), only about
8 400 iterations in 300 s, so it improves little.

Results depend on the random seed. With seeds 1–3 (60 s each) medium gives 2502.80, 2773.60 and
2503.40 €, district 3346.60, 3349.60 and 3347.20 €, metropolis 7147.60, 7111.00 and 7139.60 €.
The table keeps seed 0 so that every result can be reproduced, for example:

```bash
python3 src/ils.py -i data/instances/instance_03_medium_35pl.json -o solutions/03_medium_35pl_ils.json --time-limit 60 --seed 0
```
