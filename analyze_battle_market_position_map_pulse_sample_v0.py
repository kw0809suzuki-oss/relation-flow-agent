#!/usr/bin/env python3
import json,sys
from pathlib import Path

root=Path(sys.argv[1] if len(sys.argv)>1 else ".")
files=sorted(root.glob("**/battle_market_position_map_v0_*_seat*.json"))
rows=[json.loads(p.read_text(encoding="utf-8")) for p in files]
if len(rows)!=5:raise SystemExit(f"expected 5 inputs, got {len(rows)}")
if any(any(abs(float(v["error"]))>1e-9 for v in r["cash_validation"]) for r in rows):
    raise SystemExit("cash validation failed")

PRODUCTS=("WHEAT","CARROT","TOMATO","STRAWBERRY","MELON","EGG","MILK","WOOL","FERTILIZER")
WINDOWS={
 "A_lead":(13,14),
 "A_response":(14,15),
 "B_lead":(16,17),
 "B_response":(17,18),
}

def state(r,day,hour=0):
    xs=[x for x in r["timeline"] if int(x["day"])==day and int(x["hour"])==hour]
    if not xs:raise KeyError((r["seed"],day,hour))
    return xs[0]

def sells(r,start_day,end_day,player,item):
    return [
      e for e in r["sell_events"]
      if int(e["player"])==player and e.get("item")==item
      and start_day*24 <= int(e["day"])*24+int(e["hour"]) < end_day*24
    ]

cases=[]
for r in rows:
    seat=int(r["seat"]);opp=1-seat
    c={"seed":r["seed"],"seat":seat,"terminal":r["terminal"],"windows":{}}
    for name,(d0,d1) in WINDOWS.items():
        s0=state(r,d0);s1=state(r,d1)
        w={
          "start_market":{},
          "end_market":{},
          "self":{},
          "opponent":{},
          "cash_state_change":{
            "self":s1["self"]["cash"]-s0["self"]["cash"],
            "opponent":s1["opponent"]["cash"]-s0["opponent"]["cash"]
          }
        }
        for item in PRODUCTS:
            w["start_market"][item]={
              "inventory":s0["market"]["inventory"][item],
              "price":s0["market"]["price"][item]
            }
            w["end_market"][item]={
              "inventory":s1["market"]["inventory"][item],
              "price":s1["market"]["price"][item]
            }
            for label,pidx in (("self",seat),("opponent",opp)):
                ev=sells(r,d0,d1,pidx,item)
                units=len(ev)
                cash=sum(float(e["cash_delta"]) for e in ev)
                w[label][item]={
                  "start_sellable_shed":s0[label]["sellable_shed"][item],
                  "end_sellable_shed":s1[label]["sellable_shed"][item],
                  "start_carried_not_sellable":s0[label]["carried_not_sellable"][item],
                  "sell_units":units,
                  "sell_cash":cash,
                  "realized_price_mean":(cash/units if units else None),
                  "realized_prices":[float(e["price"]) for e in ev]
                }
        c["windows"][name]=w
    cases.append(c)

def vec(window,side,item,key):
    return [c["windows"][window][side][item][key] for c in cases]

def sum_products(c,window,side,key):
    return sum(float(c["windows"][window][side][item][key] or 0) for item in PRODUCTS)

summary={}
for win in WINDOWS:
    summary[win]={
      "cases":[{
        "seed":c["seed"],
        "self_sell_units":int(sum_products(c,win,"self","sell_units")),
        "opponent_sell_units":int(sum_products(c,win,"opponent","sell_units")),
        "self_sell_cash":sum_products(c,win,"self","sell_cash"),
        "opponent_sell_cash":sum_products(c,win,"opponent","sell_cash"),
        "sell_cash_residual":sum_products(c,win,"opponent","sell_cash")-sum_products(c,win,"self","sell_cash"),
        "self_cash_state_change":c["windows"][win]["cash_state_change"]["self"],
        "opponent_cash_state_change":c["windows"][win]["cash_state_change"]["opponent"],
        "cash_state_change_residual":c["windows"][win]["cash_state_change"]["opponent"]-c["windows"][win]["cash_state_change"]["self"]
      } for c in cases],
      "by_item":{
        item:{
          "self_sell_units":vec(win,"self",item,"sell_units"),
          "opponent_sell_units":vec(win,"opponent",item,"sell_units"),
          "self_sell_cash":vec(win,"self",item,"sell_cash"),
          "opponent_sell_cash":vec(win,"opponent",item,"sell_cash"),
          "self_start_shed":vec(win,"self",item,"start_sellable_shed"),
          "opponent_start_shed":vec(win,"opponent",item,"start_sellable_shed"),
          "self_realized_price_mean":vec(win,"self",item,"realized_price_mean"),
          "opponent_realized_price_mean":vec(win,"opponent",item,"realized_price_mean")
        } for item in PRODUCTS
      }
    }

out={
 "schema":"kaggriculture.battle-market-position-map.pulse-sample.v0",
 "market_schedule_id":"MSS-0001",
 "battle_count":5,
 "products":list(PRODUCTS),
 "cases":cases,
 "summary":summary,
 "boundary":[
   "All five Battles use the same fixed Market State Schedule.",
   "All public SELL-able PRODUCTS are included in total SELL units and Cash.",
   "SELL cash is exact realized Cash from successful unit executions.",
   "Cash state change also includes purchases/HIRE/LAND in the interval and is therefore not equated to SELL cash.",
   "No item-level output-to-sale identity is asserted.",
   "No causal, profitability, Candidate, or policy conclusion."
 ]
}
Path("battle_market_position_map_pulse_sample_v0_result.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print("BATTLE_MARKET_PULSE_SAMPLE "+json.dumps({"summary":summary},ensure_ascii=False,separators=(",",":")))
