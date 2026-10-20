# Maths Model — Two-Echelon VRP with Time Windows, Pickups and Hub Synchronization

Trucks carry goods DP → DS (tier 1). Vans deliver DS → customers → same DS (tier 2).
A van may leave a hub only after the stock it carries has been unloaded there by a truck.
All times are in minutes from midnight, all costs in cents (same units as the validator). All numbers refer to the medium instance (1 DP, 3 DS, 35 customers), the instance our group submits.

---

## 1. Sets

| Symbol | Meaning |
|---|---|
| 0 | the main depot (DP_1) |
| H | relay hubs (DS), H = {DS_1, DS_2, DS_3} |
| C | customers (PL), \|C\| = 35 in the medium instance |
| N¹ = {0} ∪ H | nodes of the truck network (tier 1) |
| N² = H ∪ C | nodes of the van network (tier 2) |
| T | available trucks, \|T\| = 5 (max_available) |
| V | available vans, \|V\| = 15 (max_available) |

## 2. Parameters (Data)

| Symbol | Meaning | Value / source |
|---|---|---|
| dᵢ | delivery demand of customer i ∈ C (packages) | `demand` |
| pᵢ | pickup quantity of customer i ∈ C (packages) | `pickup` |
| sᵢ | service time at node i | `service_time` (DP 30, DS 25) |
| [aᵢ, bᵢ] | time window of node i (open, close) | `tw_open`, `tw_close` |
| τᵢⱼ | travel time from i to j (min) | `duration_matrix_min` |
| δᵢⱼ | distance from i to j (km), Euclidean, rounded to integer km | from (x, y) |
| Q^T, Q^V | truck / van capacity | 350 / 65 |
| F^T, F^V | fixed cost per truck / van trip | 28 000 / 8 500 ct |
| c^T, c^V | cost per km for truck / van | 175 / 80 ct |
| D^T, D^V | max shift duration of truck / van | 600 / 480 min |
| M | big constant for time (e.g. 1440) | |
| M_L | big constant for load, M_L = Q^V + maxᵢ pᵢ | |

## 3. Decision Variables

**Tier 1: trucks**

| Variable | Domain | Meaning |
|---|---|---|
| x_tij | {0,1} | 1 if truck t drives directly from i to j (i, j ∈ N¹, i ≠ j) |
| y_t | {0,1} | 1 if truck t is used |
| q_ts | ≥ 0 | quantity unloaded by truck t at hub s ∈ H |
| S_t | ≥ 0 | departure time of truck t from the DP |
| U_ts | ≥ 0 | time truck t starts unloading at hub s |
| E_t | ≥ 0 | return time of truck t to the DP |

**Tier 2: vans**

| Variable | Domain | Meaning |
|---|---|---|
| x_vij | {0,1} | 1 if van v drives directly from i to j (i, j ∈ N², i ≠ j, no hub → hub arc) |
| y_v | {0,1} | 1 if van v is used |
| z_vs | {0,1} | 1 if van v starts and ends its tour at hub s |
| w_vi | {0,1} | 1 if van v serves customer i |
| L_v | ≥ 0 | delivery load of van v when it leaves its hub |
| ℓ_vi | ≥ 0 | load on van v right after serving customer i |
| S_v | ≥ 0 | departure time of van v from its hub |
| E_v | ≥ 0 | return time of van v to its hub |
| Tᵢ | ≥ 0 | service start time at customer i |


**Synchronization: hub stock**

| Variable | Domain | Meaning |
|---|---|---|
| f_tsv | ≥ 0 | packages unloaded by truck t at hub s that are then loaded onto van v |
| g_tsv | {0,1} | 1 if van v takes stock from truck t's unloading at hub s |

## 4. Objective Function

```
min Z =  F^T · Σ_{t∈T} y_t  +  F^V · Σ_{v∈V} y_v
       + c^T · Σ_{t∈T} Σ_{i,j∈N¹} δᵢⱼ · x_tij
       + c^V · Σ_{v∈V} Σ_{i,j∈N²} δᵢⱼ · x_vij
```

In euros: 280 Σ y_t + 85 Σ y_v + 1.75 Σ δᵢⱼ x_tij + 0.80 Σ δᵢⱼ x_vij  (C14, C15, C16).

## 5. Constraints

### A. Truck routing (tier 1)

