#!/usr/bin/env python3
"""Bundle Flow Gate Effect Boundary Observer v1.

Replays the 30 fresh cases used by v0 evaluation:
fresh10 seeds 4122-4131 + fresh20 seeds 4142-4161, alternating seats.
For each same-seed/same-seat pair, extract:
gate suppression events -> first self diff -> first market diff -> first opponent diff -> terminal.
Descriptive only; no new policy rule.
"""
import json, os
from collections import Counter
from kaggle_environments import make
import export_scale_baseline_v1 as base
import whole_flow_control_agent as agent

OPPONENT=base.OPPONENT
CASES=tuple((s,(s-4122)%2) for s in list(range(4122,4132))+list(range(4142,4162)))
PRODUCTS=("WHEAT","MILK","FERTILIZER","STRAWBERRY","MELON","WOOL","EGG")

def product_stock(obs):
    p=obs.get("private",{}) or {}
    stores=[p.get("shed",{}) or {}]+list(p.get("inventories",[]) or [])
    q=Counter()
    for st in stores:
        if isinstance(st,dict):
            for k,v in st.items():
                if isinstance(v,(int,float)): q[k]+=float(v)
    return {k:q.get(k,0.0) for k in PRODUCTS}

def snap(obs, action, turn, suppressed):
    p=int(obs["player"]); me=obs["farms"][p]; opp=obs["farms"][1-p]
    market=obs.get("market",{}) or {}
    return {
      "turn":turn,"day":int(obs.get("day",0)),
      "self_money":float(me.get("money",0)),"opp_money":float(opp.get("money",0)),
      "self_hands":len(me.get("hands",[])),"self_land":len(me.get("unlocked_quadrants",[])),
      "self_cows":sum(1 for a in (me.get("animals",[]) or []) if isinstance(a,dict) and a.get("type")=="COW"),
      "opp_hands":len(opp.get("hands",[])),"opp_land":len(opp.get("unlocked_quadrants",[])),
      "opp_cows":sum(1 for a in (opp.get("animals",[]) or []) if isinstance(a,dict) and a.get("type")=="COW"),
      "stock":product_stock(obs),
      "market_prices":{k:market.get("prices",{}).get(k) for k in PRODUCTS},
      "market_inventory":{k:market.get("inventory",{}).get(k) for k in PRODUCTS},
      "action":action,
      "gate_suppressed":bool(suppressed),
    }

def play(seed,seat,enabled):
    base._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"]="1" if enabled else "0"
    agent.reset_telemetry()
    env=make("kaggriculture",configuration={"seed":seed},debug=False)
    rows=[]; turn=0; prev_supp=0
    def observed(obs):
        nonlocal turn,prev_supp
        action=agent.agent(obs)
        t=agent.get_telemetry()
        cur=t.get("bundle_flow_v0_suppressed_expansions",0)
        rows.append(snap(obs,action,turn,cur>prev_supp))
        prev_supp=cur; turn+=1
        return action
    players=[OPPONENT,OPPONENT]; players[seat]=observed
    env.run(players)
    rewards=[float(s.reward) for s in env.state]
    return {"terminal_self":rewards[seat],"terminal_opp":rewards[1-seat],
            "terminal_margin":rewards[seat]-rewards[1-seat],"trace":rows,
            "suppressed_total":prev_supp}

def neq(a,b,tol=1e-9):
    if isinstance(a,(int,float)) and isinstance(b,(int,float)): return abs(float(a)-float(b))>tol
    return a!=b

def first_diff(bt,ct,key):
    n=min(len(bt),len(ct))
    for i in range(n):
        if neq(bt[i][key],ct[i][key]): return i
    return None

def first_dict_diff(bt,ct,key):
    n=min(len(bt),len(ct))
    for i in range(n):
        if bt[i][key]!=ct[i][key]: return i
    return None

def row_at(bt,ct,i):
    if i is None: return None
    b=bt[i]; c=ct[i]
    return {"turn":i,"day":c["day"],
      "baseline":{"self_money":b["self_money"],"opp_money":b["opp_money"],"self_hands":b["self_hands"],"self_land":b["self_land"],"self_cows":b["self_cows"],"stock":b["stock"],
                  "market_prices":b["market_prices"],"market_inventory":b["market_inventory"],"action":b["action"]},
      "control":{"self_money":c["self_money"],"opp_money":c["opp_money"],"self_hands":c["self_hands"],"self_land":c["self_land"],"self_cows":c["self_cows"],"stock":c["stock"],
                 "market_prices":c["market_prices"],"market_inventory":c["market_inventory"],"action":c["action"]}}

