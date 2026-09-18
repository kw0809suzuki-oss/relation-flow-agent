#!/usr/bin/env python3
"""Observe actual private State schema and terminal WHEAT/MILK placement for seed4119."""
import json
from kaggle_environments import make
import export_scale_baseline_v1 as base
import whole_flow_control_agent as baseline
import milk_low_price_hold_v1 as hold

SEED=4119; SEAT=1; OPPONENT=base.OPPONENT

def safe(v):
    try: json.dumps(v); return v
    except TypeError: return repr(v)

def play(label, agent_fn, reset=None):
    base._configure_baseline()
    if reset: reset()
    env=make("kaggriculture",configuration={"seed":SEED},debug=False)
    trace=[]; turn=0
    def observed(obs):
        nonlocal turn
        p=int(obs["player"]); farm=obs["farms"][p]; private=obs.get("private",{}) or {}; market=obs.get("market",{}) or {}
        action=agent_fn(obs)
        trace.append({
          "turn":turn,"day":int(obs.get("day",0)),"money":float(farm.get("money",0)),
          "farm_keys":sorted(farm.keys()),"private_keys":sorted(private.keys()),
          "private":safe(private),"market_prices":safe(market.get("prices",{})),
          "action":safe(action)
        })
        turn+=1; return action
    players=[OPPONENT,OPPONENT]; players[SEAT]=observed
    env.run(players); rewards=[float(s.reward) for s in env.state]
    return {"label":label,"terminal_reward":rewards[SEAT],"last_observed":trace[-1],
      "around_599":[x for x in trace if 595<=x["turn"]<=605]}

def main():
    b=play("baseline",baseline.agent); h=play("hold",hold.agent,hold.reset_experiment)
    out={"schema":"seed4119.actual-state-schema-terminal.v1","seed":SEED,"seat":SEAT,
      "scope":"descriptive schema/value placement; terminal reward remains objective",
      "baseline":b,"hold":h,"terminal_reward_diff":h["terminal_reward"]-b["terminal_reward"]}
    with open("seed4119_actual_state_schema_terminal.json","w",encoding="utf-8") as f:
        json.dump(out,f,ensure_ascii=False,indent=2); f.write("\n")
    print("ACTUAL_STATE_SCHEMA_TERMINAL "+json.dumps({
      "baseline_terminal":b["terminal_reward"],"hold_terminal":h["terminal_reward"],
      "diff":out["terminal_reward_diff"],
      "baseline_private_keys":b["last_observed"]["private_keys"],
      "hold_private_keys":h["last_observed"]["private_keys"]},separators=(",",":")))
if __name__=="__main__": main()
