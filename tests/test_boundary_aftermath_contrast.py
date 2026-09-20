from analyze_boundary_aftermath_contrast import delta


def test_delta_is_directional_difference_only():
    a = {"money": 0.1, "capacity": -0.2, "production": 0.0}
    b = {"money": 0.05, "capacity": -0.1, "production": 0.02}
    d = delta(a, b)
    assert d["money"] == 0.05
    assert d["capacity"] == -0.1
    assert d["production"] == -0.02
