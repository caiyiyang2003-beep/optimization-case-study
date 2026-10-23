# Two-echelon delivery – Group 1 (team1)

组内说明，不交给老师。

题目：https://albanderrien.fr/cours/most/lab/ ，Group 1 规则：https://albanderrien.fr/cours/most/groupes/groupe-1/

数学模型（主版本）在 Google Doc 的 "maths model" 标签页，[math_model.md](math_model.md) 是本地备份。
两边不一致时以 Doc 为准。

## 怎么运行

只需要 Python 3，不用装别的包（`scripts/plot_instance.py` 画图要 matplotlib）。

```bash
# 解全部 10 个 instance，结果写到 solutions/，汇总表写到 solutions/summary.md
python3 src/run_all.py

# 只解一个
python3 src/greedy_nn.py -i data/instances/instance_03_medium_35pl.json -o solutions/03.json

# 用老师的 validator 检查一个解
python3 scripts/evaluate_solution.py --instance data/instances/instance_03_medium_35pl.json --solution solutions/03_medium_35pl_greedy.json
```

最后一定要再上网页 evaluator 验一次。本地 validator 不查 Group 1 规则，网页版查。

## 文件

| 文件 | 内容 |
|---|---|
| `src/instance_tools.py` | 读 instance、检查坏数据、距离和时间（取整方式和 validator 一致）、简单下界 |
| `src/greedy_nn.py` | 求解器，见下面"算法" |
| `src/run_all.py` | 跑所有 instance，用老师的 validator 检查，写汇总表 |
| `src/ils.py` | ILS（还在做，这周不交） |
| `src/tune_vnd.py` | 选 ILS 邻域用的实验脚本，结果在 `solutions/vnd_comparison.md` |
| `scripts/` | 老师给的脚本：`evaluate_solution.py`（validator）、`load_data.py`、`plot_instance.py` |
| `data/instances/` | 网站上的 10 个 instance |
| `data/medium_35pl/` 等 | 最早给的 3 个 instance、legacy 解和违规分类 |
| `solutions/*_greedy.json` | 当前提交用的解（team1 / api_key 已经写在里面） |

注意：`scripts/validator_server.py` 其实是网页的 HTML，不是 Python，不能运行。

## 算法（`greedy_nn.py`）

所有参数都从 JSON 读，不针对某个 instance 写死。

1. **货车：Nearest Neighbor。** 从 DS 出发，一直去最近的、还装得下（含 pickup）、赶得上时间窗、
   不超过班次时长的客户，没有就回 DS，再开下一辆。服务必须在关窗前结束（我们的假设）。
2. **Group 1 修复。** 每个 DS 至少 2 趟货车，没有 DS 超过总数一半。不满足时，每次选最便宜的一步：
   A. 整条路线换一个 DS 出发；B. 拆出一个客户单独派一辆车。
3. **卡车：也是 Nearest Neighbor。** 某个 DS 的需求超过一整车，先派满车直送；剩下的零头，卡车从 DP 出发，
   一直去最近的、零头还装得下、时间窗赶得上的 DS。
4. **库存检查（模型约束 29–33）。** 每个 DS 单独看：每辆货车出发时，到这一刻已经卸下的货 ≥ 已经出发的
   货车带走的货。哪个 DS 不够，就给它单独派一趟卡车再试。
5. **车队上限（约束 34）和多趟。** 把多趟路线排到同一辆实体车上，不超过 `max_available`。
   同一辆车的第二趟在 JSON 里叫 `Delivery_Van_3_T2` 这种名字，每趟都重新算固定成本（我们的假设）。

解不出来时会报原因，不会崩溃。

## 当前结果

| Instance | 结果 | 成本 (€) |
|---|---|---|
| 01 toy | 可行 | 495.70 |
| 02 small | 可行 | 1042.00 |
| 03 medium | 可行 | 2878.40 |
| 04 district | 可行 | 3730.00 |
| 05 suburban | 无可行解：PL_1 的时间窗派专车也赶不到 | – |
| 06 micro hubs | 可行 | 5920.40 |
| 07 regional | 无可行解：PL_14 需求 74 > 货车容量 65，Group 1 不允许拆单 | – |
| 08 legacy CRM | 坏数据：PL_18 需求 10 000 000 | – |
| 09 urban | 坏数据：JSON 写错了（`"demand": 23A`） | – |
| 10 metropolis | 可行 | 7919.75 |

6 个可行解都在网页 evaluator 上验过，0 违规。下界见 `solutions/summary.md` 和 Doc 的 Bounds 部分。

## 本地 validator 和网页版的区别

| 检查 | 本地 `evaluate_solution.py` | 网页版 | 我们的代码 |
|---|---|---|---|
| Group 1 规则 | 不查 | 查 | 遵守 |
| 服务在关窗前结束 | 只查到达 | 只查到达 | 遵守（更严） |
| 库存数量 | 只查货车不早于第一趟卡车到达 | 同左 | 查数量（更严） |
| `max_available` | 不查 | 不查 | 遵守 |

## 下一步

- ILS：初始解（上面的 NN）→ VND（2-opt + Or-opt，best improvement）→ 随机移除 k 个客户再插回 → BestBasedThreshold 接受准则，60 s 停止。
  medium 上 60 s 能从 2878.40 € 降到约 2600 €，不同随机种子之间差异较大。
- 06 的卡车 NN 比 Clarke-Wright 贵 350 €，以后可以改进。
