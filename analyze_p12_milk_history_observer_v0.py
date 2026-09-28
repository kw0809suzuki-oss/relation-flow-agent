#!/usr/bin/env python3
"""Aggregate P12 MILK market history and locate stratification onset."""
import glob
import json
from pathlib import Path

OUT = Path("p12_milk_history_observer_v0_result.json")
FOCUS = (19, 17)


def group_name(delta_self):
    if delta_self > 0:
        return "improved"
    if delta_self < 0:
        return "worsened"
    return "equal"


def stats(values):
    if not values:
        return None
    s = sorted(values)
    n = len(s)
    mid = n // 2
    median = s[mid] if n % 2 else (s[mid - 1] + s[mid]) / 2
    return {
        "n": n,
        "mean": sum(s) / n,
        "median": median,
        "min": min(s),
        "max": max(s),
        "nonzero": sum(1 for x in s if x != 0),
    }


def key(row):
    return (int(row["day"]), int(row["hour"]))


def row_map(world):
    return {key(r): r for r in world.get("rows", [])}


def main():
    files = sorted(glob.glob("p12-milk-history-observer-artifacts/*.json"))
    cases = []
    for path in files:
        obj = json.loads(Path(path).read_text(encoding="utf-8"))
        obj["group"] = group_name(float(obj["delta_self"]))
        obj["_current"] = row_map(obj["current"])
        obj["_candidate"] = row_map(obj["candidate"])
        cases.append(obj)

    times = sorted({
        t
        for c in cases
        for t in set(c["_current"]).intersection(c["_candidate"])
        if t <= FOCUS
    })

    timeline = []
    for day, hour in times:
        groups = {"improved": [], "worsened": []}
        for c in cases:
            if c["group"] not in groups:
                continue
            b = c["_current"][(day, hour)]
            p = c["_candidate"][(day, hour)]
            groups[c["group"]].append({
                "inventory": p["market_inventory_milk"] - b["market_inventory_milk"],
                "price": p["market_price_milk"] - b["market_price_milk"],
            })

        imp_i = [x["inventory"] for x in groups["improved"]]
        wor_i = [x["inventory"] for x in groups["worsened"]]
        imp_p = [x["price"] for x in groups["improved"]]
        wor_p = [x["price"] for x in groups["worsened"]]

        inv_imp = stats(imp_i)
        inv_wor = stats(wor_i)
        price_imp = stats(imp_p)
        price_wor = stats(wor_p)

        inv_gap = (
            inv_wor["min"] - inv_imp["max"]
            if inv_imp and inv_wor else None
        )
        price_gap = (
            price_imp["min"] - price_wor["max"]
            if price_imp and price_wor else None
        )

        timeline.append({
            "day": day,
            "hour": hour,
            "inventory": {
                "improved": inv_imp,
                "worsened": inv_wor,
                "range_gap": inv_gap,
                "mean_order": (
                    inv_imp is not None
                    and inv_wor is not None
                    and inv_imp["mean"] < inv_wor["mean"]
                ),
            },
            "price": {
                "improved": price_imp,
                "worsened": price_wor,
                "range_gap": price_gap,
                "mean_order": (
                    price_imp is not None
                    and price_wor is not None
                    and price_imp["mean"] > price_wor["mean"]
                ),
            },
            "both_mean_order": (
                inv_imp is not None and inv_wor is not None
                and price_imp is not None and price_wor is not None
                and inv_imp["mean"] < inv_wor["mean"]
                and price_imp["mean"] > price_wor["mean"]
            ),
            "both_range_disjoint": (
                inv_gap is not None and price_gap is not None
                and inv_gap > 0 and price_gap > 0
            ),
        })

    first_any_nonzero = None
    first_both_mean_order = None
    first_persistent_both_mean_order = None
    first_inventory_touch = None
    first_price_touch = None
    first_both_range_disjoint = None

    for idx, r in enumerate(timeline):
        inv = r["inventory"]
        price = r["price"]
        any_nonzero = (
            inv["improved"]["nonzero"] > 0
            or inv["worsened"]["nonzero"] > 0
            or price["improved"]["nonzero"] > 0
            or price["worsened"]["nonzero"] > 0
        )
        point = {"day": r["day"], "hour": r["hour"]}
        if first_any_nonzero is None and any_nonzero:
            first_any_nonzero = point
        if first_both_mean_order is None and r["both_mean_order"]:
            first_both_mean_order = point
        if (
            first_persistent_both_mean_order is None
            and r["both_mean_order"]
            and all(x["both_mean_order"] for x in timeline[idx:])
        ):
            first_persistent_both_mean_order = point
        if first_inventory_touch is None and inv["range_gap"] >= 0:
            first_inventory_touch = {
                **point,
                "range_gap": inv["range_gap"],
            }
        if first_price_touch is None and price["range_gap"] >= 0:
            first_price_touch = {
                **point,
                "range_gap": price["range_gap"],
            }
        if first_both_range_disjoint is None and r["both_range_disjoint"]:
            first_both_range_disjoint = point

    payload = {
        "schema": "kaggriculture.p12-milk-history-observer.aggregate.v0",
        "case_count": len(cases),
        "terminal_counts": {
            "improved": sum(1 for c in cases if c["group"] == "improved"),
            "worsened": sum(1 for c in cases if c["group"] == "worsened"),
            "equal": sum(1 for c in cases if c["group"] == "equal"),
        },
        "milestones": {
            "first_any_nonzero_market_delta": first_any_nonzero,
            "first_both_group_mean_order": first_both_mean_order,
            "first_persistent_both_group_mean_order_to_day19_hour17": first_persistent_both_mean_order,
            "first_inventory_range_touch_or_separation": first_inventory_touch,
            "first_price_range_touch_or_separation": first_price_touch,
            "first_both_ranges_cleanly_disjoint": first_both_range_disjoint,
        },
        "timeline": timeline,
        "boundary": [
            "This locates temporal emergence of group-level MILK market stratification only.",
            "Mean ordering is descriptive and is weaker than range separation.",
            "Range gap < 0 means group ranges overlap; 0 means touch; > 0 means disjoint.",
            "No participant action, resolver event, or causal mechanism is attributed.",
            "The next causal probe should be chosen only after locating the earliest informative interval.",
        ],
    }
    OUT.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "case_count": payload["case_count"],
        "terminal_counts": payload["terminal_counts"],
        "milestones": payload["milestones"],
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