| # | Constraint | Meaning |
|---|---|---|
| (1) | Σ_{s∈H} x_t0s = y_t  ∀t ∈ T | a used truck leaves the DP exactly once |
| (2) | Σ_{s∈H} x_ts0 = y_t  ∀t ∈ T | a used truck returns to the DP exactly once (no reloading, C4) |
| (3) | Σ_{i∈N¹} x_tis = Σ_{j∈N¹} x_tsj ≤ y_t  ∀t ∈ T, s ∈ H | flow conservation at each hub, visited at most once per tour |
| (4) | Σ_{s∈H} q_ts ≤ Q^T · y_t  ∀t ∈ T | truck capacity (C8) |
| (5) | q_ts ≤ Q^T · Σ_{i∈N¹} x_tis  ∀t ∈ T, s ∈ H | a truck can unload only at a hub it visits |

### B. Truck timing

| # | Constraint | Meaning |
|---|---|---|
| (6) | a₀ ≤ S_t,  E_t ≤ b₀  ∀t ∈ T | DP opening hours |
| (7) | U_ts ≥ S_t + τ₀ₛ − M(1 − x_t0s)  ∀t, s ∈ H | arrival time at the first hub |
| (8) | U_tj ≥ U_ti + sᵢ + τᵢⱼ − M(1 − x_tij)  ∀t, i, j ∈ H, i ≠ j | time propagation between hubs (also removes subtours) |
| (9) | E_t ≥ U_ts + sₛ + τₛ₀ − M(1 − x_ts0)  ∀t, s ∈ H | return time to the DP |
| (10) | aₛ ≤ U_ts,  U_ts + sₛ ≤ bₛ + M(1 − Σ_{i∈N¹} x_tis)  ∀t, s ∈ H | unloading happens inside the hub window (C6) |
| (11) | E_t − S_t ≤ D^T  ∀t ∈ T | max truck duration, 600 min (C7) |

### C. Van routing (tier 2)

| # | Constraint | Meaning |
|---|---|---|
| (12) | Σ_{s∈H} z_vs = y_v  ∀v ∈ V | a used van belongs to exactly one hub (any hub may serve any customer, C12) |
| (13) | Σ_{j∈C} x_vsj = z_vs  ∀v ∈ V, s ∈ H | the van leaves its hub once |
| (14) | Σ_{i∈C} x_vis = z_vs  ∀v ∈ V, s ∈ H | the van returns to the same hub |
| (15) | Σ_{i∈N²} x_vij = Σ_{k∈N²} x_vjk = w_vj  ∀v ∈ V, j ∈ C | flow conservation: a van that enters a customer also leaves it |
| (16) | Σ_{v∈V} w_vj = 1  ∀j ∈ C | each customer is served exactly once by one van (no split, C11) |
| (17) | x_vss' = 0  ∀v, s, s' ∈ H | a van never drives hub → hub |

### D. Van load with pickups

| # | Constraint | Meaning |
|---|---|---|
| (18) | L_v = Σ_{j∈C} dⱼ · w_vj  ∀v ∈ V | the load at departure is the sum of the van's deliveries |
| (19) | L_v ≤ Q^V · y_v  ∀v ∈ V | capacity at departure (C8) |
| (20) | ℓ_vj ≥ L_v − dⱼ + pⱼ − M_L(1 − Σ_{s∈H} x_vsj)  ∀v, j ∈ C | load after the first customer |
| (21) | ℓ_vj ≥ ℓ_vi − dⱼ + pⱼ − M_L(1 − x_vij)  ∀v, i, j ∈ C, i ≠ j | load after each later customer (pickups take space, C9) |
| (22) | ℓ_vj ≤ Q^V  ∀v, j ∈ C | capacity after every stop (C8) |

### E. Van timing

| # | Constraint | Meaning |
|---|---|---|
| (23) | Tⱼ ≥ S_v + τₛⱼ − M(1 − x_vsj)  ∀v, s ∈ H, j ∈ C | arrival at the first customer |
| (24) | Tⱼ ≥ Tᵢ + sᵢ + τᵢⱼ − M(1 − Σ_{v∈V} x_vij)  ∀i, j ∈ C, i ≠ j | time propagation (also removes subtours) |
| (25) | E_v ≥ Tᵢ + sᵢ + τᵢₛ − M(1 − x_vis)  ∀v, i ∈ C, s ∈ H | return time to the hub |
| (26) | aⱼ ≤ Tⱼ,  Tⱼ + sⱼ ≤ bⱼ  ∀j ∈ C | the whole service lies inside the customer window; early arrival means waiting (C6) |
| (27) | S_v ≥ aₛ − M(1 − z_vs),  E_v ≤ bₛ + M(1 − z_vs)  ∀v, s ∈ H | the van leaves after the hub opens and is back before it closes |
| (28) | E_v − S_v ≤ D^V  ∀v ∈ V | max van shift, 480 min, including travel, service and waiting (C7) |

