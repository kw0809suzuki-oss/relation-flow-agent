"""Runtime bridge from observed Role candidates back into live G15 Re-entry.

This is an operational-coordinate bridge, not a control rule.
"""

CATALOG = [
("RV_5bad123399da","RF_32b8b7d1006c",("BUY:PASS","BUY:MOVE","SELL:MOVE","BUY:MOVE"),(("cows",1),("day",0),("feed_need",1),("land",0),("units",3),("wheat",2),("unit_motion","CHANGED_POS")),1.0,1.0),
("RV_60d69f233e6e","RF_3ca576fa2843",("SELL:MOVE",),(("cows",0),("day",0),("unit_motion","CHANGED_POS")),0.94166,0.942047),
("RV_5d405dcf5f67","RF_3ca576fa2843",("SELL:MOVE","BUY:MOVE","SELL:MOVE"),(("cows",0),("day",0),("unit_motion","CHANGED_POS")),0.91284,0.91433),
("RV_43da5c6c8d91","RF_3ca576fa2843",("SELL:MOVE","SELL:MOVE"),(("cows",0),("day",0),("unit_motion","CHANGED_POS")),0.926513,0.926207),
("RV_aeec711888ca","RF_3d92be729c2d",("BUY:MOVE","SELL:MOVE","SELL:MOVE"),(("day",0),("land",0),("unit_motion","CHANGED_POS")),0.95725,0.963946),
("RV_13da72f92ab3","RF_3d92be729c2d",("BUY:MOVE","SELL:MOVE","SELL:MOVE","SELL:MOVE"),(("day",0),("land",0),("unit_motion","CHANGED_POS")),0.980234,0.98231),
("RV_1893fe72a94b","RF_3d92be729c2d",("BUY:WORK","SELL:MOVE"),(("day",0),("land",0),("unit_motion","CHANGED_POS")),0.981651,0.980303),
("RV_eb7375f14b36","RF_3d92be729c2d",("BUY:MOVE","SELL:MOVE"),(("day",0),("land",0),("unit_motion","CHANGED_POS")),0.97949,0.977772),
("RV_77dd214fad8d","RF_3d92be729c2d",("SELL:MOVE",),(("day",0),("land",0),("unit_motion","CHANGED_POS")),0.96143,0.961049),
("RV_7c75e68b5418","RF_3d92be729c2d",("SELL:WORK","BUY:MOVE","SELL:MOVE","BUY:MOVE","SELL:MOVE"),(("day",0),("land",0),("unit_motion","CHANGED_POS")),0.978846,0.992203),
("RV_2d97f1b22b42","RF_3d92be729c2d",("SELL:MOVE","SELL:MOVE","SELL:MOVE","SELL:MOVE"),(("day",0),("land",0),("unit_motion","CHANGED_POS")),0.949713,0.947845),
("RV_d47541deddfd","RF_4b685b0ae327",("SELL:WORK","BUY:MOVE","SELL:WORK","SELL:WORK","SELL:MOVE"),(("cows",1),("day",1),("feed_need",1),("land",0),("units",0),("wheat",-1),("unit_motion","CHANGED_POS")),1.0,1.0),
("RV_707945350700","RF_5948ac11adbf",("BUY:MOVE",),(("cows",0),("land",0),("unit_motion","CHANGED_POS")),0.973745,0.96963),
("RV_3430b703d82e","RF_5948ac11adbf",("SELL:MOVE",),(("cows",0),("land",0),("unit_motion","CHANGED_POS")),0.966095,0.967239),
("RV_af258bc4c06d","RF_5948ac11adbf",("SELL:MOVE","SELL:MOVE"),(("cows",0),("land",0),("unit_motion","CHANGED_POS")),0.950919,0.950912),
("RV_b0bd0296ce94","RF_5c9b534ad1bf",("SELL:MOVE","SELL:WORK","SELL:WORK"),(("land",0),),1.0,1.0),
("RV_a5c2ebb0f87a","RF_6010cff5b311",("BUY:WORK","SELL:MOVE","BUY:WORK","SELL:WORK","BUY:MOVE","SELL:WORK"),(("cows",1),("day",1),("feed_need",1),("land",0),("money",-400.0),("units",-3),("wheat",0),("unit_motion","CHANGED_POS")),1.0,1.0),
("RV_aa4415260c0c","RF_617c51780879",("SELL:MOVE","BUY:MOVE"),(("day",0),("land",0),("units",0),("unit_motion","CHANGED_POS")),0.919279,0.925065),
("RV_ed7762c43b3e","RF_617c51780879",("SELL:MOVE",),(("day",0),("land",0),("units",0),("unit_motion","CHANGED_POS")),0.954392,0.954269),
("RV_1fed3d17e2e1","RF_617c51780879",("SELL:MOVE","SELL:MOVE"),(("day",0),("land",0),("units",0),("unit_motion","CHANGED_POS")),0.947471,0.947344),
("RV_eb5a54ba4d3d","RF_696865e59a50",("SELL:MOVE",),(("cows",0),("day",0),("land",0),("unit_motion","CHANGED_POS")),0.940731,0.941101),
("RV_57c6d4824466","RF_696865e59a50",("BUY:MOVE","SELL:MOVE","BUY:MOVE","SELL:MOVE"),(("cows",0),("day",0),("land",0),("unit_motion","CHANGED_POS")),0.910547,0.919664),
("RV_b32d4d5946ac","RF_6b0d87fe1cfe",("SELL:MOVE",),(("land",0),("units",0),("unit_motion","CHANGED_POS")),0.954471,0.954308),
("RV_ab302d02bab4","RF_6b0d87fe1cfe",("SELL:MOVE","BUY:MOVE","SELL:MOVE"),(("land",0),("units",0),("unit_motion","CHANGED_POS")),0.965171,0.96353),
("RV_2934d419d1a7","RF_70c7119daf36",("BUY:MOVE",),(("cows",0),("day",0),("land",0),("units",0),("unit_motion","CHANGED_POS")),0.912482,0.915933),
("RV_e9a897d178e0","RF_70c7119daf36",("SELL:MOVE",),(("cows",0),("day",0),("land",0),("units",0),("unit_motion","CHANGED_POS")),0.934266,0.934774),
("RV_fa79749e3c91","RF_70c7119daf36",("SELL:MOVE","SELL:MOVE","SELL:MOVE"),(("cows",0),("day",0),("land",0),("units",0),("unit_motion","CHANGED_POS")),0.904405,0.901906),
("RV_ded9960e1418","RF_70c7119daf36",("SELL:MOVE","SELL:MOVE"),(("cows",0),("day",0),("land",0),("units",0),("unit_motion","CHANGED_POS")),0.916761,0.916443),
("RV_a6b59fb2ddc1","RF_728b3b9069d1",("SELL:MOVE","SELL:WORK","BUY:MOVE"),(("day",1),("land",0),("unit_motion","CHANGED_POS")),0.930622,0.925743),
("RV_d7639c4c59c5","RF_975874d04b8e",("SELL:WORK",),(("cows",0),("land",0)),0.983798,0.981195),
("RV_ee11d21293a5","RF_9c1bdc9b8d88",("SELL:MOVE",),(("cows",0),("unit_motion","CHANGED_POS")),0.967024,0.968185),
("RV_42f641bb02a5","RF_9c1bdc9b8d88",("SELL:MOVE","SELL:MOVE","BUY:MOVE"),(("cows",0),("unit_motion","CHANGED_POS")),0.914854,0.908726),
("RV_cf515063e678","RF_bb13a34704dc",("BUY:MOVE",),(("land",0),("unit_motion","CHANGED_POS")),0.995515,0.995489),
("RV_374c57628b19","RF_bb13a34704dc",("SELL:MOVE",),(("land",0),("unit_motion","CHANGED_POS")),0.998418,0.998403),
("RV_8cc89b56238a","RF_cd8e13506551",("NONE:MOVE","NONE:MOVE","NONE:MOVE"),(("cows",0),("land",0),("money",0.0),("unit_motion","CHANGED_POS")),0.989899,0.976415),
("RV_e1e93eea7d86","RF_e2b6cf4db316",("BUY:MOVE","SELL:MOVE"),(("cows",0),("land",0),("units",0),("unit_motion","CHANGED_POS")),0.907435,0.90718),
("RV_2e04a7524325","RF_e2b6cf4db316",("SELL:MOVE",),(("cows",0),("land",0),("units",0),("unit_motion","CHANGED_POS")),0.934346,0.934813),
]

