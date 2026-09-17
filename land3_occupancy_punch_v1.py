"""One-shot Land2->3 occupancy-gate experiment.

Only when the agent owns exactly two quadrants, lower Strong Origin's
occupancy_target by 0.10 for the duration of that decision. All other gates,
policy layers, cash reserve, remaining-days logic, and actions stay unchanged.
"""
import whole_flow_control_agent as base
import strong_origin


def set_control_enabled(v): base.set_control_enabled(v)
def set_probe_enabled(v): base.set_probe_enabled(v)
def set_attribution_enabled(v): base.set_attribution_enabled(v)
def reset_telemetry(): base.reset_telemetry()
def get_telemetry(): return base.get_telemetry()


def agent(obs):
    player = obs["player"]
    me = obs["farms"][player]
    if len(me.get("unlocked_quadrants", [])) != 2:
        return base.agent(obs)

    original = {name: cfg["occupancy_target"] for name, cfg in strong_origin.STRATEGIES.items()}
    try:
        for cfg in strong_origin.STRATEGIES.values():
            cfg["occupancy_target"] = max(0.0, cfg["occupancy_target"] - 0.10)
        return base.agent(obs)
    finally:
        for name, value in original.items():
            strong_origin.STRATEGIES[name]["occupancy_target"] = value
