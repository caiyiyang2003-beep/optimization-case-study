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

Always check the final solutions on the online evaluator too: the local validator does not check
the Group 1 rules, the online one does.

## Files

| File | Content |
|---|---|
| `src/instance_tools.py` | Reads an instance, rejects broken data, distances and travel times (rounded as the validator does), a simple lower bound |
| `src/greedy_nn.py` | The solver, see "Algorithm" below |
| `src/run_all.py` | Solves every instance, checks it with the course validator, writes the summary table |
| `src/ils.py` | Iterated local search (work in progress, not handed in this week) |
| `src/tune_vnd.py` | Experiment used to choose the ILS neighbourhoods, results in `solutions/vnd_comparison.md` |
| `scripts/` | Scripts from the course: `evaluate_solution.py` (validator), `load_data.py`, `plot_instance.py` |
| `data/instances/` | The 10 instances from the course website |
| `data/medium_35pl/` etc. | The first 3 instances, the legacy solution and its classified violations |
| `solutions/*_greedy.json` | Our current solutions (team name and API key already filled in) |

Note: `scripts/validator_server.py` actually contains the HTML of the course web page, not Python code, so it cannot be run.

## Algorithm (`greedy_nn.py`)

Everything is read from the JSON file; nothing is tuned for a particular instance.

1. **Vans: nearest neighbour.** A van leaves a hub and keeps driving to the closest customer it can
   still serve (capacity including pickups, time window, shift length); when none fits it returns
   and the next van starts. Service must end before the window closes (our assumption).
2. **Group 1 repair.** Every hub sends at least 2 van trips and no hub sends more than half of them.
   While a rule is broken, apply the cheapest move that reduces the violation:
   take one customer out of a route and serve it with its own van, from any hub.
3. **Trucks: nearest neighbour too.** Demand above a full truckload goes first in direct trips.
   For the remaining demand, a truck leaves the DP and keeps driving to the closest hub whose
   remaining demand still fits and whose time window can still be met.
4. **Stock check (model constraints 29–33).** Hub by hub: each time a van leaves, the stock unloaded
   so far must cover the goods taken by all vans gone so far. A hub that runs short gets its own
   truck trip and the trucks are planned again.
5. **Fleet limit (constraint 34) and multiple trips.** Trips are chained onto physical vehicles so
   that `max_available` is respected. If there are too many vans, trips leave as early as possible,
   but never before the last truck has unloaded at their hub, so one van can run several trips. The second trip of a vehicle is named like
   `Delivery_Van_3_T2`, and every trip pays the fixed cost again (our assumption).

When an instance cannot be solved, the code says why instead of crashing.

## Current results

| Instance | Result | Cost (€) |
|---|---|---|
| 01 toy | feasible | 495.70 |
| 02 small | feasible | 1042.00 |
| 03 medium | feasible | 2878.40 |
| 04 district | feasible | 3730.00 |
| 05 suburban | infeasible: PL_1's time window cannot be met even by a dedicated van | – |
| 06 micro hubs | feasible | 5920.40 |
| 07 regional | infeasible: PL_14 orders 74 > van capacity 65, and Group 1 forbids splitting orders | – |
| 08 legacy CRM | broken data: PL_18 orders 10 000 000 | – |
| 09 urban | broken data: invalid JSON (`"demand": 23A`) | – |
| 10 metropolis | feasible | 7919.75 |

All 6 feasible solutions pass the online evaluator with 0 violations. Lower bounds are in
`solutions/summary.md` and in the Bounds section of the Doc.

## Local validator vs online evaluator

| Check | Local `evaluate_solution.py` | Online evaluator | Our code |
|---|---|---|---|
| Group 1 rules | not checked | checked | respected |
| Service ends before the window closes | arrival only | arrival only | respected (stricter) |
| Stock quantity | only "van leaves after the first truck arrives" | same | quantities checked (stricter) |
| `max_available` | not checked | not checked | respected |

## Next steps

- ILS: initial solution (the nearest neighbour above) → VND (2-opt + Or-opt, best improvement) →
  remove k random customers and reinsert them → BestBasedThreshold acceptance, stop after 60 s.
  On medium, 60 s bring the cost from 2878.40 € to about 2600 €; results vary a lot between random seeds.
- On instance 06, nearest-neighbour trucks cost 350 € more than the savings heuristic we used before; worth improving later.
