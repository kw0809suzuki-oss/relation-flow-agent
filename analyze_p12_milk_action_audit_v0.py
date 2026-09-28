#!/usr/bin/env python3
"""Aggregate the narrow P12 all-participant MILK action audit."""
import glob
import json
from pathlib import Path

OUT = Path("p12_milk_action_audit_v0_result.json")


def group_name(delta_self):
    if delta_self > 0:
        return "improved"
    if delta_self < 0:
        return "worsened"
    return "equal"


def transition_map(world):
    return {
        int(row["from_hour"]): row
        for row in world.get("transitions", [])
        if int(row.get("from_day", 0)) == 19
    }


def role_row(row, role):
    for item in row.get("submitted_actions", []):
        if item.get("role") == role:
            return item
    return {}


def action_signature(item):
    return json.dumps(item.get("market_actions", []), ensure_ascii=False, sort_keys=True)


def rng(values):
    if not values:
        return None
    return {
        "min": min(values),
        "max": max(values),
        "mean": sum(values) / len(values),
    }


def separated(a, b):
    if not a or not b:
        return False
    return max(a) < min(b) or max(b) < min(a)


def main():
    files = sorted(glob.glob("p12-milk-action-audit-artifacts/*.json"))
    cases = []
    for path in files:
        obj = json.loads(Path(path).read_text(encoding="utf-8"))
        cases.append(obj)

    metrics = {}
    seed_rows = []
    for case in cases:
        group = group_name(float(case["delta_self"]))
        cur = transition_map(case["current"])
        cand = transition_map(case["candidate"])
        seed_summary = {
            "seed": case["seed"],
            "seat": case["seat"],
            "group": group,
            "delta_self": case["delta_self"],
            "hours": {},
        }
        for hour in (16, 17, 18):
            if hour not in cur or hour not in cand:
                continue
            c0 = cur[hour]
            c1 = cand[hour]
            row = {
                "milk_inventory_before_delta": c1["market_before"]["milk_inventory"] - c0["market_before"]["milk_inventory"],
                "milk_inventory_after_delta": c1["market_after"]["milk_inventory"] - c0["market_after"]["milk_inventory"],
                "milk_price_before_delta": c1["market_before"]["milk_price"] - c0["market_before"]["milk_price"],
                "milk_price_after_delta": c1["market_after"]["milk_price"] - c0["market_after"]["milk_price"],
                "self_sell_milk_delta": role_row(c1, "self").get("sell_milk_units", 0) - role_row(c0, "self").get("sell_milk_units", 0),
                "opponent_sell_milk_delta": role_row(c1, "opponent").get("sell_milk_units", 0) - role_row(c0, "opponent").get("sell_milk_units", 0),
                "self_market_action_changed": action_signature(role_row(c1, "self")) != action_signature(role_row(c0, "self")),
                "opponent_market_action_changed": action_signature(role_row(c1, "opponent")) != action_signature(role_row(c0, "opponent")),
                "current_submitted_actions": c0.get("submitted_actions", []),
                "candidate_submitted_actions": c1.get("submitted_actions", []),
            }
            seed_summary["hours"][str(hour)] = row
            for key in (
                "milk_inventory_before_delta",
                "milk_inventory_after_delta",
                "milk_price_before_delta",
                "milk_price_after_delta",
                "self_sell_milk_delta",
                "opponent_sell_milk_delta",
            ):
                metrics.setdefault(str(hour), {}).setdefault(key, {}).setdefault(group, []).append(float(row[key]))
        seed_rows.append(seed_summary)

    summary = {}
    for hour, hour_metrics in metrics.items():
        summary[hour] = {}
        for key, groups in hour_metrics.items():
            imp = groups.get("improved", [])
            wor = groups.get("worsened", [])
            summary[hour][key] = {
                "improved": rng(imp),
                "worsened": rng(wor),
                "clean_group_separation": separated(imp, wor),
            }

    payload = {
        "schema": "kaggriculture.p12-milk-action-audit.aggregate.v0",
        "case_count": len(cases),
        "improved": sum(1 for x in cases if x["delta_self"] > 0),
        "worsened": sum(1 for x in cases if x["delta_self"] < 0),
        "summary_by_from_hour": summary,
        "seed_rows": seed_rows,
        "boundary": [
            "Replay actions are submissions, not resolver-acceptance receipts.",
            "A clean separation in submitted action metrics is association, not causality.",
            "Market state transitions are public environment outcomes after submitted actions.",
            "No policy or P12 trigger is changed.",
        ],
    }
    OUT.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "case_count": payload["case_count"],
        "improved": payload["improved"],
        "worsened": payload["worsened"],
        "summary_by_from_hour": payload["summary_by_from_hour"],
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
