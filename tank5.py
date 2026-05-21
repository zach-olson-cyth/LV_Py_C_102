"""
tank3.py — LabVIEW Python Node: Tank Level Process Simulation
Function: tank_model_solve

Block diagram: Tank Level Process Simulation (image-2.jpg)
Case structure: "False" frame — normal simulation (not reinitialize)

Parameter order is FROZEN per Parameter Order Lock Policy.
Do NOT reorder. Append new params at END only. Create _v2 if restructuring required.

Version: 1.0.0
Author: Generated for Scythe Systems / zach.olson@cyth.com

INPUTS (exact LabVIEW terminal order, top to bottom on left side of Python Node):
  1. Valve_pos       DBL   float           Valve position / controller output (0–100 %)
  2. dt              DBL   float           Simulation timestep in seconds
  3. range_vals      1D DBL [2]  list[float]  [output_high, output_low] — e.g. [100.0, 0.0]
  4. initial_level   DBL   float           Tank starting level (0–100 %)
  5. process_params  1D DBL [7]  list[float]  [static_gain, lag, deadtime, load,
                                               deadband, sensor_noise, leak_rate_half_full]
  6. state_in        DBL   float           Persistent level state; pass -1.0 on first call

OUTPUTS (exact LabVIEW terminal order, top to bottom on right side of Python Node):
  1. measured_level  DBL   float           Simulated tank level (0–100 %)
  2. flow_in         DBL   float           Effective inflow rate after lag (% full / second)
  3. flow_out        DBL   float           Outflow / leak rate (% full / second)
  4. state_out       DBL   float           Updated state for LabVIEW shift register

LabVIEW return type: Cluster of 4 DBLs (same order as tuple above)

LEAK MODEL:
  The leak is located at the bottom of the tank. Static pressure drives flow.
  Torricelli's law: Q_leak ∝ sqrt(h)  where h is fill height.
  Reference point: leak_rate_half_full is the rate when the tank is at 50 % full.
  At arbitrary level L (%):
      Q_leak = leak_rate_half_full * sqrt(L / 50.0)
  At L = 0 → Q_leak = 0  (no pressure, no leak)
  At L = 50 → Q_leak = leak_rate_half_full  (reference calibration point)
  At L = 100 → Q_leak = leak_rate_half_full * sqrt(2)  (~41 % higher than half-full rate)

CASE STRUCTURE (False frame = normal run):
  - If state_in < 0: first-call sentinel detected → reinitialize to initial_level
  - Apply valve deadband: if |Valve_pos| < deadband → treat as 0
  - Clamp valve to [0, 100] %
  - Compute valve flow (raw): valve_flow = static_gain * (Valve_pos / 100.0) + load + noise
  - Apply process lag to inflow:  flow_in = valve_flow / lag  [if lag > 0]
                                  flow_in = valve_flow         [if lag == 0]
    This is the EFFECTIVE rate at which liquid actually enters the tank.
    lag models valve actuator / process response time constant on the supply side.
  - Compute outflow (flow_out): pressure-dependent leak via Torricelli sqrt model.
    The leak is driven by instantaneous static pressure and is NOT lagged.
  - Integrate level directly using effective rates:
        dL/dt = flow_in - flow_out
    Both flow_in and flow_out are now in matching units (% full/s) and their
    difference is the true net rate of level change.
  - Returned flow_in and flow_out represent the actual physical flow rates —
    flow_in < flow_out means tank drains; flow_in > flow_out means tank fills.
  - Deadtime: not implemented in this version (add FIFO buffer if needed)
  - Saturate level to [output_low, output_high] — tank cannot go below empty or above full

NOTE ON DEADTIME:
  deadtime is unpacked from process_params but not applied to the level integration.
  To add: maintain a queue of past flow_in values and index by deadtime/dt samples.
"""

import math
import random


