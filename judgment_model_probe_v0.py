#!/usr/bin/env python3
"""Judgment Model probe v0.

Feeds real v1.1 grounded packets to an LLM and records how it interprets
unsettled relation hints. No actions are changed in the game.
"""
import json
import os
from pathlib import Path

from kaggle_environments import make
from openai import OpenAI

import export_scale_baseline_v1 as base
import g17_agent as current
from judgment_capability_v1_1 import build_packet

OPPONENT = base.OPPONENT
SEED = 6301
SEAT = 0
SELECT_DAYS = {8, 16, 24}
OUT = Path("judgment_model_probe_v0.json")


SYSTEM = """You are the Judgment Model for Kaggriculture.

Your job is to interpret an observed farm State using relation hints that are
guidance candidates, not established rules.

Important:
- Do not treat strong/candidate/weak triage labels as decision weights.
- A strong hint may be irrelevant in this State.
- A weak hint may be relevant.
- Evaluate every hint against the actual State.
- Keep conflicting interpretations if they remain plausible.
- Do not choose a concrete game action.
- Do not invent facts absent from the packet.
- If evidence is missing, say so.

Return JSON only with this shape:
{
  "hint_evaluations": {
    "<hint_name>": {
      "relevance": "relevant|weakly_relevant|not_relevant|conflicting|missing_evidence",
      "state_support": ["..."],
      "state_counter": ["..."],
      "missing_evidence": ["..."]
    }
  },
  "directions": {
    "grow": {"need": "high|medium|low|uncertain", "because": ["..."], "against": ["..."]},
    "earn": {"need": "high|medium|low|uncertain", "because": ["..."], "against": ["..."]},
    "recover": {"need": "high|medium|low|uncertain", "because": ["..."], "against": ["..."]}
  },
  "cross_direction_tensions": ["..."],
  "missing_evidence": ["..."],
  "closure_note": "what remains unresolved"
}
"""


def configure():
    os.environ["ORIGIN_GATE_POLARITY"] = "inverted"
    os.environ["ORIGIN_GATE_MAGNITUDE"] = "0.04"
    os.environ["G15_CONNECT_OPPONENT_FIELD_DESCRIPTION"] = "1"
    os.environ["G15_ADAPTIVE_W_AMPLITUDE"] = "1"
    os.environ["G15_REMOVE_R_RELATION"] = "0"
    os.environ["G15_REMOVE_E_RELATION"] = "0"
    os.environ["G15_REMOVE_W_RELATION"] = "0"
    os.environ["G15_DISABLE_RESONANCE_CONTROL"] = "0"
    os.environ["ORIGIN_CROP_COMMITMENT"] = "1"
    os.environ["BUNDLE_FLOW_CONTROL_V0"] = "1"
    current.set_probe_enabled(True)
    current.set_attribution_enabled(True)
    current.reset_telemetry()


def collect_packets():
    configure()
    env = make("kaggriculture", configuration={"seed": SEED}, debug=False)
    packets = {}
    last_day = None

    def observed(obs):
        nonlocal last_day
        day = int(obs.get("day", 0) or 0)
        if day in SELECT_DAYS and day != last_day:
            packets[day] = build_packet(
                obs,
                human_direction="目的はterminal selfを伸ばし、最終的には勝率を上げる。方向は仮説として扱う。",
            )
        last_day = day
        return current.agent(obs)

    players = [OPPONENT, OPPONENT]
    players[SEAT] = observed
    env.run(players)
    rewards = [float(s.reward) for s in env.state]
    return packets, {
        "self": rewards[SEAT],
        "opponent": rewards[1-SEAT],
        "margin": rewards[SEAT] - rewards[1-SEAT],
    }


def call_model(client, model, packet):
    prompt = json.dumps(packet, ensure_ascii=False, separators=(",", ":"))
    response = client.responses.create(
        model=model,
        input=[
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": prompt},
        ],
    )
    raw = response.output_text
    try:
        parsed = json.loads(raw)
        parse_error = None
    except Exception as exc:
        parsed = None
        parse_error = repr(exc)
    return {"raw": raw, "parsed": parsed, "parse_error": parse_error}


def main():
    packets, terminal = collect_packets()
    key = os.getenv("OPENAI_API_KEY", "").strip()
    model = os.getenv("JUDGMENT_MODEL", "gpt-5.6-luna")

    if not key:
        payload = {
            "schema": "kaggriculture.judgment-model-probe.v0",
            "status": "skipped_no_api_key",
            "model": model,
            "terminal": terminal,
            "packet_days": sorted(packets),
        }
        OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print("JUDGMENT_MODEL_PROBE_V0 " + json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
        return

    client = OpenAI(api_key=key)
    judgments = {}
    for day in sorted(packets):
        judgments[str(day)] = call_model(client, model, packets[day])

    payload = {
        "schema": "kaggriculture.judgment-model-probe.v0",
        "status": "completed",
        "model": model,
        "policy_mutated": False,
        "terminal": terminal,
        "judgments": judgments,
        "boundary": [
            "Relation hints remain guidance candidates.",
            "Triage labels are not supplied as decision weights.",
            "The model may mark any hint not relevant.",
            "No concrete action is generated or applied.",
        ],
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    compact = {
        day: {
            "parse_error": row["parse_error"],
            "directions": (row["parsed"] or {}).get("directions"),
            "hint_relevance": {
                name: data.get("relevance")
                for name, data in ((row["parsed"] or {}).get("hint_evaluations") or {}).items()
            },
            "closure_note": (row["parsed"] or {}).get("closure_note"),
        }
        for day, row in judgments.items()
    }
    print("JUDGMENT_MODEL_PROBE_V0 " + json.dumps({
        "status": "completed",
        "model": model,
        "terminal": terminal,
        "days": compact,
    }, ensure_ascii=False, separators=(",", ":")))


if __name__ == "__main__":
    main()