### F. Hub synchronization and stock balance

| # | Constraint | Meaning |
|---|---|---|
| (29) | Σ_{t∈T} Σ_{s∈H} f_tsv = L_v  ∀v ∈ V | the van's whole delivery load comes from truck unloads; hubs start empty (C1); pickups are never reused (C10) |
| (30) | f_tsv ≤ Q^V · z_vs  ∀t, s, v | a van only takes stock from its own hub |
| (31) | Σ_{v∈V} f_tsv = q_ts  ∀t ∈ T, s ∈ H | what a truck unloads at a hub is what that hub's vans take out (C13) |
| (32) | f_tsv ≤ Q^V · g_tsv  ∀t, s, v | links quantity and binary |
| (33) | S_v ≥ U_ts + sₛ − M(1 − g_tsv)  ∀t, s, v | a van leaves only after the truck it draws from has finished unloading (C2) |

Why (29)–(33) work: they are a linear form of the stock condition
I_s(h) = Σ_{t : U_ts + sₛ ≤ h} q_ts − Σ_{v from s : S_v ≤ h} L_v ≥ 0 for every hub s and every time h.
Each package a van carries is matched to a truck unloading that finished before the van left.
Several trucks may feed the same hub (C3).

### G. Fleet size, carrier agreements and domains

| # | Constraint | Meaning |
|---|---|---|
| (34) | Σ_{t∈T} y_t ≤ 5,  Σ_{v∈V} y_v ≤ 15 | fleet limits (C5): at most 5 truck trips and 15 van trips; already implied by \|T\| = 5 and \|V\| = 15 |
| (35) | y_t ≥ y_{t+1},  y_v ≥ y_{v+1} | optional symmetry breaking (speeds up the solver) |
| (36) | Σ_{v∈V} z_vs ≥ 2  ∀s ∈ H | every hub dispatches at least 2 vans (C17) |
| (37) | 2 Σ_{v∈V} z_vs ≤ Σ_{v∈V} y_v  ∀s ∈ H | no hub runs more than half of the vans (C18) |
| (38) | x, y, z, w, g ∈ {0,1};  q, f, L, ℓ, S, U, E, T ≥ 0 | variable domains |



## 6. Modelling Assumptions

1. **Single-trip baseline.** Each vehicle index performs at most one trip, and its fixed cost F^T or F^V is charged once for that trip, as the validator charges once per route. The fleet limits (34) therefore bound the number of trips: at most 5 truck trips and 15 van trips. Several trips by the same physical vehicle are not modelled. The lower bounds (2 truck trips, 10 van trips) do not prove that this baseline is feasible, because time windows, shift limits and the carrier rules may require more vehicles; feasibility is checked by the first greedy solution. If more trips are needed, the extension gives each physical vehicle k ordered trips r = 1, …, R_k and adds: S_k,r+1 ≥ E_k,r + s₀ for a truck (reload at the DP) or S_k,r+1 ≥ E_k,r for a van (no overlap); E_k,R − S_k,1 ≤ D^T or D^V (daily shift); all trips of one van start from the same hub (C19).
2. **Hub visits.** In one tour a truck visits each hub at most once. A hub can still be supplied several times a day by different trucks (or by different trips in the extension).
3. **Time windows.** Service must start no earlier than aᵢ and finish no later than bᵢ. The local validator only checks arrival ≤ bᵢ, so a solution that meets this rule also passes it.
4. **Shift start and end.**
   - A truck's shift starts when it leaves the DP; loading at the DP (s₀) is not counted, as in the validator.
   - A van's shift starts when it leaves its hub. Loading a van takes no modelled time, and unloading pickups at the hub takes none either.
