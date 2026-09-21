#!/usr/bin/env python3
import json
from pathlib import Path

from scale_roi_observer import ScaleObservation, estimate_land_window_return, land_recovery_windows


INPUT = Path("scale_baseline_v1.json")
OUTPUT = Path("land_recovery_window_v1.json")


def iter_observation_sets(raw):
    # Accept either a flat list or the baseline export's per-case structure.
    if isinstance(raw, list):
        if raw and isinstance(raw[0], dict) and "day" in raw[0]:
            yield "flat", raw
            return
        for i, row in enumerate(raw):
            if isinstance(row, dict):
                obs = row.get("observations") or row.get("daily") or row.get("rows")
                if obs:
                    yield str(row.get("seed", i)), obs
        return
    if isinstance(raw, dict):
        cases = raw.get("cases") or raw.get("runs") or []
        for i, row in enumerate(cases):
            obs = row.get("observations") or row.get("daily") or row.get("rows")
            if obs:
                yield str(row.get("seed", i)), obs


def normalize(rows):
    out = []
    for row in rows:
        if row.get("animals") is None:
            animals = 0
        else:
            animals = int(row["animals"])
        produced = 0.0 if row.get("produced_value") is None else float(row["produced_value"])
        collected = 0.0 if row.get("collected_value") is None else float(row["collected_value"])
        out.append(ScaleObservation(
            day=int(row["day"]), money=float(row["money"]), land=int(row["land"]),
            hands=int(row["hands"]), animals=animals,
            produced_value=produced, collected_value=collected,
        ))
    return out


def main():
    raw = json.loads(INPUT.read_text(encoding="utf-8"))
    cases = []
    all_windows = []
    all_obs = []
    for case_id, rows in iter_observation_sets(raw):
        obs = normalize(rows)
        windows = land_recovery_windows(obs, window_days=5)
        all_windows.extend(windows)
        all_obs.extend(obs)
        cases.append({
            "case": case_id,
            "windows": [w.__dict__ for w in windows],
        })

    estimate = estimate_land_window_return(all_obs, unit_cost=1.0, window_days=5)
    result = {
        "schema": "scale-chassis.land-recovery-window.v1",
        "window_days": 5,
        "causal_attribution": False,
        "case_count": len(cases),
        "window_count": len(all_windows),
        "unit_cost_placeholder": 1.0,
        "estimate_daily_collected_gain": estimate.mean_daily_return,
        "median_daily_collected_gain": estimate.median_daily_return,
        "cases": cases,
        "note": "This measures realized post-LAND flow only. It does not yet decide admission until the actual LAND cost/runway rule is wired.",
    }
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("LAND_RECOVERY_WINDOW " + json.dumps({k: result[k] for k in ("case_count","window_count","estimate_daily_collected_gain","median_daily_collected_gain")}, separators=(",", ":")))


if __name__ == "__main__":
    main()
