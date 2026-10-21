# VND configuration comparison

Costs in EUR (vans + trucks). Rank 1 = cheapest on that instance.

### Stage A: VND alone from the nearest-neighbour solution

| Neighbourhoods | Improvement | 01_toy_2pl | 02_small_easy_8pl | 03_medium_35pl | 04_district_50pl | 06_micro_hubs_18ds | 10_metropolis_75pl | Average rank |
|---|---|---|---|---|---|---|---|---|
| relocate + swap | best | 495.70 | 962.80 | 2736.80 | 3542.00 | 5530.40 | 7409.95 | 1.7 |
| swap + two_opt_star | best | 495.70 | 962.80 | 2713.60 | 3545.20 | 5532.00 | 7624.75 | 3.5 |
| relocate + swap | first | 495.70 | 962.80 | 2741.60 | 3683.60 | 5530.40 | 7272.40 | 4.0 |
| two_opt + relocate | best | 495.70 | 962.80 | 2763.20 | 3687.60 | 5530.40 | 7582.75 | 4.8 |
| or_opt + relocate | best | 495.70 | 962.80 | 2763.20 | 3687.60 | 5530.40 | 7582.75 | 4.8 |
| relocate + two_opt_star | best | 495.70 | 962.80 | 2728.00 | 3666.80 | 5530.40 | 7727.95 | 5.2 |
| swap + two_opt_star | first | 495.70 | 962.80 | 2763.20 | 3589.20 | 5536.00 | 7598.35 | 5.2 |
| two_opt + two_opt_star | best | 495.70 | 962.80 | 2725.60 | 3664.40 | 5532.00 | 7706.35 | 5.3 |
| relocate + two_opt_star | first | 495.70 | 962.80 | 2748.00 | 3678.00 | 5530.40 | 7733.55 | 6.5 |
| two_opt + relocate | first | 495.70 | 962.80 | 2773.60 | 3687.60 | 5530.40 | 7751.15 | 7.7 |
| or_opt + relocate | first | 495.70 | 962.80 | 2773.60 | 3687.60 | 5530.40 | 7751.15 | 7.7 |
| two_opt + two_opt_star | first | 495.70 | 962.80 | 2777.60 | 3617.20 | 5542.40 | 7719.15 | 7.8 |
| or_opt + two_opt_star | first | 495.70 | 962.80 | 2777.60 | 3617.20 | 5542.40 | 7719.15 | 7.8 |
| or_opt + two_opt_star | best | 495.70 | 1026.00 | 2739.20 | 3664.40 | 5532.00 | 7706.35 | 8.0 |
| two_opt + swap | best | 495.70 | 1033.20 | 2861.60 | 3595.60 | 5555.20 | 7671.75 | 10.2 |
| two_opt + swap | first | 495.70 | 1033.20 | 2855.20 | 3668.40 | 5555.20 | 7586.15 | 10.3 |
| or_opt + swap | best | 495.70 | 1033.20 | 2861.60 | 3595.60 | 5555.20 | 7677.35 | 10.3 |
| or_opt + swap | first | 495.70 | 1033.20 | 2855.20 | 3668.40 | 5555.20 | 7670.95 | 10.8 |
| two_opt + or_opt | first | 495.70 | 1034.00 | 2873.60 | 3727.60 | 5570.40 | 7916.55 | 16.0 |
| two_opt + or_opt | best | 495.70 | 1034.00 | 2873.60 | 3727.60 | 5570.40 | 7916.55 | 16.0 |

### Stage B: ILS, 60 s, seed 0

