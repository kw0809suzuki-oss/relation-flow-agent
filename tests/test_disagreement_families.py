import json
from pathlib import Path
from subprocess import run


def test_family_compression_groups_same_disagreement(tmp_path):
    src = tmp_path / "in.json"
    src.write_text(json.dumps({
        "schema": "kaggriculture.dual-lens-candidate-observation.v0",
        "seed": 1,
        "seat": 0,
        "disagreement_count": 2,
        "candidate_generation_points": [
            {
                "combat_judgment": "switch",
                "economic_judgment": "stop",
                "economic_reason": "reserve_negative_and_trend_negative",
                "state": {
                    "relation_axes": {"money": -0.2, "capacity": -0.1, "production": 0.0},
                    "axis_movements": {"money": -0.1, "capacity": 0.0, "production": -0.2},
                },
            },
            {
                "combat_judgment": "switch",
                "economic_judgment": "stop",
                "economic_reason": "reserve_negative_and_trend_negative",
                "state": {
                    "relation_axes": {"money": -0.4, "capacity": -0.3, "production": -0.2},
                    "axis_movements": {"money": -0.3, "capacity": -0.2, "production": -0.1},
                },
            },
        ],
    }))
    script = Path(__file__).parents[1] / "analyze_disagreement_families.py"
    result = run(["python", str(script), str(src)], cwd=tmp_path, capture_output=True, text=True)
    assert result.returncode == 0
    out = json.loads((tmp_path / "dual_lens_disagreement_families.json").read_text())
    fam = out["families"]["switch->stop"]
    assert fam["count"] == 2
    assert fam["status"] == "candidate_family"
    assert fam["promote"] is False
