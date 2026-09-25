#!/usr/bin/env python3
"""Aggregate NR-01 SCAN raw traces into one compact Evidence Packet."""
import json
import sys
from pathlib import Path

root = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
files = sorted(root.glob("**/nr01_scan_raw_*.json"))
if not files:
    raise SystemExit("no NR-01 raw inputs")

rows = [json.loads(p.read_text(encoding="utf-8")) for p in files]
rows.sort(key=lambda r: int(r["seed"]))

events = []
for r in rows:
    for e in r.get("scan_events", []):
        if e.get("qualifies"):
            x = dict(e)
            x["seed"] = int(r["seed"])
            x["seat"] = int(r["seat"])
            events.append(x)

events.sort(key=lambda e: (int(e["day"]), int(e["hour"]), int(e["seed"]), int(e["seat"])))
candidate = 1 if events else 0
selected = events[0] if events else None

support_cases = sorted({int(e["seed"]) for e in events})
event_count_by_seed = {}
for e in events:
    event_count_by_seed[str(e["seed"])] = event_count_by_seed.get(str(e["seed"]), 0) + 1

packet = {
    "schema": "kaggriculture.nr01-scan.evidence-packet.v0",
    "candidate": candidate,
    "current_identity": "Baseline + WR-02",
    "battle_count": len(rows),
    "support": {
        "cases_with_candidate": len(support_cases),
        "support_seeds": support_cases,
        "qualifying_events_total": len(events),
        "qualifying_events_by_seed": event_count_by_seed,
    },
    "boundary": selected["boundary"] if selected else None,
    "front": selected["front"] if selected else None,
    "back": selected["back"] if selected else None,
    "world": selected["world"] if selected else None,
    "previous_turns": selected["previous_turns"] if selected else [],
    "state_t1": selected.get("state_t1") if selected else None,
    "delta_state": selected.get("delta_state") if selected else None,
    "representative": {
        "seed": selected["seed"],
        "seat": selected["seat"],
        "day": selected["day"],
        "hour": selected["hour"],
        "same_position": selected["same_position"],
        "unit_indices": selected["unit_indices"],
    } if selected else None,
    "guard": selected["guard"] if selected else {
        "resource_state_present": False,
        "resource_generated_or_acquired_by_current": False,
        "current_productive_action_generated": False,
        "world_failure_observed": False,
        "alternate_empty_capacity_observed": False,
    },
    "decision_boundary": {
        "scan_result_only": True,
        "candidate_is_not_adoption": True,
        "close_scope_rule": "Close target equals the exact transform exercised by an A/B test.",
        "forbidden_broadenings": [
            "Day4 planting as a whole",
            "Available Resource -> Productive State as a whole",
            "unused Resource interpreted as Current intent",
        ],
    },
    "raw_artifacts": [p.name for p in files],
}

Path("nr01_scan_fresh10.json").write_text(
    json.dumps(packet, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
)

if selected:
    reasons = selected["world"].get("failure_reasons", {})
    md = f"""# NR-01 SCAN v0 — Evidence Packet

**candidate:** 1  
**boundary:** \`{selected["boundary"]}\`  
**support:** {len(support_cases)}/{len(rows)} battles, {len(events)} qualifying events

## Representative event

- seed: {selected["seed"]}
- seat: {selected["seat"]}
- turn: Day{selected["day"]} h{selected["hour"]}
- same position: {selected["same_position"]}
- unit indices: {selected["unit_indices"]}

## Front — Current Action

- PLANT requests: {selected["front"]["plant_requests"]}
- requests by crop: \`{json.dumps(selected["front"]["requests_by_crop"], ensure_ascii=False)}\`

## Back — Resource / World state

- workers: {selected["back"]["workers"]}
- empty tiles: {selected["back"]["empty_tiles"]}
- alternate empty tiles: {selected["back"]["alternate_empty_tiles"]}
- available seed: \`{json.dumps(selected["back"]["available_seed"], ensure_ascii=False)}\`
- seed sufficient for requests: {selected["back"]["seed_sufficient_for_requests"]}
- Current seed acquisition confirmed: {selected["back"]["resource_origin_confirmed"]}
- prior Current seed acquisition: `{json.dumps(selected["back"]["prior_current_seed_acquisition"], ensure_ascii=False)}`
- target was empty at State_t: {selected["back"]["target_was_empty"]}

## World execution

- success: {selected["world"]["success"]}
- failed: {selected["world"]["failed"]}
- failure reasons: \`{json.dumps(reasons, ensure_ascii=False)}\`

## Previous 3 turns

\`\`\`json
{json.dumps(selected["previous_turns"], ensure_ascii=False, indent=2)}
\`\`\`

## State transition

\`\`\`json
{json.dumps(selected.get("delta_state"), ensure_ascii=False, indent=2)}
\`\`\`

## Guard

\`\`\`json
{json.dumps(selected["guard"], ensure_ascii=False, indent=2)}
\`\`\`

## Scope contract

This packet identifies one candidate boundary only. It does not adopt a repair.

**Close target = the exact transform exercised by an A/B test.**

A rejected repair must not automatically close:
- Day4 planting as a whole
- Available Resource -> Productive State as a whole
- any Resource for which Current usage intent was not directly observed
"""
else:
    md = f"""# NR-01 SCAN v0 — Evidence Packet

**candidate:** 0  
**support:** 0/{len(rows)} battles

No event in this fresh10 satisfied all SCAN guards at once:

1. Current generated multiple productive PLANT actions from the same position.
2. Seed stock was sufficient for those requests.
3. Another empty unlocked tile existed at State_t.
4. World execution produced \`TARGET_TILE_NOT_EMPTY\`.

This is a SCAN-surface result only. It does not close Available Resource -> Productive State globally.

## Scope contract

**Close target = the exact transform exercised by an A/B test.**
"""

Path("nr01_evidence_packet.md").write_text(md, encoding="utf-8")

print(
    "NR01_SCAN_AGG "
    + json.dumps(
        {
            "candidate": candidate,
            "battle_count": len(rows),
            "cases_with_candidate": len(support_cases),
            "qualifying_events_total": len(events),
            "representative": packet["representative"],
            "boundary": packet["boundary"],
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )
)
