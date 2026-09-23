#!/usr/bin/env python3
import glob,json,statistics
from pathlib import Path

rows=[json.loads(Path(p).read_text(encoding="utf-8"))
      for p in glob.glob("artifacts/**/hire_settlement_cost_v0_*.json",recursive=True)]

turns=[t for r in rows for t in r.get("turns",[])]
settled=[t for t in turns if t.get("hire_settlement_proxy")]
unsettled=[t for t in turns if not t.get("hire_settlement_proxy")]

def mean(xs): return statistics.mean(xs) if xs else None

payload={
 "schema":"kaggriculture.hire-settlement-cost.aggregate.v0",
 "cases":len(rows),
 "scale_check":{
   "baseline_absolute_mean_self":mean([r["terminal"]["self"] for r in rows]),
   "opponent_absolute_mean_self":mean([r["terminal"]["opponent"] for r in rows]),
   "mean_terminal_residual":mean([r["terminal"]["residual"] for r in rows]),
   "candidate_absolute_mean_self":None,
   "delta":None
 },
 "hire_request_turns":len(turns),
 "settlement_proxy_turns":len(settled),
 "unsettled_request_turns":len(unsettled),
 "settled":{
   "mean_hands_delta":mean([x["hands_delta"] for x in settled]),
   "mean_money_delta":mean([x["money_delta"] for x in settled]),
   "mean_priced_market_net_face":mean([x["priced_market_net_face"] for x in settled]),
   "mean_money_residual":mean([x["money_residual_after_priced_market_face"] for x in settled])
 },
 "unsettled":{
   "mean_hands_delta":mean([x["hands_delta"] for x in unsettled]),
   "mean_money_delta":mean([x["money_delta"] for x in unsettled]),
   "mean_priced_market_net_face":mean([x["priced_market_net_face"] for x in unsettled]),
   "mean_money_residual":mean([x["money_residual_after_priced_market_face"] for x in unsettled])
 },
 "per_seed":[{"seed":r["seed"],**r.get("summary",{})} for r in sorted(rows,key=lambda x:x["seed"])],
 "boundary":"HIRE settlement proxy only; no assumed unit price."
}
Path("hire_settlement_cost_v0_aggregate.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps(payload,ensure_ascii=False))