def analyze(seed,seat):
    b=play(seed,seat,False); c=play(seed,seat,True)
    bt,ct=b["trace"],c["trace"]
    self_i=first_diff(bt,ct,"self_money")
    opp_i=first_diff(bt,ct,"opp_money")
    price_i=first_dict_diff(bt,ct,"market_prices")
    inv_i=first_dict_diff(bt,ct,"market_inventory")
    market_candidates=[i for i in (price_i,inv_i) if i is not None]
    market_i=min(market_candidates) if market_candidates else None
    action_i=first_dict_diff(bt,ct,"action")
    gate_events=[r["turn"] for r in ct if r["gate_suppressed"]]
    first_gate=gate_events[0] if gate_events else None
    sd=c["terminal_self"]-b["terminal_self"]
    md=c["terminal_margin"]-b["terminal_margin"]
    return {
      "seed":seed,"seat":seat,
      "class":"improved" if sd>0 else "worsened" if sd<0 else "equal",
      "self_diff":sd,"opp_diff":c["terminal_opp"]-b["terminal_opp"],"margin_diff":md,
      "baseline_terminal":{"self":b["terminal_self"],"opp":b["terminal_opp"],"margin":b["terminal_margin"]},
      "control_terminal":{"self":c["terminal_self"],"opp":c["terminal_opp"],"margin":c["terminal_margin"]},
      "suppressed_total":c["suppressed_total"],"first_gate_turn":first_gate,
      "first_action_diff":row_at(bt,ct,action_i),
      "first_self_diff":row_at(bt,ct,self_i),
      "first_market_diff":row_at(bt,ct,market_i),
      "first_opponent_diff":row_at(bt,ct,opp_i),
      "gate_events":gate_events,
      "pre_first_action_diff":row_at(bt,ct,action_i-1 if action_i is not None and action_i>0 else None),
    }

def summarize(rows,cls):
    xs=[r for r in rows if r["class"]==cls]
    def avg(k):
        return sum(r[k] for r in xs)/len(xs) if xs else None
    def avgturn(field):
        vals=[r[field]["turn"] for r in xs if r[field] is not None]
        return sum(vals)/len(vals) if vals else None
    return {
      "count":len(xs),"mean_self_diff":avg("self_diff"),"mean_opp_diff":avg("opp_diff"),
      "mean_margin_diff":avg("margin_diff"),"mean_suppressed_total":avg("suppressed_total"),
      "mean_first_gate_turn":sum(r["first_gate_turn"] for r in xs if r["first_gate_turn"] is not None)/max(1,sum(r["first_gate_turn"] is not None for r in xs)),
      "mean_first_action_diff_turn":avgturn("first_action_diff"),
      "mean_first_self_diff_turn":avgturn("first_self_diff"),
      "mean_first_market_diff_turn":avgturn("first_market_diff"),
      "mean_first_opponent_diff_turn":avgturn("first_opponent_diff"),
    }

def state_features(rows, cls):
    xs=[r for r in rows if r["class"]==cls]
    out={}
    for label in ("pre_first_action_diff","first_action_diff","first_self_diff","first_market_diff","first_opponent_diff"):
        vals=[]
        for r in xs:
            ev=r.get(label)
            if not ev: continue
            b=ev["baseline"]; q=ev["control"]
            vals.append({
              "turn":ev["turn"],"day":ev["day"],
              "baseline_self_money":b["self_money"],"control_self_money":q["self_money"],
              "baseline_opp_money":b["opp_money"],"control_opp_money":q["opp_money"],
              "control_wheat":q["stock"].get("WHEAT",0),
              "control_milk":q["stock"].get("MILK",0),
              "control_fertilizer":q["stock"].get("FERTILIZER",0),
              "control_hands":q["self_hands"],"control_land":q["self_land"],"control_cows":q["self_cows"],
            })
        if vals:
            keys=vals[0].keys()
            out[label]={k:sum(v[k] for v in vals)/len(vals) for k in keys if k not in ("day",)}
            out[label]["mean_day"]=sum(v["day"] for v in vals)/len(vals)
            out[label]["n"]=len(vals)
    return out

def main():
    rows=[analyze(s,seat) for s,seat in CASES]
    out={"schema":"bundle-flow-gate-boundary.v1","policy_mutated":False,
      "cases":rows,
      "summary":{"improved":summarize(rows,"improved"),"worsened":summarize(rows,"worsened"),"equal":summarize(rows,"equal")},
      "state_features":{"improved":state_features(rows,"improved"),"worsened":state_features(rows,"worsened")},
      "boundary":"first differences are temporal observations, not causal attribution"}
    open("bundle_flow_gate_boundary_v1.json","w",encoding="utf-8").write(json.dumps(out,ensure_ascii=False,indent=2)+"
")
    print("BUNDLE_FLOW_GATE_BOUNDARY_V1 "+json.dumps(out["summary"],separators=(",",":")))
    print("BUNDLE_FLOW_GATE_STATE_FEATURES "+json.dumps(out["state_features"],separators=(",",":")))
    pre=[]
    for r in rows:
        ev=r.get("pre_first_action_diff"); ad=r.get("first_action_diff")
        if not ev or not ad: continue
        q=ev["control"]
        pre.append({"seed":r["seed"],"seat":r["seat"],"class":r["class"],"turn":ev["turn"],"day":ev["day"],"cash":q["self_money"],"wheat":q["stock"].get("WHEAT",0),"milk":q["stock"].get("MILK",0),"fertilizer":q["stock"].get("FERTILIZER",0),"cows":q["self_cows"],"land":q["self_land"],"hands":q["self_hands"],"opp_money":q["opp_money"],"baseline_action":ad["baseline"]["action"],"control_action":ad["control"]["action"],"terminal_self_diff":r["self_diff"],"terminal_opp_diff":r["opp_diff"],"terminal_margin_diff":r["margin_diff"]})
    print("BUNDLE_FLOW_GATE_PRE_ACTION_ROWS "+json.dumps(pre,separators=(",",":")))

if __name__=="__main__": main()
# workflow trigger: corrected boundary observer