5. **Distances.** δᵢⱼ is the Euclidean distance rounded to whole km, as in the validator. Travel times come from the duration matrix.
6. **Truck capacity.** Constraint (4) is enforced even though the local validator does not check it.
7. **Carrier agreements (Group 1).** The memo requires a minimum dispatch volume at every active hub, without giving a number, and forbids any carrier from handling more than half of the vans. The online evaluator for team1 checks two rules: every hub, even an otherwise unused one, has at least 2 van routes, and no hub has more than ⌈t/2⌉ van routes, where t is the total number of van routes. We use the stricter version of each rule, so that a solution satisfies both: every hub dispatches at least 2 vans (36), and no hub dispatches more than half of the vans (37). Vans are counted as van routes, as in the evaluator. A van works only for the carrier of its hub (C19).
8. **Pickups.** Packages collected from customers are unloaded at the van's hub when it returns and stay there; they are not carried back to the DP on the same day, so they use no truck capacity and add no truck timing constraint.
9. **Opening hours.** Hub and depot time windows come from the instance file, which the validator checks and which matches the medium-instance map on the course page: DP 06:00–20:00, DS_1 and DS_2 07:00–18:00, DS_3 07:00–19:00.
10. **Fixed cost unit.** The fleet table of the course page quotes the fixed costs per day (280 € and 85 €), whereas the validator charges them per route. We adopt the validator's rule: one fixed cost per trip. Under the single-trip baseline both readings give the same cost; they would differ only for a vehicle running several trips.
11. **Instance scope.** The model and the bounds are stated for the medium instance (1 DP, 3 DS, 35 customers), which our group submits. Constraints (36) and (37) need several hubs, so they are switched off when the code is tested on the toy instance, which has a single hub; the evaluator also applies them only to instances with more than one hub.

## 7. Bounds (medium instance)

The bounds hold for the single-trip baseline with one fixed cost per trip. Each one keeps only the constraints it relies on, so it is valid for every feasible solution of the medium instance. Distances are in whole kilometres, as in the validator.

| Bound | Value | Justification |
|---|---|---|
| Fleet, trucks | 2 trips | A truck trip carries at most Q^T = 350 packages and the total delivery demand is 624, so at least ⌈624/350⌉ = 2 truck trips are needed. |
| Fleet, vans | 10 trips | A van leaves its hub with its whole delivery load, at most Q^V = 65, so at least ⌈624/65⌉ = 10 van trips. Constraint (36) alone requires 2 × 3 = 6 vans, a weaker bound. A 4/3/3 split of 10 vans satisfies both (36) and (37). |
| Fixed cost | 1 410.00 € | 2 × 280 € + 10 × 85 € = 141 000 ct. |
| Van distance | 181 km, 144.80 € | Every customer is entered exactly once, from a hub or another customer; the sum of the shortest incoming arc per customer is 181 km. |
| Truck distance | 225 km, 393.75 € | At least two truck trips, and every hub must be supplied (every hub dispatches vans (36) and starts with no stock). Enumerating every way to cover the three hubs with two trips, with rounded distances, gives a minimum of 225 km: DP → DS_1 → DS_2 → DP (169 km) and DP → DS_3 → DP (56 km). Three or more trips give at least 281 km. |
| Total lower bound | 1 948.55 € | 1 410.00 + 144.80 + 393.75 €. |
| Upper bound | to be computed | Cost of the first feasible solution of our greedy prototype (0 validator errors). The legacy solution is not feasible, so it is not an upper bound. |


## 8. Link to the Constraint Table

| ID | Model constraints |
|---|---|
| C1 Initial hub stock = 0 | (29) |
| C2 Truck–van synchronization | (32), (33) |
| C3 Truck multiple visits | (31) allows several trucks per hub; multi-trip extension |
| C4 No truck reloading | (1), (2): one departure and one return per tour |
| C5 Fleet limit | (34) |
| C6 Time window | (6), (10), (26), (27) |
| C7 Max route duration | (11), (28) |
| C8 Vehicle capacity | (4), (19), (22) |
| C9 Pickup capacity | (20), (21) |
| C10 No reuse of pickups | (29): only L_v (deliveries) is drawn from hub stock |
| C11 No split delivery | (16) |
| C12 Flexible DS assignment | (12): z_vs is a decision variable |
| C13 Hub flow balance | (31) |
| C14 Vehicle fixed cost | objective: y_t, y_v (one fixed cost per trip) |
| C15 Transport cost | objective: δᵢⱼ x terms |
| C16 Total cost | objective |
| C17 Minimum hub dispatch | (36) |
| C18 Carrier concentration cap | (37) |
| C19 Hub–carrier binding | (12): each van index has one hub z_vs; assumption 1 |
