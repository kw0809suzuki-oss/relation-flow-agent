#!/usr/bin/env python3
"""Observe value placement around turn599 for seed4119 baseline vs MILK Hold."""
import json
from kaggle_environments import make
import export_scale_baseline_v1 as base
import whole_flow_control_agent as baseline
import milk_low_price_hold_v1 as hold

SEED=4119
SEAT=1
OPPONENT=base.OPPONENT
WINDOW=range(590,606)

def snap(obs):
    p=int(obs["player"]); farm=obs["farms"][p]
    return {
      "day":int(obs.get("day",0)),
      "money":float(farm.get("money",0)),
      "inventory":farm.get("inventory",{}),
      "animals":farm.get("animals",{}),
      "land":farm.get("land"),
      "hands":farm.get("hands"),
      "plants":farm.get("plants"),
      "market_prices":obs.get("market",{}).get("prices",{}),
    }

def play(agent_fn, reset=None):
    base._configure_baseline()
    if reset: reset()
    env=make("kaggriculture",configuration={"seed":SEED},debug=False)
    trace=[]; turn=0
    def observed(obs):
        nonlocal turn
        s=snap(obs); a=agent_fn(obs)
        if turn in WINDOW:
            s["turn"]=turn; s["action"]=a; trace.append(s)
        turn+=1; return a
    players=[OPPONENT,OPPONENT]; players[SEAT]=observed
    env.run(players)
    rewards=[float(s.reward) for s in env.state]
    return trace,rewards[SEAT]

def main():
    b,bt=play(baseline.agent)
    h,ht=play(hold.agent,hold.reset_experiment)
    byb={x["turn"]:x for x in b}; byh={x["turn"]:x for x in h}
    rows=[]
    for t in WINDOW:
        br,hr=byb[t],byh[t]
        rows.append({"turn":t,"baseline":br,"hold":hr,"money_diff":hr["money"]-br["money"]})
    out={"schema":"seed4119.turn599-value-observer.v1","seed":SEED,"seat":SEAT,
      "scope":"descriptive state/action/value placement only; no causal attribution",
      "baseline_terminal":bt,"hold_terminal":ht,"terminal_diff":ht-bt,"rows":rows}
    with open("seed4119_turn599_value_observer.json","w",encoding="utf-8") as f:
        json.dump(out,f,ensure_ascii=False,indent=2,default=str); f.write("\n")
    print("TURN599_VALUE_OBSERVER "+json.dumps({"terminal_diff":ht-bt,"rows":len(rows)},separators=(",",":")))
if __name__=="__main__": main()
