# Greedy results on all instances

Lower bound: simple instance-independent bound (fixed costs from fleet sizes, cheapest incoming arc per customer, one out-and-back to the nearest hub per truck trip).

| Instance | Status | Truck trips on trucks | Van trips on vans | Cost (EUR) | Lower bound (EUR) | Gap | Model check | Course validator | Note |
|---|---|---|---|---|---|---|---|---|---|
| 01_toy_2pl | solved | 1 on 1 | 1 on 1 | 495.70 | 478.10 | 4% | OK | OK | (0.0s) |
| 02_small_easy_8pl | solved | 1 on 1 | 4 on 4 | 962.80 | 829.00 | 16% | OK | OK | (0.0s) |
| 03_medium_35pl | solved | 3 on 3 | 11 on 10 | 2 733.60 | 1 750.80 | 56% | OK | OK | (0.0s) |
| 04_district_50pl | solved | 3 on 3 | 17 on 16 | 4 763.40 | 2 859.00 | 67% | OK | OK | (0.0s) |
| 05_suburban_52pl | infeasible |  |  |  | 3 540.20 |  |  |  | with fleet limits: customer PL_1 cannot be served even by a dedicated van (window 420-450 too early or too far from every hub); without limits: customer PL_1 cannot be served even by a dedicated van (window 420-450 too early or too far from every hub) |
| 06_micro_hubs_18ds | solved | 4 on 4 | 36 on 18 | 5 532.00 | 4 339.90 | 27% | OK | OK | (0.4s) |
| 07_regional_58pl | invalid instance |  |  |  |  |  |  |  | PL_14: order of 74 delivered / 0 collected exceeds the van capacity 65, and orders cannot be split |
| 08_legacy_crm_60pl | invalid instance |  |  |  |  |  |  |  | PL_18: order of 10000000 delivered / 0 collected exceeds the van capacity 65, and orders cannot be split |
| 09_urban_64pl | invalid instance |  |  |  |  |  |  |  | invalid JSON at line 335, column 19: Expecting ',' delimiter -> '"demand": 23A,' |
| 10_metropolis_75pl | solved | 6 on 6 | 35 on 22 | 7 604.15 | 5 952.80 | 28% | OK | OK | (0.5s) |