def tank_model_solve(
    Valve_pos,        # float  — valve position / controller output (0–100 %)
    dt,               # float  — simulation timestep (seconds)
    range_vals,       # list[float] or tuple — [output_high, output_low]
    initial_level,    # float  — initial tank level (% full, 0–100)
    process_params,   # list[float] or tuple — [static_gain, lag, deadtime, load,
                      #                          deadband, sensor_noise, leak_rate_half_full]
    state_in          # float  — persistent state; use -1.0 on first call
):
    """
    Simulate one timestep of a tank-level process for LabVIEW Python Node integration.

    Returns
    -------
    tuple of (measured_level, flow_in, flow_out, state_out)
    All values are plain Python float — no numpy scalars.
    LabVIEW return type: Cluster of 4 DBLs.
    """

    # ------------------------------------------------------------------ #
    # 1. Unpack process parameters (exact order from block diagram array) #
    # ------------------------------------------------------------------ #
    static_gain          = float(process_params[0])  # dimensionless gain on valve
    lag                  = float(process_params[1])  # first-order lag time constant (s)
    deadtime             = float(process_params[2])  # transport delay (s) — reserved
    load                 = float(process_params[3])  # process load / disturbance (% full/s)
    deadband             = float(process_params[4])  # valve deadband (% — absolute)
    sensor_noise         = float(process_params[5])  # std-dev of additive Gaussian noise
    leak_rate_half_full  = float(process_params[6])  # leak rate at 50 % fill (% full/s)

    # Unpack output range limits
    output_high = float(range_vals[0])   # e.g. 100.0  — tank full
    output_low  = float(range_vals[1])   # e.g.   0.0  — tank empty

    # ------------------------------------------------------------------ #
    # 2. State initialization — sentinel pattern                          #
    #    First-call detection: state_in < 0 → reinitialize to initial_level
    # ------------------------------------------------------------------ #
    if isinstance(state_in, (list, tuple)):
        raw_state = float(state_in[0]) if len(state_in) > 0 else -1.0
    else:
        raw_state = float(state_in)

    if raw_state < 0.0:
        # First call: use the initial_level set in the block diagram constant (30 %)
        prev_level = float(initial_level)
    else:
        prev_level = raw_state

    # ------------------------------------------------------------------ #
    # 3. Valve deadband and saturation                                    #
    # ------------------------------------------------------------------ #
    valve = float(Valve_pos)

    # Deadband: small signals around zero are treated as zero (stiction / hysteresis)
    if abs(valve) < deadband:
        valve = 0.0

    # Hard saturation: physical valve cannot open beyond 0–100 %
    valve = max(0.0, min(valve, 100.0))

    # ------------------------------------------------------------------ #
    # 4. Inflow calculation                                               #
    # ------------------------------------------------------------------ #
    # Step 1 — raw valve delivery: full-open (100%) delivers static_gain %/s
    valve_flow = static_gain * (valve / 100.0)

    # Add process load / disturbance (from LOAD CALC SUBVII in block diagram)
    valve_flow += load

    # Additive Gaussian sensor noise on the flow signal
    if sensor_noise > 0.0:
        valve_flow += random.gauss(0.0, sensor_noise)

    # Step 2 — apply process lag to get effective inflow rate
    # lag is the first-order time constant (s) of the supply-side process.
    # Dividing raw valve flow by lag gives the actual rate at which liquid
    # enters the tank per second, in the same units as flow_out.
    # This is what the control valve actually controls.
    if lag > 0.0:
        flow_in = valve_flow / lag
    else:
        flow_in = valve_flow

    # ------------------------------------------------------------------ #
    # 5. Pressure-dependent leak (Torricelli / hydrostatic model)         #
    #                                                                     #
    # Physical basis: for a hole at the bottom of the tank,              #
    #   v_leak = sqrt(2 * g * h)   (Torricelli)                          #
    # h is proportional to tank level, so:                               #
    #   Q_leak ∝ sqrt(level)                                             #
    #                                                                     #
    # Calibration: leak_rate_half_full is Q_leak when level = 50 %       #
    #   Q_leak(L) = leak_rate_half_full * sqrt(L / 50.0)                 #
    #                                                                     #
    # At L = 0   →  Q_leak = 0        (no hydrostatic pressure)          #
    # At L = 50  →  Q_leak = leak_rate_half_full   (reference)           #
    # At L = 100 →  Q_leak = leak_rate_half_full * sqrt(2) ≈ 1.414×ref  #
    # ------------------------------------------------------------------ #
    if prev_level <= 0.0 or leak_rate_half_full <= 0.0:
        flow_out = 0.0
    else:
        # Clamp level used for leak calculation to physical range before sqrt
        level_for_leak = max(0.0, min(prev_level, output_high))
        flow_out = leak_rate_half_full * math.sqrt(level_for_leak / 50.0)

    # ------------------------------------------------------------------ #
    # 6. Tank level integration (forward Euler)                           #
    # flow_in is already the effective post-lag rate; flow_out is the     #
    # instantaneous Torricelli leak. Both are in % full/s — subtract      #
    # directly to get the net rate of level change.                       #
    # ------------------------------------------------------------------ #
    delta_level = (flow_in - flow_out) * dt

    new_level = prev_level + delta_level

    # ------------------------------------------------------------------ #
    # 7. Saturation block — tank volume limits                            #
    #    Tank cannot be below empty (output_low) or above full (output_high)
    # ------------------------------------------------------------------ #
    measured_level = max(output_low, min(new_level, output_high))

    # ------------------------------------------------------------------ #
    # 8. State output — returned to LabVIEW shift register               #
    # ------------------------------------------------------------------ #
    state_out = measured_level

    # ------------------------------------------------------------------ #
    # 9. Return cluster of 4 DBLs — exact LabVIEW terminal order         #
    #    (level, flow_sensor_in, flow_sensor_out, state_out)              #
    # ------------------------------------------------------------------ #
    return (
        float(measured_level),
        float(flow_in),
        float(flow_out),
        float(state_out)
    )