NUMERIC_AXES = ("money","units","cows","wheat","feed_need","land","day")


def _delta(start, current, current_unit_pos):
    out = {axis: current.get(axis, 0) - start.get(axis, 0) for axis in NUMERIC_AXES}
    out["unit_motion"] = "CHANGED_POS" if start.get("unit_pos_sig") != current_unit_pos else "SAME_POS"
    return out


def _signature_matches(signature, delta):
    return all(delta.get(axis) == expected for axis, expected in signature)


def observe(recent_snapshots, current_state, current_unit_pos, semantic_token):
    matches = []
    for role_id, family_id, motif, signature, a_rate, b_rate in CATALOG:
        n = len(motif)
        if len(recent_snapshots) < n:
            continue
        window = recent_snapshots[-n:]
        tokens = tuple(semantic_token(s.get("action")) for s in window)
        if tokens != motif:
            continue
        d = _delta(window[0], current_state, current_unit_pos)
        if not _signature_matches(signature, d):
            continue
        matches.append({"role_id": role_id, "family_id": family_id, "signature": signature, "motif": motif, "support": min(a_rate, b_rate)})

    maximal = []
    for row in matches:
        sig = set(row["signature"])
        if any(sig < set(other["signature"]) for other in matches if other is not row):
            continue
        maximal.append(row)
    maximal.sort(key=lambda x: (-len(x["signature"]), -x["support"], x["role_id"]))
    return {
        "catalog_policy": "AB_MATCH_RATE_GE_0.90_AND_GAMES_GE_90",
        "matched_role_ids": [x["role_id"] for x in matches],
        "maximal_role_ids": [x["role_id"] for x in maximal],
        "maximal_family_ids": sorted({x["family_id"] for x in maximal}),
        "maximal_support": [round(x["support"], 6) for x in maximal],
        "matched_count": len(matches),
        "maximal_count": len(maximal),
        "connected_to_control": False,
    }
