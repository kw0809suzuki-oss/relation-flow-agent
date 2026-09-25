"""Candidate wrapper: current Battle body followed by Official World Resolver v0."""

import whole_flow_control_agent as body
import official_world_resolver as resolver


def set_control_enabled(enabled):
    return body.set_control_enabled(enabled)


def set_probe_enabled(enabled):
    return body.set_probe_enabled(enabled)


def set_attribution_enabled(enabled):
    return body.set_attribution_enabled(enabled)


def reset_telemetry():
    return body.reset_telemetry()


def get_telemetry():
    return body.get_telemetry()


def get_trace():
    return body.get_trace()


def agent(obs):
    candidate = body.agent(obs)
    return resolver.resolve_action(obs, candidate)
