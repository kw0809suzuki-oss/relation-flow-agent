#!/usr/bin/env python3
import glob,json
from collections import Counter
from pathlib import Path

def mean(xs): return sum(xs)/len(xs) if xs else None
paths=sorted(Path(p) for p in glob.glob("generated-return-bridge-artifacts/**/first_generated_return_input_bridge_v0_*.json",recursive=True))
if len(paths)!=10: raise SystemExit(f"Expected 10 artifacts, found {len(paths)}")
raws=[json.loads(p.read_text(encoding="utf-8")) for p in paths]
rows=[]
for r in raws:
    seat=int(r["seat"])
    rows.append({"seed":r["seed"],"seat":seat,"self":r["first_by_player"][str(seat)],
                 "opponent":r["first_by_player"][str(1-seat)],"terminal":r["terminal"]})
def sig(e):
    if not e:return None
    return f'D{e["day"]}h{e["hour"]}:{e["op"]}:{e.get("item") or "-"}'
opp=[x["opponent"] for x in rows if x["opponent"]]
sel=[x["self"] for x in rows if x["self"]]
payload={
 "schema":"kaggriculture.first-generated-return-input-bridge.result.v0",
 "battle_count":10,
 "opponent":{
   "found_cases":len(opp),
   "signature_frequency":dict(Counter(sig(e) for e in opp)),
   "op_item_frequency":dict(Counter(f'{e["op"]}:{e.get("item")}' for e in opp)),
   "mean_day":mean([e["day"] for e in opp]),
   "mean_hour":mean([e["hour"] for e in opp]),
   "mean_generated_return_cash_before":mean([e["generated_return_cash_before"] for e in opp]),
   "mean_cash_without_generated_return":mean([e["cash_without_generated_return"] for e in opp]),
   "mean_cost":mean([e["cost"] for e in opp]),
 },
 "self":{
   "found_cases":len(sel),
   "signature_frequency":dict(Counter(sig(e) for e in sel)),
   "op_item_frequency":dict(Counter(f'{e["op"]}:{e.get("item")}' for e in sel)),
 },
 "cases":rows,
 "boundary":[
   "Only generated non-WHEAT realized SELL cash with zero initial stock is removed in the affordability counterfactual.",
   "A repeated event is a candidate connection point, not yet a WR-03 trigger.",
   "Production consequence must be verified separately before any intervention."
 ]}
Path("first_generated_return_input_bridge_v0_result.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print("FIRST_GENERATED_RETURN_INPUT_BRIDGE_RESULT "+json.dumps(payload,ensure_ascii=False,separators=(",",":")))
