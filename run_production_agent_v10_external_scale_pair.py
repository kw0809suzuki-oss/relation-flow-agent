#!/usr/bin/env python3
"""Fresh10: v10 external scale vs frozen v6.
Observe terminal only for the adoption decision.
"""
import json, statistics
from pathlib import Path
from kaggle_environments import make
import production_agent_v6_bridge1 as baseline_agent
import production_agent_v10_external_scale as candidate_agent

OPPONENT="opponents/seyamalam_v21.py"
CASES=tuple((seed,(seed-4122)%2) for seed in range(4122,4132))


def score(rewards, seat):
    own=float(rewards[seat]); opp=float(rewards[1-seat])
    return {"self":own,"opponent":opp,"margin":own-opp,"win":own>opp}


def play(seed, seat, module):
    module.reset_telemetry()
    env=make("kaggriculture",configuration={"seed":seed},debug=False)
    players=[OPPONENT,OPPONENT]
    players[seat]=module.agent
    env.run(players)
    rewards=[state.reward for state in env.state]
    return {"terminal":score(rewards,seat),"telemetry":module.get_telemetry()}


def main():
    rows=[]
    for seed,seat in CASES:
        base=play(seed,seat,baseline_agent)
        cand=play(seed,seat,candidate_agent)
        rows.append({
            "seed":seed,"seat":seat,"baseline":base,"candidate":cand,
            "self_delta":cand["terminal"]["self"]-base["terminal"]["self"],
            "margin_delta":cand["terminal"]["margin"]-base["terminal"]["margin"],
        })
    def stats(key):
        vals=[r[key] for r in rows]
        return {"mean":statistics.mean(vals),"median":statistics.median(vals),
                "positive":sum(v>0 for v in vals),"negative":sum(v<0 for v in vals),"zero":sum(v==0 for v in vals)}
    summary={
        "cases":len(rows),
        "self_delta":stats("self_delta"),
        "margin_delta":stats("margin_delta"),
        "baseline_self_mean":statistics.mean(r["baseline"]["terminal"]["self"] for r in rows),
        "candidate_self_mean":statistics.mean(r["candidate"]["terminal"]["self"] for r in rows),
        "baseline_opponent_mean":statistics.mean(r["baseline"]["terminal"]["opponent"] for r in rows),
        "candidate_opponent_mean":statistics.mean(r["candidate"]["terminal"]["opponent"] for r in rows),
        "baseline_wins":sum(r["baseline"]["terminal"]["win"] for r in rows),
        "candidate_wins":sum(r["candidate"]["terminal"]["win"] for r in rows),
    }
    out={
        "schema":"kaggriculture.production-v10-external-scale-pair.v1",
        "baseline":"production_agent_v6_bridge1.py",
        "candidate":"production_agent_v10_external_scale.py",
        "design_unit":"External body scale: Land3 / Hands11 / Animals13 target; v6 logic unchanged",
        "evaluation_boundary":{"terminal_only_for_adoption":True,"bundle_not_inspected":True,"component_attribution":False},
        "cases":rows,"summary":summary,
    }
    Path("production_agent_v10_external_scale_pair_result.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
    print("PRODUCTION_V10_EXTERNAL_SCALE_PAIR "+json.dumps(summary,separators=(",",":")))

if __name__=="__main__": main()
