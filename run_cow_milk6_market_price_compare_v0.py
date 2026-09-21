#!/usr/bin/env python3
import json, os
from pathlib import Path
from kaggle_environments import make

import export_scale_baseline_v1 as base
import whole_flow_control_agent as baseline
import cow_first_purchase_suppress_v0 as candidate

OPPONENT = base.OPPONENT
FRESH10 = [(4402 + i, i % 2) for i in range(10)]
FOCUS_TURNS = {197,198}

def configure():
    base._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"] = "1"
    baseline.set_control_enabled(False)
    baseline.set_probe_enabled(True)
    baseline.set_attribution_enabled(True)
    baseline.reset_telemetry()

def play(agent_fn, seed, seat, reset=None):
    configure()
    if reset:
        reset()
    snaps=[]
    turn=[0]
    env=make("kaggriculture",configuration={"seed":seed},debug=False)

    def observed(obs):
        t=turn[0]
        if t in FOCUS_TURNS:
            market=obs.get("market",{}) or {}
            snaps.append({
                "turn":t,
                "day":obs.get("day"),
                "hour":obs.get("hour"),
                "prices":market.get("prices",{}) or {},
                "inventory":market.get("inventory",{}) or {},
            })
        action=agent_fn(obs)
        turn[0]+=1
        return action

    players=[OPPONENT,OPPONENT]
    players[seat]=observed
    env.run(players)
    rewards=[float(s.reward) for s in env.state]
    return {"score":{"self":rewards[seat],"opp":rewards[1-seat],"margin":rewards[seat]-rewards[1-seat]},"snapshots":snaps}

def main():
    cases=[]
    for seed,seat in FRESH10:
        b=play(baseline.agent,seed,seat)
        c=play(candidate.agent,seed,seat,candidate.reset_experiment)
        self_diff=c["score"]["self"]-b["score"]["self"]
        cls="improved" if self_diff>0 else ("worsened" if self_diff<0 else "equal")
        cases.append({
            "seed":seed,"seat":seat,"class":cls,"accident3":seed in (4404,4407,4409),
            "self_diff":self_diff,
            "baseline":b["snapshots"],
            "candidate":c["snapshots"],
        })

    def get(case, which, turn, key):
        snaps={x["turn"]:x for x in case[which]}
        return snaps.get(turn,{}).get("prices",{}).get(key)

    summary={
        "improved_milk_price_t197":[get(c,"candidate",197,"MILK") for c in cases if c["class"]=="improved"],
        "worsened_milk_price_t197":[get(c,"candidate",197,"MILK") for c in cases if c["class"]=="worsened"],
        "accident3_milk_price_t197":[get(c,"candidate",197,"MILK") for c in cases if c["accident3"]],
        "improved_milk_price_t198":[get(c,"candidate",198,"MILK") for c in cases if c["class"]=="improved"],
        "worsened_milk_price_t198":[get(c,"candidate",198,"MILK") for c in cases if c["class"]=="worsened"],
        "accident3_milk_price_t198":[get(c,"candidate",198,"MILK") for c in cases if c["accident3"]],
    }

    out={
        "schema":"kaggriculture.milk6-market-price-compare.v0",
        "source":{"historical_commit":"27cac110515eca257c157904984add017d5ea8bb","historical_run":35422159593},
        "focus_turns":[197,198],
        "principle":{"observer_only":True,"direct_market_price_observation":True,"causal_claim":False},
        "cases":cases,
        "summary":summary,
        "promote":False,
    }
    Path("cow_milk6_market_price_compare_v0.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps(summary,ensure_ascii=False,separators=(",",":")))

if __name__=="__main__":
    main()