# ======================================================================= #
# __main__ smoke test — must PASS standalone before wiring to LabVIEW    #
# Run: python tank3.py                                                    #
# ======================================================================= #
if __name__ == "__main__":
    import sys

    PASS = True

    def check(label, condition, got=None):
        global PASS
        if condition:
            print(f"  PASS  {label}")
        else:
            print(f"  FAIL  {label}  (got: {got})")
            PASS = False

    # ------------------------------------------------------------------ #
    # Test parameters matching block diagram defaults                     #
    # process_params = [static_gain=50, lag=4, deadtime=1, load=0,       #
    #                   deadband=1, sensor_noise=0, leak_rate_half_full=5]#
    # range_vals = [100.0, 0.0]                                           #
    # initial_level = 30.0                                                #
    # ------------------------------------------------------------------ #
    process_params_bd = [50.0, 4.0, 1.0, 0.0, 1.0, 0.0, 5.0]
    range_vals_bd     = [100.0, 0.0]
    dt_bd             = 0.001   # 0.001 s timestep (from block diagram: 0.001 × Multiply)
    initial_level_bd  = 30.0

    print("=" * 60)
    print("tank_model_solve — Smoke Test")
    print("=" * 60)

    # ------------------------------------------------------------------ #
    # Test 1: First call (sentinel state = -1.0)                         #
    # ------------------------------------------------------------------ #
    print("\nTest 1: First-call sentinel initialization")
    level, fi, fo, s_out = tank_model_solve(
        50.0,               # Valve_pos 50 %
        dt_bd,
        range_vals_bd,
        initial_level_bd,   # 30 %
        process_params_bd,
        -1.0                # sentinel → reinit to 30 %
    )
    check("Return is tuple of 4", isinstance((level, fi, fo, s_out), tuple) and len((level, fi, fo, s_out)) == 4)
    check("All outputs are float", all(isinstance(v, float) for v in (level, fi, fo, s_out)))
    check("measured_level in [0, 100]", 0.0 <= level <= 100.0, level)
    check("state_out == measured_level", abs(s_out - level) < 1e-9, s_out)
    check("flow_out > 0 (leak at 30 %)", fo > 0.0, fo)
    check("flow_out < leak_half_full (level<50%)", fo < 5.0, fo)
    # valve=50%: flow_in = 50*(50/100)/lag = 25/4 = 6.25; flow_out = 5*sqrt(30/50) = 3.87
    # flow_in should be ~6.25 -- controlled by valve, NOT driven by leak
    check("flow_in controlled by valve (not leak)", abs(fi - 50.0*(50.0/100.0)/4.0) < 0.01, fi)
    check("flow_in != flow_out (not cross-coupled)", abs(fi - fo) > 0.1, (fi, fo))

    print(f"  INFO  level={level:.4f}%, flow_in={fi:.4f} (expect 6.25), flow_out={fo:.4f} (expect 3.87)")

    # ------------------------------------------------------------------ #
    # Test 2: Valve fully closed — tank must drain to zero                #
    #                                                                     #
    # With valve=0 and lag=4:                                             #
    #   flow_in = 0; dL/dt = 0/lag - leak = -leak  (instantaneous)       #
    #   leak at 50% = 5.0 %/s → drains ~26% in 10 s                      #
    #   After 20 s from 30% start, tank should be empty.                 #
    # ------------------------------------------------------------------ #
    print("\nTest 2: Valve closed — tank must drain completely to 0")
    state = 30.0
    for _ in range(20000):   # 20 seconds at dt=0.001
        level, fi, fo, state = tank_model_solve(
            0.0,
            dt_bd,
            range_vals_bd,
            initial_level_bd,
            process_params_bd,
            state
        )
    check("Tank drains to 0 within 20s (valve closed)", level == 0.0, level)
    check("Level stays >= 0 (saturation enforced)", level >= 0.0, level)
    print(f"  INFO  After 20000 steps (20s) with valve=0: level={level:.4f}%")

    # Intermediate check: level is noticeably dropping after just 1 second
    state = 30.0
    for _ in range(1000):
        level, fi, fo, state = tank_model_solve(
            0.0, dt_bd, range_vals_bd, initial_level_bd, process_params_bd, state
        )
    check("Level drops >1% in first 1s (valve closed)", level < 29.0, level)
    print(f"  INFO  After 1000 steps (1s) with valve=0: level={level:.4f}%")

    # ------------------------------------------------------------------ #
    # Test 3: Valve fully open — level should fill toward output_high     #
    # ------------------------------------------------------------------ #
    print("\nTest 3: Valve fully open — level should increase toward 100 %")
    state = 30.0   # start at initial
    for _ in range(5000):
        level, fi, fo, state = tank_model_solve(
            100.0,          # valve fully open
            dt_bd,
            range_vals_bd,
            initial_level_bd,
            process_params_bd,
            state
        )
    check("Level rises when valve fully open", level > 30.0, level)
    check("Level does not exceed 100 % (saturation)", level <= 100.0, level)
    print(f"  INFO  After 5000 steps with valve=100: level={level:.4f}%")

    # ------------------------------------------------------------------ #
    # Test 4: Tank empty — leak must be zero                             #
    # ------------------------------------------------------------------ #
    print("\nTest 4: Empty tank — leak must be zero")
    level, fi, fo, state_out = tank_model_solve(
        0.0,
        dt_bd,
        range_vals_bd,
        initial_level_bd,
        process_params_bd,
        0.0   # state = empty
    )
    check("Leak is 0 when tank is empty", abs(fo) < 1e-9, fo)

    # ------------------------------------------------------------------ #
    # Test 5: Leak at 50 % fill should equal leak_rate_half_full (no lag correction)
    # Use large dt to amplify any difference
    # ------------------------------------------------------------------ #
    print("\nTest 5: Leak calibration — at 50 % level, flow_out ≈ leak_rate_half_full")
    # One step with level exactly at 50 %; no-lag params and very small dt to keep level near 50
    params_no_lag = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 5.0]   # static_gain=0, lag=0, leak=5
    level, fi, fo, s_out = tank_model_solve(
        0.0,
        1e-9,            # near-zero dt so level barely moves
        range_vals_bd,
        50.0,
        params_no_lag,
        50.0             # state exactly at 50 %
    )
    check("flow_out ≈ 5.0 at 50 % fill", abs(fo - 5.0) < 0.01, fo)
    print(f"  INFO  flow_out at 50%: {fo:.6f}  (expected ~5.0)")

    # ------------------------------------------------------------------ #
    # Test 6: Leak at 100 % fill should ≈ leak_rate_half_full * sqrt(2) #
    # ------------------------------------------------------------------ #
    print("\nTest 6: Leak at 100 % fill ≈ leak_rate_half_full × √2")
    level, fi, fo, s_out = tank_model_solve(
        0.0,
        1e-9,
        range_vals_bd,
        100.0,
        params_no_lag,
        100.0
    )
    expected_full = 5.0 * math.sqrt(2.0)
    check(f"flow_out ≈ {expected_full:.4f} at 100 % fill", abs(fo - expected_full) < 0.01, fo)
    print(f"  INFO  flow_out at 100%: {fo:.6f}  (expected ~{expected_full:.4f})")

    # ------------------------------------------------------------------ #
    # Test 6b: flow_in is controlled by valve, flow_out by level          #
    # At 30% fill, flow_in should scale with valve; flow_out fixed by     #
    # static pressure.  flow_in < flow_out means draining.               #
    # ------------------------------------------------------------------ #
    print("\nTest 6b: Valve controls flow_in independently of flow_out")
    # static_gain=50, lag=4: flow_in = 50*(v/100)/4 = v*0.125
    # flow_out at 30% = 5*sqrt(30/50) = 3.873 (constant for fixed level)
    prev_fo = None
    for valve_test in [0.0, 25.0, 50.0, 100.0]:
        _, fi_t, fo_t, _ = tank_model_solve(
            valve_test, dt_bd, range_vals_bd, initial_level_bd, process_params_bd, 30.0
        )
        expected_fi = 50.0 * (valve_test / 100.0) / 4.0
        check(f"flow_in at valve={valve_test:.0f}% = {expected_fi:.3f}",
              abs(fi_t - expected_fi) < 0.01, fi_t)
        if prev_fo is not None:
            check(f"flow_out unchanged as valve changes (30% fixed)",
                  abs(fo_t - prev_fo) < 0.001, fo_t)
        prev_fo = fo_t
        direction = "FILL" if fi_t > fo_t else "DRAIN"
        print(f"  INFO  valve={valve_test:5.1f}%  flow_in={fi_t:.4f}  flow_out={fo_t:.4f}  [{direction}]")

    # ------------------------------------------------------------------ #
    # Test 7: Deadband — small valve signal should produce zero inflow   #
    # ------------------------------------------------------------------ #
    print("\nTest 7: Deadband — valve signal within deadband treated as zero")
    # deadband = 1.0, send valve at 0.5 % (inside deadband)
    level_a, fi_a, fo_a, _ = tank_model_solve(
        0.5,    # inside deadband of 1.0
        dt_bd, range_vals_bd, 30.0, process_params_bd, 30.0
    )
    level_b, fi_b, fo_b, _ = tank_model_solve(
        0.0,    # exactly zero
        dt_bd, range_vals_bd, 30.0, process_params_bd, 30.0
    )
    check("Valve inside deadband matches valve=0", abs(fi_a - fi_b) < 1e-9, (fi_a, fi_b))

    # ------------------------------------------------------------------ #
    # Test 8: Saturation — output clamped to [output_low, output_high]  #
    # ------------------------------------------------------------------ #
    print("\nTest 8: Saturation block — output clamped to [0, 100]")
    # Force overflow: start at 99.9 %, high static_gain, large dt
    params_fast = [200.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]  # gain=200, no leak
    level, fi, fo, s_out = tank_model_solve(
        100.0,
        1.0,                # 1-second step
        range_vals_bd,
        99.9,
        params_fast,
        99.9
    )
    check("Level saturates at output_high (100.0)", level <= 100.0, level)

    # Force underflow: start at 0.1 %, valve closed, high leak
    params_drain = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 200.0]
    level, fi, fo, s_out = tank_model_solve(
        0.0,
        1.0,
        range_vals_bd,
        0.1,
        params_drain,
        0.1
    )
    check("Level saturates at output_low (0.0)", level >= 0.0, level)

    # ------------------------------------------------------------------ #
    # Test 9: Noise injection with non-zero sensor_noise                 #
    # ------------------------------------------------------------------ #
    print("\nTest 9: Sensor noise — multiple calls should produce varying flow_in")
    params_noisy = [50.0, 4.0, 1.0, 0.0, 1.0, 2.0, 5.0]  # sensor_noise = 2.0
    fi_values = []
    state = 30.0
    for _ in range(100):
        _, fi, _, state = tank_model_solve(
            50.0, dt_bd, range_vals_bd, initial_level_bd, params_noisy, state
        )
        fi_values.append(fi)
    unique_vals = len(set(round(v, 8) for v in fi_values))
    check("Noise produces varied flow_in values (>10 unique)", unique_vals > 10, unique_vals)

    # ------------------------------------------------------------------ #
    # Test 10: type safety — no numpy scalars in outputs                 #
    # ------------------------------------------------------------------ #
    print("\nTest 10: Return type safety — all outputs are plain float")
    level, fi, fo, s_out = tank_model_solve(
        50.0, dt_bd, range_vals_bd, initial_level_bd, process_params_bd, 30.0
    )
    check("measured_level is float", type(level) is float, type(level))
    check("flow_in is float",        type(fi) is float,    type(fi))
    check("flow_out is float",       type(fo) is float,    type(fo))
    check("state_out is float",      type(s_out) is float, type(s_out))

    # ------------------------------------------------------------------ #
    # Final result                                                        #
    # ------------------------------------------------------------------ #
    print()
    print("=" * 60)
    if PASS:
        print("OVERALL: PASS — ready to wire into LabVIEW Python Node")
    else:
        print("OVERALL: FAIL — fix errors above before wiring to LabVIEW")
    print("=" * 60)
    sys.exit(0 if PASS else 1)
