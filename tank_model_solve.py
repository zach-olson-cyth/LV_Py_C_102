"""
LabVIEW Python Node tank model.

Function:
    tank_model_solve

Input order is locked to the LabVIEW Python Node:
    1. Valve_pos
    2. dt
    3. range_vals
    4. initial_level
    5. process_params
    6. state_in

Return order is locked to the LabVIEW cluster of 4 DBLs:
    1. measured_level
    2. flow_in
    3. flow_out
    4. state_out
"""

import math
import random


def _as_float(value):
    return float(value)


def _clamp(value, low, high):
    if value < low:
        return low
    if value > high:
        return high
    return value


def _state_to_level(state_in, initial_level, output_low, output_high):
    if isinstance(state_in, (list, tuple)):
        if len(state_in) < 1:
            return _clamp(initial_level, output_low, output_high)
        raw_state = float(state_in[0])
    else:
        raw_state = float(state_in)

    if raw_state < 0.0:
        return _clamp(initial_level, output_low, output_high)

    return _clamp(raw_state, output_low, output_high)


def tank_model_solve(
    Valve_pos,
    dt,
    range_vals,
    initial_level,
    process_params,
    state_in
):
    """
    Simulate one timestep of a tank level process.

    Inputs, exact LabVIEW Python Node order:
        Valve_pos:
            LabVIEW DBL, Python float.
            Valve position/controller output in percent, expected 0 to 100.

        dt:
            LabVIEW DBL, Python float.
            Simulation timestep in seconds.

        range_vals:
            LabVIEW 1D Array of DBL or cluster of 2 DBLs.
            Python list[float] or tuple(float, float).
            Order is [output_high, output_low].
            These values define the fixed tank range. The model clamps tank state
            and measured output between output_low and output_high.

        initial_level:
            LabVIEW DBL, Python float.
            Initial tank level used when state_in is -1.0 or state_in[0] < 0.0.

        process_params:
            LabVIEW 1D Array of DBL, Python list[float] or tuple[float, ...].
            Exact order:
                [static_gain,
                 lag,
                 deadtime,
                 load,
                 deadband,
                 sensor_noise,
                 leak_rate_half_full]

        state_in:
            LabVIEW DBL or 1D Array of DBL.
            Python float or list[float].
            Persistent tank level from the shift register.
            Use -1.0, or [-1.0], as the first-call sentinel.

    Outputs, exact LabVIEW cluster order:
        measured_level:
            LabVIEW DBL, Python float.
            Tank level after optional sensor noise and output saturation.

        flow_in:
            LabVIEW DBL, Python float.
            Inflow rate in level-units per second before tank integration.

        flow_out:
            LabVIEW DBL, Python float.
            Total outflow rate in level-units per second.

        state_out:
            LabVIEW DBL, Python float.
            Saturated true tank level for the next shift-register state.
    """
    valve_pos = _as_float(Valve_pos)
    step_s = _as_float(dt)
    initial = _as_float(initial_level)

    output_high = float(range_vals[0])
    output_low = float(range_vals[1])
    if output_high < output_low:
        temp = output_high
        output_high = output_low
        output_low = temp

    static_gain = float(process_params[0])
    lag = float(process_params[1])
    deadtime = float(process_params[2])
    load = float(process_params[3])
    deadband = abs(float(process_params[4]))
    sensor_noise = abs(float(process_params[5]))
    leak_rate_half_full = max(0.0, float(process_params[6]))

    if step_s < 0.0:
        step_s = 0.0

    true_level = _state_to_level(state_in, initial, output_low, output_high)

    valve_pos = _clamp(valve_pos, 0.0, 100.0)

    if valve_pos <= deadband:
        effective_valve = 0.0
    else:
        effective_valve = valve_pos - deadband

    flow_in = static_gain * effective_valve / 100.0

    tank_span = output_high - output_low
    if tank_span <= 0.0:
        tank_span = 1.0

    fill_fraction = (true_level - output_low) / tank_span
    fill_fraction = _clamp(fill_fraction, 0.0, 1.0)

    if fill_fraction <= 0.0:
        leak_flow = 0.0
    else:
        leak_flow = leak_rate_half_full * math.sqrt(fill_fraction / 0.5)

    process_load = max(0.0, load)
    flow_out = process_load + leak_flow

    net_flow = flow_in - flow_out

    if lag > 0.0:
        effective_lag = lag + max(0.0, deadtime)
        d_level = net_flow * step_s / effective_lag
    else:
        d_level = net_flow * step_s

    next_level = _clamp(true_level + d_level, output_low, output_high)

    if sensor_noise > 0.0:
        measured_level = next_level + random.gauss(0.0, sensor_noise)
    else:
        measured_level = next_level

    measured_level = _clamp(measured_level, output_low, output_high)

    return (
        float(measured_level),
        float(flow_in),
        float(flow_out),
        float(next_level)
    )


if __name__ == "__main__":
    params = [50.0, 4.0, 1.0, 0.0, 1.0, 0.0, 5.0]
    limits = [100.0, 0.0]

    state = -1.0
    ok = True

    for _ in range(5):
        measured, flow_in, flow_out, state = tank_model_solve(
            100.0,
            0.1,
            limits,
            30.0,
            params,
            state
        )
        ok = ok and isinstance(measured, float)
        ok = ok and isinstance(flow_in, float)
        ok = ok and isinstance(flow_out, float)
        ok = ok and isinstance(state, float)
        ok = ok and 0.0 <= measured <= 100.0
        ok = ok and 0.0 <= state <= 100.0

    empty_case = tank_model_solve(0.0, 1.0, limits, 0.0, params, -1.0)
    half_case = tank_model_solve(0.0, 1.0, limits, 50.0, params, -1.0)
    full_case = tank_model_solve(0.0, 1.0, limits, 100.0, params, -1.0)

    ok = ok and empty_case[2] <= half_case[2] <= full_case[2]
    ok = ok and abs(half_case[2] - params[6]) < 1.0e-9

    if ok:
        print("OVERALL: PASS")
    else:
        print("OVERALL: FAIL")
