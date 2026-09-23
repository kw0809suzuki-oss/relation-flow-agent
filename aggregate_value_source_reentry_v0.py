#!/usr/bin/env python3
import glob,json,statistics
from pathlib import Path
from collections import defaultdict,Counter

rows=[json.loads(Path(p).read_text(encoding="utf-8"))
      for p in glob.glob("artifacts/**/value_source_reentry_v0_*.json",recursive=True)]

def mean(xs): return statistics.mean(xs) if xs else None
byday=defaultdict(list)
for r in rows:
    for d in r.get("days",[]): byday[d["day"]].append(d)

summary=[]
for day in sorted(byday):
    xs=byday[day]
    self_items=Counter(); self_face=Counter()
    opp_crops=Counter(); opp_animals=Counter()
    self_crops=Counter(); self_animals=Counter()
    for x in xs:
        for k,v in x.get("self_sell_items",{}).items():
            self_items[k]+=v.get("units",0); self_face[k]+=v.get("face_value",0)
        self_crops.update(x.get("self_comp",{}).get("crops",{}))
        self_animals.update(x.get("self_comp",{}).get("animals",{}))
        opp_crops.update(x.get("opp_comp",{}).get("crops",{}))
        opp_animals.update(x.get("opp_comp",{}).get("animals",{}))
    summary.append({
      "day":day,"n":len(xs),
      "mean_self_money":mean([x["self_money"] for x in xs]),
      "mean_opp_money":mean([x["opp_money"] for x in xs]),
      "mean_money_gap":mean([x["money_gap"] for x in xs]),
      "mean_money_gap_change":mean([x["money_gap_change"] for x in xs if x["money_gap_change"] is not None]),
      "mean_self_sell_face_total":mean([x["self_sell_face_total"] for x in xs]),
      "mean_self_sell_units_total":mean([x["self_sell_units_total"] for x in xs]),
      "self_sell_face_by_item_total":dict(self_face),
      "self_sell_units_by_item_total":dict(self_items),
      "mean_self_crop_tiles":mean([x["self_comp"]["crop_tiles"] for x in xs]),
      "mean_self_animal_tiles":mean([x["self_comp"]["animal_tiles"] for x in xs]),
      "mean_opp_crop_tiles":mean([x["opp_comp"]["crop_tiles"] for x in xs]),
      "mean_opp_animal_tiles":mean([x["opp_comp"]["animal_tiles"] for x in xs]),
      "self_crop_composition_total":dict(self_crops),
      "self_animal_composition_total":dict(self_animals),
      "opp_crop_composition_total":dict(opp_crops),
      "opp_animal_composition_total":dict(opp_animals)
    })

valid=[x for x in summary if x["mean_money_gap_change"] is not None]
largest=max(valid,key=lambda x:x["mean_money_gap_change"]) if valid else None

payload={
 "schema":"kaggriculture.value-source-reentry.aggregate.v0",
 "cases":len(rows),
 "scale_check":{
   "baseline_absolute_mean_self":mean([r["terminal"]["self"] for r in rows]),
   "opponent_absolute_mean_self":mean([r["terminal"]["opponent"] for r in rows]),
   "mean_terminal_residual":mean([r["terminal"]["residual"] for r in rows]),
   "candidate_absolute_mean_self":None,
   "delta":None
 },
 "largest_mean_cash_gap_expansion_day":largest["day"] if largest else None,
 "largest_mean_cash_gap_expansion":largest["mean_money_gap_change"] if largest else None,
 "day_summary":summary,
 "boundary":"Opponent private stock/SELL remains unobserved."
}
Path("value_source_reentry_v0_aggregate.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps({"cases":len(rows),"scale_check":payload["scale_check"],"largest_day":payload["largest_mean_cash_gap_expansion_day"],"largest_gap_change":payload["largest_mean_cash_gap_expansion"]},ensure_ascii=False))
