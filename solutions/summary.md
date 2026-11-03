# Initial solutions (nearest neighbour)

| Instance | Status | Truck trips on trucks | Van trips on vans | Cost (EUR) | Lower bound (EUR) | Validator | Note |
|---|---|---|---|---|---|---|---|
| 01_toy_2pl | solved | 1 on 1 | 1 on 1 | 494.00 | 476.00 | OK |  |
| 02_small_easy_8pl | solved | 1 on 1 | 4 on 4 | 1029.00 | 826.60 | OK |  |
| 03_medium_35pl | solved | 3 on 3 | 11 on 10 | 3223.40 | 1809.20 | OK |  |
| 04_district_50pl | solved | 3 on 3 | 18 on 12 | 3720.60 | 2840.20 | OK |  |
| 05_suburban_52pl | infeasible |  |  |  |  |  | customers ['PL_1'] cannot be served even by a dedicated van |
| 06_micro_hubs_18ds | solved | 3 on 3 | 36 on 18 | 5363.40 | 4333.80 | OK |  |
| 07_regional_58pl | invalid instance |  |  |  |  |  | PL_14: order of 74 delivered / 0 collected exceeds the van capacity 65, and orders cannot be split |
| 08_legacy_crm_60pl | invalid instance |  |  |  |  |  | PL_18: order of 10000000 delivered / 0 collected exceeds the van capacity 65, and orders cannot be split |
| 09_urban_64pl | invalid instance |  |  |  |  |  | invalid JSON at line 335, column 19: Expecting ',' delimiter -> '"demand": 23A,' |
| 10_metropolis_75pl | solved | 6 on 6 | 37 on 18 | 7905.30 | 5950.40 | OK |  |
