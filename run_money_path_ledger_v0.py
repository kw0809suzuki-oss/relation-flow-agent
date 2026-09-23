#!/usr/bin/env python3
import json, os
from pathlib import Path
from collections import Counter,defaultdict
from kaggle_environments import make
import export_scale_baseline_v1 as base
import g17_agent as combat

SEED=int(os.environ["BATTLE_SEED"]); SEAT=int(os.environ["BATTLE_SEAT"])
OPPONENT=base.OPPONENT
OUT=Path(f"money_path_ledger_v0_{SEED}.json")

def configure():
    base._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"]="1"
    os.environ["ORIGIN_CROP_COMMITMENT"]="0"
    for k in ["OUTER_MEANING_OPTION_PRESERVATION_DAY","OUTER_MEANING_REALIZABLE_CAPACITY_DAY","OUTER_MEANING_CONVERSION_PATH_DAY","OUTER_MEANING_GUIDED_CONVERSION_DAY"]:
        os.environ.pop(k,None)
    os.environ["OUTER_MEANING_OBJECTIVE_PRESSURE_DAY"]="14"
    for k in ["ORIGIN_EVALUATION_LENS","ORIGIN_MODEL_CANDIDATE_EVALUATION","ORIGIN_MODEL_CANDIDATE_COMPARISON","ORIGIN_MODEL_CANDIDATE_SELECTION","ORIGIN_MODEL_CANDIDATE_DIRECTION","ORIGIN_MODEL_SELECTION_GUIDED_GENERATION","ORIGIN_MODEL_SELECTION_TO_ACTION","ORIGIN_MODEL_DIRECTIONAL_STATE_READ"]:
        os.environ[k]="0"
    os.environ["ORIGIN_DIRECTION_CONTROL_MODE"]="none"
    os.environ["ORIGIN_ABSTRACTION_TRANSMISSION"]="1"
    os.environ["ORIGIN_GUIDANCE_MODE"]="objective_pressure_guidance"
    combat.set_probe_enabled(True); combat.set_attribution_enabled(True); combat.reset_telemetry()

def stock(obs):
    p=obs["private"]
    c=Counter()
    for k,v in (p.get("shed",{}) or {}).items():
        if isinstance(v,(int,float)): c[str(k)]+=v
    for inv in p.get("inventories",[]) or []:
        for k,v in (inv or {}).items():
            if isinstance(v,(int,float)): c[str(k)]+=v
    return dict(c)

def parse_market(action, prices):
    sells=Counter(); buys=Counter()
    sell_face=buy_face=0.0
    hire=land=0
    rows=[]
    for o in (action.get("market",[]) if isinstance(action,dict) else []) or []:
        if not isinstance(o,(list,tuple)) or not o:
            continue
        cmd=str(o[0]); item=None; qty=None; face=None
        if cmd=="HIRE":
            hire+=1
        elif cmd=="BUY_LAND":
            land+=1
        elif len(o)>=3 and isinstance(o[2],(int,float)):
            item=str(o[1]); qty=float(o[2])
            px=float(prices.get(item,0) or 0)
            face=px*qty
            if cmd=="SELL":
                sells[item]+=qty; sell_face+=face
            elif cmd in ("BUY_PRODUCT","BUY_SEED","BUY_ANIMAL"):
                buys[item]+=qty; buy_face+=face
        rows.append({"order":list(o),"face_value":face})
    return {
      "orders":rows,
      "sell_units":dict(sells),"buy_units":dict(buys),
      "sell_face_value":sell_face,"priced_buy_face_value":buy_face,
      "hire_count":hire,"buy_land_count":land
    }

