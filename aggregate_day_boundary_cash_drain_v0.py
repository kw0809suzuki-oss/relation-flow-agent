#!/usr/bin/env python3
import glob,json,statistics,math
from pathlib import Path

rows=[json.loads(Path(p).read_text(encoding="utf-8"))
      for p in glob.glob("artifacts/**/day_boundary_cash_drain_v0_*.json",recursive=True)]
bs=[b for r in rows for b in r.get("boundaries",[])]

def mean(xs): return statistics.mean(xs) if xs else None
def corr(xs,ys):
    if len(xs)<2 or len(xs)!=len(ys): return None
    mx,my=mean(xs),mean(ys)
    num=sum((x-mx)*(y-my) for x,y in zip(xs,ys))
    dx=sum((x-mx)**2 for x in xs); dy=sum((y-my)**2 for y in ys)
    if dx<=0 or dy<=0: return None
    return num/math.sqrt(dx*dy)

empty=[b for b in bs if b.get("prior_turn_market_empty")]
nonempty=[b for b in bs if not b.get("prior_turn_market_empty")]
neg=[b for b in bs if b["money_delta"]<0]

payload={
 "schema":"kaggriculture.day-boundary-cash-drain.aggregate.v0",
 "cases":len(rows),
 "scale_check":{
   "baseline_absolute_mean_self":mean([r["terminal"]["self"] for r in rows]),
   "opponent_absolute_mean_self":mean([r["terminal"]["opponent"] for r in rows]),
   "mean_terminal_residual":mean([r["terminal"]["residual"] for r in rows]),
   "candidate_absolute_mean_self":None,
   "delta":None
 },
 "boundaries":len(bs),
 "negative_boundaries":len(neg),
 "negative_share":len(neg)/len(bs) if bs else None,
 "mean_money_delta_all":mean([b["money_delta"] for b in bs]),
 "mean_money_delta_market_empty":mean([b["money_delta"] for b in empty]),
 "mean_money_delta_market_nonempty":mean([b["money_delta"] for b in nonempty]),
 "market_empty_boundaries":len(empty),
 "market_nonempty_boundaries":len(nonempty),
 "corr_money_delta_hands_before":corr([b["hands_before"] for b in bs],[b["money_delta"] for b in bs]),
 "corr_money_delta_animals_before":corr([b["animals_before"] for b in bs],[b["money_delta"] for b in bs]),
 "corr_drain_hands_before":corr([b["hands_before"] for b in neg],[-b["money_delta"] for b in neg]),
 "corr_drain_animals_before":corr([b["animals_before"] for b in neg],[-b["money_delta"] for b in neg]),
 "per_day":[
   {
     "from_day":d,
     "n":len([b for b in bs if b["from_day"]==d]),
     "mean_money_delta":mean([b["money_delta"] for b in bs if b["from_day"]==d]),
     "mean_hands_before":mean([b["hands_before"] for b in bs if b["from_day"]==d]),
     "mean_animals_before":mean([b["animals_before"] for b in bs if b["from_day"]==d]),
     "market_empty_share":mean([1.0 if b["prior_turn_market_empty"] else 0.0 for b in bs if b["from_day"]==d])
   }
   for d in sorted(set(b["from_day"] for b in bs))
 ],
 "boundary":"Observed day-boundary association only; no mechanism label."
}
Path("day_boundary_cash_drain_v0_aggregate.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps(payload,ensure_ascii=False))
