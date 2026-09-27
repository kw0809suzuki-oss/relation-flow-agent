#!/usr/bin/env python3
import json
import statistics
from pathlib import Path

FILES = sorted(Path("p12-milk-flow-observer-artifacts").glob("p12_milk_flow_observer_v0_*_seat*.json"))
ROWS = [json.loads(p.read_text(encoding="utf-8")) for p in FILES]
if len(ROWS) != 20:
    raise SystemExit(f"expected 20 results, got {len(ROWS)}")

METRICS = [
    "market_inventory_milk",
    "market_price_milk",
    "self_cumulative_sell_milk",
    "self_cumulative_buy_cow",
    "self_cows",
    "self_milk_qty",
    "self_wheat_qty",
    "self_cash",
    "opponent_cash",
]

def group(r):
    return "IMPROVED" if r["delta_self"] > 0 else "WORSENED" if r["delta_self"] < 0 else "TIED"

def keyrows(side):
    return {(x["day"], x["hour"]): x for x in side["rows"]}

def stats(xs):
    if not xs:
        return None
    return {
        "n": len(xs),
        "mean": statistics.mean(xs),
        "median": statistics.median(xs),
        "min": min(xs),
        "max": max(xs),
        "unique": sorted(set(xs)),
    }

times = sorted(set(
    (x["day"], x["hour"])
    for r in ROWS
    for side in ("current", "candidate")
    for x in r[side]["rows"]
))

timeline = []
first_any_sep = None
first_market_sep = None
first_self_action_sep = None

for t in times:
    vals = {m: {"IMPROVED": [], "WORSENED": []} for m in METRICS}
    complete = True
    for r in ROWS:
        c = keyrows(r["current"]).get(t)
        k = keyrows(r["candidate"]).get(t)
        if c is None or k is None:
            complete = False
            continue
        g = group(r)
        if g not in ("IMPROVED", "WORSENED"):
            continue
        for m in METRICS:
            vals[m][g].append(float(k[m]) - float(c[m]))

    comps = {}
    seps = []
    for m in METRICS:
        imp = vals[m]["IMPROVED"]
        wor = vals[m]["WORSENED"]
        if len(imp) != 6 or len(wor) != 14:
            continue
        sep = max(imp) < min(wor) or max(wor) < min(imp)
        comps[m] = {
            "improved": stats(imp),
            "worsened": stats(wor),
            "ranges_disjoint": sep,
        }
        if sep:
            seps.append(m)

    if seps and first_any_sep is None:
        first_any_sep = {"day": t[0], "hour": t[1], "metrics": seps}
    market_seps = [m for m in seps if m in ("market_inventory_milk", "market_price_milk")]
    if market_seps and first_market_sep is None:
        first_market_sep = {"day": t[0], "hour": t[1], "metrics": market_seps}
    action_seps = [m for m in seps if m in ("self_cumulative_sell_milk", "self_cumulative_buy_cow", "self_cows", "self_milk_qty")]
    if action_seps and first_self_action_sep is None:
        first_self_action_sep = {"day": t[0], "hour": t[1], "metrics": action_seps}

    timeline.append({
        "day": t[0],
        "hour": t[1],
        "complete": complete,
        "range_separators": seps,
        "comparisons": comps,
    })

focus = None
if first_market_sep:
    for row in timeline:
        if row["day"] == first_market_sep["day"] and row["hour"] == first_market_sep["hour"]:
            focus = row
            break

cases = []
if first_market_sep:
    t = (first_market_sep["day"], first_market_sep["hour"])
    for r in ROWS:
        c = keyrows(r["current"])[t]
        k = keyrows(r["candidate"])[t]
        cases.append({
            "seed": r["seed"],
            "seat": r["seat"],
            "terminal_group": group(r),
            "delta_self": r["delta_self"],
            "delta_margin": r["delta_margin"],
            "delta_market_inventory_milk": k["market_inventory_milk"] - c["market_inventory_milk"],
            "delta_market_price_milk": k["market_price_milk"] - c["market_price_milk"],
            "delta_cumulative_sell_milk": k["self_cumulative_sell_milk"] - c["self_cumulative_sell_milk"],
            "delta_cumulative_buy_cow": k["self_cumulative_buy_cow"] - c["self_cumulative_buy_cow"],
            "delta_self_cows": k["self_cows"] - c["self_cows"],
            "delta_self_milk_qty": k["self_milk_qty"] - c["self_milk_qty"],
            "delta_self_cash": k["self_cash"] - c["self_cash"],
            "delta_opponent_cash": k["opponent_cash"] - c["opponent_cash"],
        })

out = {
    "schema": "kaggriculture.p12-milk-flow-observer.fresh20.result.v0",
    "battle_count": len(ROWS),
    "terminal_counts": {
        "improved": sum(group(r) == "IMPROVED" for r in ROWS),
        "worsened": sum(group(r) == "WORSENED" for r in ROWS),
    },
    "first_any_range_separation": first_any_sep,
    "first_market_range_separation": first_market_sep,
    "first_self_action_range_separation": first_self_action_sep,
    "focus": focus,
    "focus_cases": cases,
    "timeline": timeline,
    "boundary": [
        "Shared market state cannot be causally attributed to self from this observer alone.",
        "Self cumulative SELL MILK / BUY COW are directly observed selected-agent actions.",
        "Range separation is descriptive association with terminal group, not a policy trigger.",
    ],
}
Path("p12_milk_flow_observer_v0_result.json").write_text(
    json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
)
print("P12_MILK_FLOW_RESULT " + json.dumps({
    "first_any_range_separation": first_any_sep,
    "first_market_range_separation": first_market_sep,
    "first_self_action_range_separation": first_self_action_sep,
}, separators=(",", ":")))