def main():
    configure()
    observations=[]
    pending=None

    def wrapped(obs):
        nonlocal pending
        day=int(obs.get("day",0) or 0)
        me=obs["farms"][obs["player"]]
        now={
          "day":day,
          "money":float(me.get("money",0) or 0),
          "stock":stock(obs)
        }
        if pending is not None:
            pending["after_day"]=day
            pending["money_after"]=now["money"]
            pending["money_delta"]=now["money"]-pending["money_before"]
            pending["stock_after"]=now["stock"]
            released={}
            keys=set(pending["stock_before"])|set(now["stock"])|set(pending["market"]["sell_units"])|set(pending["market"]["buy_units"])
            for k in sorted(keys):
                before=float(pending["stock_before"].get(k,0) or 0)
                after=float(now["stock"].get(k,0) or 0)
                requested_sell=float(pending["market"]["sell_units"].get(k,0) or 0)
                requested_buy=float(pending["market"]["buy_units"].get(k,0) or 0)
                observed_drop=max(0.0,before-after)
                # Proxy only: concurrent harvest/use/place can affect stock.
                release_proxy=min(requested_sell, max(0.0, observed_drop+requested_buy))
                released[k]={
                  "before":before,"after":after,"delta":after-before,
                  "requested_sell":requested_sell,"requested_buy":requested_buy,
                  "observed_release_proxy":release_proxy
                }
            pending["stock_reconciliation"]=released
            pending["requested_sell_units_total"]=sum(pending["market"]["sell_units"].values())
            pending["observed_release_proxy_total"]=sum(x["observed_release_proxy"] for x in released.values())
            pending["priced_market_net_face"]=pending["market"]["sell_face_value"]-pending["market"]["priced_buy_face_value"]
            pending["money_residual_after_priced_market_face"]=pending["money_delta"]-pending["priced_market_net_face"]
            observations.append(pending)
            pending=None

        action=combat.agent(obs)
        if 10 <= day <= 15:
            prices=dict((obs.get("market",{}) or {}).get("prices",{}) or {})
            pending={
              "day":day,
              "money_before":now["money"],
              "stock_before":now["stock"],
              "market":parse_market(action,prices)
            }
        return action

    env=make("kaggriculture",configuration={"seed":SEED},debug=False)
    players=[OPPONENT,OPPONENT]; players[SEAT]=wrapped
    env.run(players)
    rewards=[float(s.reward) for s in env.state]

    byday=defaultdict(list)
    for x in observations:
        if 10 <= x["day"] <= 15:
            byday[x["day"]].append(x)

    days=[]
    for d in range(10,16):
        xs=byday.get(d,[])
        if not xs: continue
        days.append({
          "day":d,
          "money_start":xs[0]["money_before"],
          "money_end":xs[-1]["money_after"],
          "money_delta":xs[-1]["money_after"]-xs[0]["money_before"],
          "sell_face_value":sum(x["market"]["sell_face_value"] for x in xs),
          "priced_buy_face_value":sum(x["market"]["priced_buy_face_value"] for x in xs),
          "hire_count":sum(x["market"]["hire_count"] for x in xs),
          "buy_land_count":sum(x["market"]["buy_land_count"] for x in xs),
          "requested_sell_units":sum(x["requested_sell_units_total"] for x in xs),
          "observed_release_proxy_units":sum(x["observed_release_proxy_total"] for x in xs),
          "turn_money_residual_sum":sum(x["money_residual_after_priced_market_face"] for x in xs)
        })

    payload={
      "schema":"kaggriculture.money-path-ledger.v0",
      "seed":SEED,"seat":SEAT,
      "terminal":{"self":rewards[SEAT],"opponent":rewards[1-SEAT],"residual":rewards[1-SEAT]-rewards[SEAT]},
      "days":days,
      "turns":observations,
      "boundary":[
        "No direct settlement receipt is exposed.",
        "Observed release is a stock-change proxy and may include concurrent consumption/placement/harvest effects.",
        "HIRE and BUY_LAND are counted but intentionally not assigned assumed dollar costs.",
        "Money residual therefore contains unpriced costs and any settlement mismatch."
      ]
    }
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"seed":SEED,"self":rewards[SEAT],"opp":rewards[1-SEAT],"days":days},ensure_ascii=False))

if __name__=="__main__": main()
