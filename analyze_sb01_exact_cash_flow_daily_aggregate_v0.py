#!/usr/bin/env python3
import json,sys
from pathlib import Path

DAYS=range(30)
FOCUS=("SELL:STRAWBERRY","SELL:WOOL","SELL:MELON","SELL:MILK","SELL:FERTILIZER","SELL:WHEAT","BUY_PRODUCT:WHEAT")

def mean(xs): return sum(xs)/len(xs) if xs else 0.0

root=Path(sys.argv[1] if len(sys.argv)>1 else ".")
files=sorted(root.glob("sb01_exact_cash_flow_daily_*.json"))
if not files: files=sorted(root.glob("**/sb01_exact_cash_flow_daily_*.json"))
rows=[json.loads(p.read_text(encoding="utf-8")) for p in files]
if not rows: raise SystemExit("No daily cash files")
bad=[r["seed"] for r in rows if r["self"]["error"]!=0 or r["opponent"]["error"]!=0]
if bad: raise SystemExit(f"Non-zero reconstruction error: {bad}")

def v(r,side,day,key):
    return float((r[side].get("daily_ledger",{}).get(str(day),{}) or {}).get(key,0))

daily={}
cum={k:0.0 for k in FOCUS}
cum_nonwheat=0.0
cum_net=0.0
for day in DAYS:
    entry={"keys":{}}
    for k in FOCUS:
        sv=[v(r,"self",day,k) for r in rows]
        ov=[v(r,"opponent",day,k) for r in rows]
        gap=mean([o-s for s,o in zip(sv,ov)])
        cum[k]+=gap
        entry["keys"][k]={
            "self_mean":mean(sv),
            "opponent_mean":mean(ov),
            "daily_gap_opponent_minus_self":gap,
            "cumulative_gap":cum[k]
        }

    nonwheat_keys=("SELL:STRAWBERRY","SELL:WOOL","SELL:MELON","SELL:MILK","SELL:FERTILIZER")
    nw=sum(entry["keys"][k]["daily_gap_opponent_minus_self"] for k in nonwheat_keys)
    cum_nonwheat+=nw

    # Full net realized Cash flow for the day.
    s_net=[];o_net=[]
    for r in rows:
        sl=(r["self"].get("daily_ledger",{}).get(str(day),{}) or {})
        ol=(r["opponent"].get("daily_ledger",{}).get(str(day),{}) or {})
        s_net.append(sum(float(x) for x in sl.values()))
        o_net.append(sum(float(x) for x in ol.values()))
    net_gap=mean([o-s for s,o in zip(s_net,o_net)])
    cum_net+=net_gap
    entry["nonwheat_sales_gap"]=nw
    entry["cumulative_nonwheat_sales_gap"]=cum_nonwheat
    entry["net_cashflow_gap"]=net_gap
    entry["cumulative_net_cashflow_gap"]=cum_net
    daily[str(day)]=entry

terminal_gap=mean([r["opponent"]["actual_terminal"]-r["self"]["actual_terminal"] for r in rows])

def first_cross(field,target):
    for d in DAYS:
        if daily[str(d)][field] >= target:
            return d
    return None

milestones={}
for frac in (0.25,0.5,0.75,1.0):
    milestones[str(frac)]={
      "terminal_gap_target":terminal_gap*frac,
      "first_day_cumulative_net_gap_crosses":first_cross("cumulative_net_cashflow_gap",terminal_gap*frac),
      "first_day_cumulative_nonwheat_sales_gap_crosses":first_cross("cumulative_nonwheat_sales_gap",terminal_gap*frac),
    }

out={
 "schema":"kaggriculture.sb01.exact-cash-flow-daily-aggregate.v0",
 "battle_count":len(rows),
 "terminal_gap":terminal_gap,
 "daily":daily,
 "milestones":milestones,
 "boundary":[
   "All daily ledgers are exact realized Cash deltas and every case reconstructs terminal Cash with zero error.",
   "Cumulative gaps are opponent minus self.",
   "Non-WHEAT sales gap includes STRAWBERRY, WOOL, MELON, MILK and FERTILIZER only.",
   "This localizes realized Cash formation in time; it does not assign causal intervention value."
 ]
}
Path("sb01_exact_cash_flow_daily_aggregate_v0.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
compact={
 "battle_count":len(rows),"terminal_gap":terminal_gap,"milestones":milestones,
 "days":{str(d):{
   "nonwheat_sales_gap":daily[str(d)]["nonwheat_sales_gap"],
   "cum_nonwheat":daily[str(d)]["cumulative_nonwheat_sales_gap"],
   "net_gap":daily[str(d)]["net_cashflow_gap"],
   "cum_net":daily[str(d)]["cumulative_net_cashflow_gap"],
   "strawberry":daily[str(d)]["keys"]["SELL:STRAWBERRY"]["daily_gap_opponent_minus_self"],
   "wool":daily[str(d)]["keys"]["SELL:WOOL"]["daily_gap_opponent_minus_self"],
   "melon":daily[str(d)]["keys"]["SELL:MELON"]["daily_gap_opponent_minus_self"],
   "milk":daily[str(d)]["keys"]["SELL:MILK"]["daily_gap_opponent_minus_self"],
 } for d in DAYS}
}
print("SB01_EXACT_CASH_FLOW_DAILY_AGG "+json.dumps(compact,ensure_ascii=False,separators=(",",":")))
