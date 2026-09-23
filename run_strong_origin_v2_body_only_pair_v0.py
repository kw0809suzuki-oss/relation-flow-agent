#!/usr/bin/env python3
"""Paired Battle: Strong Origin v2 Body-only v0 vs current baseline."""
import json, os
from pathlib import Path

from kaggle_environments import make

import export_scale_baseline_v1 as basecfg
import whole_flow_control_agent as baseline
import strong_origin_v2_body_only_v0 as candidate

SEED=int(os.environ["BATTLE_SEED"])
SEAT=int(os.environ["BATTLE_SEAT"])
OUT=Path(f"strong_origin_v2_body_only_pair_v0_{SEED}.json")


def configure_baseline():
    basecfg._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"]="1"
    baseline.set_control_enabled(False)
    baseline.set_probe_enabled(True)
    baseline.set_attribution_enabled(True)
    baseline.reset_telemetry()


def configure_candidate():
    # Body-only explicitly does not consume G15/Flow controls.
    os.environ["BUNDLE_FLOW_CONTROL_V0"]="0"
    os.environ["ORIGIN_CROP_COMMITMENT"]="0"
    candidate.reset_telemetry()


def run(agent_fn, configure, telemetry_fn):
    configure()
    env=make("kaggriculture",configuration={"seed":SEED},debug=False)
    players=[basecfg.OPPONENT,basecfg.OPPONENT]
    players[SEAT]=agent_fn
    env.run(players)
    rewards=[float(x.reward) for x in env.state]
    return {
      "self":rewards[SEAT],
      "opponent":rewards[1-SEAT],
      "margin":rewards[SEAT]-rewards[1-SEAT],
      "win":rewards[SEAT]>rewards[1-SEAT],
      "telemetry":telemetry_fn(),
    }


b=run(baseline.agent,configure_baseline,baseline.get_telemetry)
c=run(candidate.agent,configure_candidate,candidate.get_telemetry)

payload={
  "schema":"kaggriculture.strong-origin-v2.body-only.paired.v0",
  "seed":SEED,"seat":SEAT,
  "baseline":b,"candidate":c,
  "delta_self":c["self"]-b["self"],
  "delta_opponent":c["opponent"]-b["opponent"],
  "delta_margin":c["margin"]-b["margin"],
  "boundary":[
    "Current baseline is whole_flow_control_agent with control OFF and current baseline configuration.",
    "Candidate is frozen Strong Origin + static livestock loop + adopted D14 expansion closure.",
    "Candidate excludes G15 dynamic livestock/Flow control, opponent-phase steering, Bundle Flow, re-entry modulation, and Catalog operations.",
    "No new economic rule is introduced.",
    "Terminal self is primary authority; wins and margin are secondary terminal outputs."
  ]
}
OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print("STRONG_ORIGIN_V2_BODY_ONLY_PAIR "+json.dumps({
  "seed":SEED,"seat":SEAT,
  "baseline":{"self":b["self"],"opponent":b["opponent"],"margin":b["margin"],"win":b["win"]},
  "candidate":{"self":c["self"],"opponent":c["opponent"],"margin":c["margin"],"win":c["win"]},
  "delta_self":payload["delta_self"],
  "delta_margin":payload["delta_margin"],
  "candidate_d14_removed":c["telemetry"].get("d14_removed_orders"),
},ensure_ascii=False,separators=(",",":")))
