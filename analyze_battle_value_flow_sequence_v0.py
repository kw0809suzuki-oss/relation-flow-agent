#!/usr/bin/env python3
import json,sys
from collections import defaultdict
from pathlib import Path

root=Path(sys.argv[1] if len(sys.argv)>1 else ".")
files=sorted(root.glob("**/battle_value_flow_sequence_v0_*.json"))
rows=[json.loads(p.read_text(encoding="utf-8")) for p in files]
if len(rows)!=5:raise SystemExit(f"expected 5 inputs, got {len(rows)}")
if any(r["audit"]["unmapped_relevant_events"]!=0 for r in rows):
    raise SystemExit("unmapped production events present")

PULSES={
 "pulse_A":{"lead_start":13,"lead_end":14,"cash_start":14,"cash_end":15},
 "pulse_B":{"lead_start":16,"lead_end":17,"cash_start":17,"cash_end":18},
}

def snap(row,day,hour=0):
    xs=[x for x in row["timeline"] if x["day"]==day and x["hour"]==hour]
    if not xs:raise KeyError((row["seed"],day,hour))
    return xs[0]

def prod_window(row,start_day,end_day):
    # [start_day h0, end_day h0): include events at start, exclude endpoint day h0.
    ev=[]
    for e in row["production_events"]:
        d=int(e["result_day"]);h=int(e["result_hour"])
        t=d*24+h
        if start_day*24 <= t < end_day*24:ev.append(e)
    return ev

def sell_window(row,start_day,end_day):
    ev=[]
    for e in row["sell_events"]:
        d=int(e["day"]);h=int(e["hour"]);t=d*24+h
        if start_day*24 <= t < end_day*24:ev.append(e)
    return ev

def side_sum(ev,seat,field):
    return sum(float(e.get(field,0) or 0) for e in ev if int(e["player"])==seat)

def by_item(ev,seat,field):
    out=defaultdict(float)
    for e in ev:
        if int(e["player"])==seat:
            out[str(e.get("item","UNKNOWN"))]+=float(e.get(field,0) or 0)
    return dict(sorted(out.items()))

cases=[]
for r in rows:
    seat=int(r["seat"]);opp=1-seat
    pc={}
    for name,p in PULSES.items():
        ls=snap(r,p["lead_start"]);le=snap(r,p["lead_end"])
        cs=snap(r,p["cash_start"]);ce=snap(r,p["cash_end"])
        pev_lead=prod_window(r,p["lead_start"],p["lead_end"])
        sev_lead=sell_window(r,p["lead_start"],p["lead_end"])
        pev_cash=prod_window(r,p["cash_start"],p["cash_end"])
        sev_cash=sell_window(r,p["cash_start"],p["cash_end"])
        pc[name]={
          "lead_interval":{
            "days":[p["lead_start"],p["lead_end"]],
            "committed_residual_change":le["residual"]["committed_production_mark"]-ls["residual"]["committed_production_mark"],
            "cash_residual_change":le["residual"]["cash"]-ls["residual"]["cash"],
            "output_mark":{
              "self":side_sum(pev_lead,seat,"event_price_mark"),
              "opponent":side_sum(pev_lead,opp,"event_price_mark"),
              "residual":side_sum(pev_lead,opp,"event_price_mark")-side_sum(pev_lead,seat,"event_price_mark"),
              "self_by_item":by_item(pev_lead,seat,"event_price_mark"),
              "opponent_by_item":by_item(pev_lead,opp,"event_price_mark"),
            },
            "sell_cash":{
              "self":side_sum(sev_lead,seat,"cash_delta"),
              "opponent":side_sum(sev_lead,opp,"cash_delta"),
              "residual":side_sum(sev_lead,opp,"cash_delta")-side_sum(sev_lead,seat,"cash_delta"),
              "self_by_item":by_item(sev_lead,seat,"cash_delta"),
              "opponent_by_item":by_item(sev_lead,opp,"cash_delta"),
            }
          },
          "cash_interval":{
            "days":[p["cash_start"],p["cash_end"]],
            "committed_residual_change":ce["residual"]["committed_production_mark"]-cs["residual"]["committed_production_mark"],
            "cash_residual_change":ce["residual"]["cash"]-cs["residual"]["cash"],
            "output_mark":{
              "self":side_sum(pev_cash,seat,"event_price_mark"),
              "opponent":side_sum(pev_cash,opp,"event_price_mark"),
              "residual":side_sum(pev_cash,opp,"event_price_mark")-side_sum(pev_cash,seat,"event_price_mark"),
              "self_by_item":by_item(pev_cash,seat,"event_price_mark"),
              "opponent_by_item":by_item(pev_cash,opp,"event_price_mark"),
            },
            "sell_cash":{
              "self":side_sum(sev_cash,seat,"cash_delta"),
              "opponent":side_sum(sev_cash,opp,"cash_delta"),
              "residual":side_sum(sev_cash,opp,"cash_delta")-side_sum(sev_cash,seat,"cash_delta"),
              "self_by_item":by_item(sev_cash,seat,"cash_delta"),
              "opponent_by_item":by_item(sev_cash,opp,"cash_delta"),
            }
          }
        }
    cases.append({"seed":r["seed"],"seat":seat,"pulses":pc})

def vals(pulse,phase,path):
    out=[]
    for c in cases:
        x=c["pulses"][pulse][phase]
        for k in path:x=x[k]
        out.append(float(x))
    return out

summary={}
for pulse in PULSES:
    summary[pulse]={}
    for phase in ("lead_interval","cash_interval"):
        summary[pulse][phase]={
          "committed_residual_change":vals(pulse,phase,["committed_residual_change"]),
          "cash_residual_change":vals(pulse,phase,["cash_residual_change"]),
          "output_mark_residual":vals(pulse,phase,["output_mark","residual"]),
          "sell_cash_residual":vals(pulse,phase,["sell_cash","residual"]),
        }

out={
 "schema":"kaggriculture.strong-origin-v2.battle-value-flow-sequence.aggregate.v0",
 "battle_count":5,
 "cases":cases,
 "summary":summary,
 "boundary":[
   "Two pulse pairs are compared on the same coordinates.",
   "Output mark is event-time displayed-price valuation of actual public production increments, not realized Cash.",
   "SELL is exact realized Cash.",
   "Temporal ordering is descriptive; no causal handoff is asserted."
 ]
}
Path("battle_value_flow_sequence_v0_result.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print("BATTLE_VALUE_FLOW_SEQUENCE_AGG "+json.dumps({"summary":summary},ensure_ascii=False,separators=(",",":")))
