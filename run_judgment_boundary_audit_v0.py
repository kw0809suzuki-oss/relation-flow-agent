#!/usr/bin/env python3
"""Run the manufacturing-boundary audit against the current v1.1 packet layer."""

import json

from judgment_boundary_audit_v0 import audit_packet
from judgment_capability_v1_1 import build_packet


def fake_obs():
    # Minimal representative observation sufficient for packet construction.
    return {
        "player": 0,
        "day": 12,
        "farms": [
            {
                "money": 4000,
                "hands": [{}, {}],
                "unlocked_quadrants": [0, 1],
                "tiles": [[None for _ in range(5)] for _ in range(5)],
            },
            {
                "money": 5000,
                "hands": [],
                "unlocked_quadrants": [0],
                "tiles": [[None for _ in range(5)] for _ in range(5)],
            },
        ],
        "private": {
            "shed": {"WHEAT": 8, "COW": 2},
            "inventories": [],
            "seeds": {"WHEAT": 3, "STRAWBERRY": 2, "MELON": 1},
        },
    }


def main():
    packet = build_packet(fake_obs(), human_direction="終盤のExpansionを疑う")
    result = audit_packet(packet)
    print("JUDGMENT_BOUNDARY_AUDIT_V0 " + json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    if not result["pass"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