| Neighbourhoods | Improvement | 01_toy_2pl | 02_small_easy_8pl | 03_medium_35pl | 04_district_50pl | 06_micro_hubs_18ds | 10_metropolis_75pl | Average rank |
|---|---|---|---|---|---|---|---|---|
| two_opt + swap | best | 495.70 | 962.80 | 2610.20 | 3337.00 | 5128.55 | 7128.00 | 2.7 |
| relocate + swap | best | 495.70 | 962.80 | 2615.80 | 3337.00 | 5529.60 | 7122.40 | 3.3 |
| swap + two_opt_star | best | 495.70 | 962.80 | 2658.40 | 3337.00 | 5128.55 | 7121.60 | 3.7 |
| relocate + two_opt_star | first | 495.70 | 962.80 | 2328.75 | 3337.00 | 5529.60 | 7198.95 | 4.0 |
| two_opt + or_opt | best | 495.70 | 962.80 | 2603.80 | 3335.30 | 5530.40 | 7129.40 | 4.3 |
| two_opt + swap | first | 495.70 | 962.80 | 2615.80 | 3337.00 | 5530.40 | 7121.60 | 4.3 |
| or_opt + two_opt_star | best | 495.70 | 962.80 | 2596.60 | 3337.00 | 5529.60 | 7197.00 | 4.3 |
| two_opt + two_opt_star | best | 495.70 | 962.80 | 2658.40 | 3337.00 | 5529.60 | 7139.20 | 5.2 |
| or_opt + relocate | best | 495.70 | 962.80 | 2345.95 | 3347.40 | 5529.60 | 7155.20 | 5.8 |
| relocate + swap | first | 495.70 | 962.80 | 2664.00 | 3337.00 | 5529.60 | 7145.60 | 6.0 |
| swap + two_opt_star | first | 495.70 | 962.80 | 2658.40 | 3337.00 | 5128.55 | 7205.00 | 6.0 |
| or_opt + swap | best | 495.70 | 962.80 | 2616.60 | 3337.00 | 5530.40 | 7183.40 | 6.3 |
| two_opt + two_opt_star | first | 495.70 | 962.80 | 2622.20 | 3329.70 | 5530.40 | 7211.95 | 7.0 |
| or_opt + swap | first | 495.70 | 962.80 | 2657.60 | 3337.00 | 5530.40 | 7190.60 | 7.2 |
| or_opt + two_opt_star | first | 495.70 | 962.80 | 2613.40 | 3337.00 | 5530.40 | 7230.60 | 7.3 |
| two_opt + relocate | best | 495.70 | 962.80 | 2345.15 | 3357.80 | 5529.60 | 7219.40 | 7.5 |
| two_opt + or_opt | first | 495.70 | 962.80 | 2627.80 | 3352.20 | 5530.40 | 7129.40 | 8.0 |
| relocate + two_opt_star | best | 495.70 | 962.80 | 2667.20 | 3337.80 | 5529.60 | 7154.40 | 8.3 |
| or_opt + relocate | first | 495.70 | 962.80 | 2635.80 | 3355.40 | 5530.40 | 7220.80 | 10.7 |
| two_opt + relocate | first | 495.70 | 962.80 | 2663.20 | 3353.00 | 5530.40 | 7221.00 | 11.5 |

### Stage A time per descent (s, mean over instances)

- two_opt + or_opt / first: 0.16
- two_opt + or_opt / best: 0.17
- two_opt + relocate / first: 0.35
- two_opt + relocate / best: 0.38
- two_opt + swap / first: 0.26
- two_opt + swap / best: 0.27
- two_opt + two_opt_star / first: 0.26
- two_opt + two_opt_star / best: 0.32
- or_opt + relocate / first: 0.29
- or_opt + relocate / best: 0.43
- or_opt + swap / first: 0.22
- or_opt + swap / best: 0.38
- or_opt + two_opt_star / first: 0.28
- or_opt + two_opt_star / best: 0.30
- relocate + swap / first: 0.57
- relocate + swap / best: 0.57
- relocate + two_opt_star / first: 0.33
- relocate + two_opt_star / best: 0.50
- swap + two_opt_star / first: 0.26
- swap + two_opt_star / best: 0.42

### Stage C: stability, 5 seeds x 60 s, best improvement

Mean gap: average over instances of (mean cost - best mean cost) / best mean cost.

| Neighbourhoods (best improvement) | 03_medium_35pl mean / best | 04_district_50pl mean / best | 06_micro_hubs_18ds mean / best | 10_metropolis_75pl mean / best | Mean gap to best mean |
|---|---|---|---|---|---|
| two_opt + or_opt | 2543.19 / 2324.75 | 3351.88 / 3346.60 | 5291.37 / 5127.75 | 7138.20 / 7114.20 | 0.44% |
| two_opt + swap | 2607.48 / 2595.80 | 3337.00 / 3337.00 | 5371.74 / 5177.40 | 7118.08 / 7020.60 | 1.28% |
| two_opt + relocate | 2516.78 / 2332.95 | 3345.64 / 3337.00 | 5529.76 / 5529.60 | 7195.12 / 7162.40 | 1.46% |
| or_opt + two_opt_star | 2580.23 / 2331.15 | 3337.00 / 3337.00 | 5459.16 / 5177.40 | 7195.04 / 7150.40 | 1.69% |
| or_opt + relocate | 2583.75 / 2340.95 | 3347.40 / 3337.00 | 5529.76 / 5529.60 | 7157.24 / 7099.80 | 2.01% |
| swap + two_opt_star | 2633.12 / 2595.80 | 3337.00 / 3337.00 | 5459.64 / 5177.40 | 7158.52 / 7105.60 | 2.09% |
| relocate + swap | 2648.04 / 2615.80 | 3337.00 / 3337.00 | 5529.76 / 5529.60 | 7174.56 / 7105.60 | 2.63% |
