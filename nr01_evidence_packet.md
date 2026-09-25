# NR-01 SCAN v0 — Evidence Packet

**candidate:** 1  
**boundary:** \`movement/allocation -> productive execution\`  
**support:** 10/10 battles, 287 qualifying events

## Representative event

- seed: 8301
- seat: 0
- turn: Day0 h11
- same position: [4, 0]
- unit indices: [1, 3]

## Front — Current Action

- PLANT requests: 2
- requests by crop: \`{"WHEAT": 2}\`

## Back — Resource / World state

- workers: 4
- empty tiles: 20
- alternate empty tiles: 19
- available seed: \`{"WHEAT": 9, "CARROT": 0, "TOMATO": 0, "STRAWBERRY": 0, "MELON": 8}\`
- seed sufficient for requests: True
- Current seed acquisition confirmed: True
- prior Current seed acquisition: `{"WHEAT": {"row_index": 7, "day": 0, "hour": 7, "crop": "WHEAT", "issued_qty": 3, "inferred_realized_qty": 3, "seed_before": 8, "seed_next": 11}}`
- target was empty at State_t: True

## World execution

- success: 1
- failed: 1
- failure reasons: \`{"TARGET_TILE_NOT_EMPTY": 1}\`

## Previous 3 turns

\`\`\`json
[
  {
    "day": 0,
    "hour": 8,
    "members": [
      {
        "unit_index": 1,
        "position": [
          4,
          2
        ],
        "action": [
          "NORTH"
        ]
      },
      {
        "unit_index": 3,
        "position": [
          4,
          1
        ],
        "action": [
          "PLANT",
          "WHEAT"
        ]
      }
    ]
  },
  {
    "day": 0,
    "hour": 9,
    "members": [
      {
        "unit_index": 1,
        "position": [
          4,
          1
        ],
        "action": [
          "WATER"
        ]
      },
      {
        "unit_index": 3,
        "position": [
          4,
          1
        ],
        "action": [
          "WATER"
        ]
      }
    ]
  },
  {
    "day": 0,
    "hour": 10,
    "members": [
      {
        "unit_index": 1,
        "position": [
          4,
          1
        ],
        "action": [
          "NORTH"
        ]
      },
      {
        "unit_index": 3,
        "position": [
          4,
          1
        ],
        "action": [
          "NORTH"
        ]
      }
    ]
  }
]
\`\`\`

## State transition

\`\`\`json
{
  "empty_tiles": -2,
  "plant_total": 2,
  "plants_by_crop_before": {
    "WHEAT": 3
  },
  "plants_by_crop_after": {
    "WHEAT": 5
  }
}
\`\`\`

## Guard

\`\`\`json
{
  "resource_state_present": true,
  "resource_generated_or_acquired_by_current": true,
  "current_productive_action_generated": true,
  "world_failure_observed": true,
  "alternate_empty_capacity_observed": true
}
\`\`\`

## Scope contract

This packet identifies one candidate boundary only. It does not adopt a repair.

**Close target = the exact transform exercised by an A/B test.**

A rejected repair must not automatically close:
- Day4 planting as a whole
- Available Resource -> Productive State as a whole
- any Resource for which Current usage intent was not directly observed
