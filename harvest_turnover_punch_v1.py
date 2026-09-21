"""One-punch experiment: shorten crop production cycle without redesigning the Agent.

Hypothesis only: terminal may improve if a worker standing on a harvestable crop
harvests as soon as yield_units > 0, instead of waiting for the frozen Strong
Origin max-yield timing. Everything else remains the existing policy.
"""
import whole_flow_control_agent as base


def _harvest_now(tile):
    return isinstance(tile, dict) and tile.get("kind") == "PLANT" and tile.get("yield_units", 0) > 0


def agent(obs):
    action = base.agent(obs)
    if not isinstance(action, dict):
        return action
    player = obs.get("player")
    farms = obs.get("farms", [])
    if not isinstance(player, int) or player >= len(farms):
        return action
    me = farms[player]
    tiles = me.get("tiles", [])
    out = dict(action)

    farmer = me.get("farmer")
    if isinstance(farmer, (list, tuple)) and len(farmer) >= 2:
        x, y = farmer[0], farmer[1]
        if 0 <= y < len(tiles) and 0 <= x < len(tiles[y]) and _harvest_now(tiles[y][x]):
            out["farmer"] = ["HARVEST"]

    hands = list(action.get("hands", []) or [])
    positions = me.get("hands", []) or []
    for i, pos in enumerate(positions):
        if i >= len(hands) or not isinstance(pos, (list, tuple)) or len(pos) < 2:
            continue
        x, y = pos[0], pos[1]
        if 0 <= y < len(tiles) and 0 <= x < len(tiles[y]) and _harvest_now(tiles[y][x]):
            hands[i] = ["HARVEST"]
    out["hands"] = hands
    return out


def __getattr__(name):
    return getattr(base, name)
