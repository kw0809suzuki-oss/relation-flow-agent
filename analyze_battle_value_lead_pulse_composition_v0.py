#!/usr/bin/env python3
import json,sys
from pathlib import Path

root=Path(sys.argv[1] if len(sys.argv)>1 else ".")
files=sorted(root.glob("**/battle_value_lead_pulse_composition_v0_*.json"))
rows=[json.loads(p.read_text(encoding="utf-8")) for p in files]
if len(rows)!=5:raise SystemExit(f"expected 5 inputs, got {len(rows)}")

crops=["WHEAT","CARROT","TOMATO","STRAWBERRY","MELON"]
animals=["GOOSE","COW","SHEEP"]
pulses=["pulse_A_day13_to_14","pulse_B_day16_to_17"]

def mean(xs):return sum(xs)/len(xs)

summary={}
for p in pulses:
    summary[p]={
      "total_mark_change":[r["pulse_residual_change"][p]["total_mark"] for r in rows],
      "crop_total_mark_change":[r["pulse_residual_change"][p]["crop_total_mark"] for r in rows],
      "animal_total_mark_change":[r["pulse_residual_change"][p]["animal_total_mark"] for r in rows],
      "crop_mark_by_type":{c:[r["pulse_residual_change"][p]["crop_mark_by_type"][c] for r in rows] for c in crops},
      "animal_mark_by_type":{a:[r["pulse_residual_change"][p]["animal_mark_by_type"][a] for r in rows] for a in animals},
      "crop_count":{c:[r["pulse_residual_change"][p]["crop_count"][c] for r in rows] for c in crops},
      "animal_count":{a:[r["pulse_residual_change"][p]["animal_count"][a] for r in rows] for a in animals},
      "crop_potential_units":{c:[r["pulse_residual_change"][p]["crop_potential_units"][c] for r in rows] for c in crops},
      "animal_potential_units":{a:[r["pulse_residual_change"][p]["animal_potential_units"][a] for r in rows] for a in animals},
    }
    summary[p]["means"]={
      "total_mark_change":mean(summary[p]["total_mark_change"]),
      "crop_total_mark_change":mean(summary[p]["crop_total_mark_change"]),
      "animal_total_mark_change":mean(summary[p]["animal_total_mark_change"]),
      "crop_mark_by_type":{c:mean(summary[p]["crop_mark_by_type"][c]) for c in crops},
      "animal_mark_by_type":{a:mean(summary[p]["animal_mark_by_type"][a]) for a in animals},
      "crop_count":{c:mean(summary[p]["crop_count"][c]) for c in crops},
      "animal_count":{a:mean(summary[p]["animal_count"][a]) for a in animals},
      "crop_potential_units":{c:mean(summary[p]["crop_potential_units"][c]) for c in crops},
      "animal_potential_units":{a:mean(summary[p]["animal_potential_units"][a]) for a in animals},
    }

out={
  "schema":"kaggriculture.strong-origin-v2.battle-value-map.lead-pulse-composition.aggregate.v0",
  "battle_count":5,
  "cases":[{"seed":r["seed"],"seat":r["seat"],"terminal":r["terminal"]} for r in rows],
  "summary":summary,
  "boundary":[
    "Pulse A and Pulse B use identical public-State classifications and valuation basis.",
    "Similarity/difference is reported descriptively; no causal mechanism is inferred.",
    "No Action or internal policy layer is opened."
  ]
}
Path("battle_value_lead_pulse_composition_v0_result.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print("LEAD_PULSE_COMPOSITION_AGG "+json.dumps(summary,ensure_ascii=False,separators=(",",":")))
