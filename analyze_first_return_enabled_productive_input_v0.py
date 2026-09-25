#!/usr/bin/env python3
import glob,json
from collections import Counter,defaultdict
from pathlib import Path

def mean(xs): return sum(xs)/len(xs) if xs else None

paths=sorted(Path(p) for p in glob.glob("return-input-artifacts/**/first_return_enabled_productive_input_v0_*.json",recursive=True))
if len(paths)!=10: raise SystemExit(f"Expected 10 artifacts, found {len(paths)}")
raws=[json.loads(p.read_text(encoding="utf-8")) for p in paths]

rows=[]
for r in raws:
    seat=int(r["seat"])
    s=r["first_by_player"][str(seat)]
    o=r["first_by_player"][str(1-seat)]
    rows.append({"seed":r["seed"],"seat":seat,"self":s,"opponent":o,"terminal":r["terminal"]})

def sig(e):
    if not e:return None
    return f'D{e["day"]}h{e["hour"]}:{e["op"]}:{e.get("item") or "-"}'

opp=[r["opponent"] for r in rows if r["opponent"]]
selfs=[r["self"] for r in rows if r["self"]]
opp_sigs=Counter(sig(e) for e in opp)
self_sigs=Counter(sig(e) for e in selfs)
opp_ops=Counter((e["op"],e.get("item")) for e in opp)
self_ops=Counter((e["op"],e.get("item")) for e in selfs)

payload={
 "schema":"kaggriculture.first-return-enabled-productive-input.result.v0",
 "battle_count":10,
 "opponent":{
   "found_cases":len(opp),
   "first_event_signature_frequency":dict(opp_sigs),
   "first_event_op_item_frequency":{f"{k[0]}:{k[1]}":v for k,v in opp_ops.items()},
   "mean_day":mean([e["day"] for e in opp]),
   "mean_hour":mean([e["hour"] for e in opp]),
   "mean_cost":mean([e["cost"] for e in opp]),
   "mean_prior_sell_cash":mean([e["prior_sell_cash"] for e in opp]),
   "mean_cash_without_prior_sell":mean([e["cash_without_prior_sell"] for e in opp]),
 },
 "self":{
   "found_cases":len(selfs),
   "first_event_signature_frequency":dict(self_sigs),
   "first_event_op_item_frequency":{f"{k[0]}:{k[1]}":v for k,v in self_ops.items()},
   "mean_day":mean([e["day"] for e in selfs]),
   "mean_hour":mean([e["hour"] for e in selfs]),
 },
 "cases":rows,
 "boundary":[
   "This identifies the first productive order whose affordability depends on prior realized SELL cash on the actual outflow path.",
   "It does not yet prove that this exact order causes the next Production separator.",
   "The next step is to connect only a repeated opponent event to a later public productive asset/production event."
 ]
}
Path("first_return_enabled_productive_input_v0_result.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print("FIRST_RETURN_ENABLED_PRODUCTIVE_INPUT_RESULT "+json.dumps(payload,ensure_ascii=False,separators=(",",":")))
