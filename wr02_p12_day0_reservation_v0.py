"""WR-02 + P12 Day0 Target Reservation v0.

Active model WR-02 is unchanged except that the frozen Strong Origin used during
Day0 is swapped to the existing Day0 target-reservation variant. From Day1
onward the reserved origin behaves as frozen Strong Origin, while WR-02's
existing Day14+ same-tile deconfliction remains unchanged.
"""
import strong_origin_body
import wr02_same_tile_plant_deconfliction_v0 as wr02
import strong_origin_day0_target_reservation_v0 as reserved_origin


def _call(fn, *args, **kwargs):
    old = strong_origin_body.strong_origin
    strong_origin_body.strong_origin = reserved_origin
    try:
        return fn(*args, **kwargs)
    finally:
        strong_origin_body.strong_origin = old


def agent(obs):
    return _call(wr02.agent, obs)


def reset_telemetry():
    return _call(wr02.reset_telemetry)


def get_telemetry():
    return wr02.get_telemetry()
