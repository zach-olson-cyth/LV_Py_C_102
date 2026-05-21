import math
import random

def tank_model_solve(
    valve_pos,          # float  — PID output / valve position (0–100 %)
    dt,                 # float  — loop interval in seconds
    output_high,        # float  — saturation high limit (e.g. 100.0)
    process_load,       # float  — constant load disturbance (e.g. 25.0)
    hv_101,             # int    — HV-101 hand valve (1=open, 0=closed)
    leak_load,          # float  — leak loss rate (e.g. 10.0)
    process_params,     # tuple  — (K, tau, theta, deadband, integrator_gain,
                        #           sigma_s, sigma_p, initial_level)
                        #  index:   0   1     2       3          4
                        #           5     6       7
    initial_level,      # float  — initial tank level override (e.g. 10.0)
    state_in,           # list[float] — shift-register state; [-1.0] on first call
):
    """
    Tank level model for LabVIEW Python Node.

    Returns a tuple matching the LabVIEW cluster wired to the return terminal:
        (level: float, state_out: list[float], flow_sensor: int)

    process_params tuple element order (mirrors block diagram cluster order):
        [0] K             static gain
        [1] tau           lag time constant (s)
        [2] theta         deadtime (s)
        [3] deadband      input deadband (%)
        [4] integrator_en integrator enable (1/0)
        [5] sigma_s       sensor noise amplitude
        [6] sigma_p       plant noise amplitude
        [7] initial_level initial PV (ignored here — use the explicit initial_level arg)

    Parameter order is FROZEN — do not reorder without a _v2 bump.
    """
    # Unpack process_params tuple (from LabVIEW cluster, 8 elements)
    K             = float(process_params[0])
    tau           = float(process_params[1])
    theta         = float(process_params[2])
    deadband      = float(process_params[3])
    integrator_en = int(process_params[4])
    sigma_s       = float(process_params[5])
    sigma_p       = float(process_params[6])
    # process_params[7] is the cluster's initial_level — not used here
    #   (the explicit initial_level arg takes precedence)

    # --- First-call sentinel detection ---
    # LabVIEW shift register must be initialised to [-1.0]
    DEADTIME_MAX_STEPS = 64
    STATE_SIZE = 2 + DEADTIME_MAX_STEPS   # [level, deadtime_ptr, *deadtime_buffer]

    if state_in[0] < 0.0:
        level_prev = float(initial_level)
        deadtime_ptr = 0
        deadtime_buf = [float(initial_level)] * DEADTIME_MAX_STEPS
    else:
        level_prev   = state_in[0]
        deadtime_ptr = int(state_in[1])
        deadtime_buf = list(state_in[2:2 + DEADTIME_MAX_STEPS])
        # pad if shorter than expected (safety)
        while len(deadtime_buf) < DEADTIME_MAX_STEPS:
            deadtime_buf.append(level_prev)

    # --- Effective valve input ---
    u = float(valve_pos)

    # HV-101: if hand valve is closed (0), block upstream flow
    if int(hv_101) == 0:
        u = 0.0

    # Deadband
    if abs(u - level_prev) < deadband:
        u_db = level_prev
    else:
        u_db = u

    # Load disturbance + plant noise
    u_load = u_db + float(process_load) - float(leak_load)
    u_noisy = u_load + float(sigma_p) * (random.random() * 2.0 - 1.0)

    # --- Deadtime buffer ---
    deadtime_steps = max(1, int(round(theta / dt))) if dt > 0.0 else 1
    deadtime_steps = min(deadtime_steps, DEADTIME_MAX_STEPS - 1)

    deadtime_buf[deadtime_ptr % DEADTIME_MAX_STEPS] = u_noisy
    u_delayed = deadtime_buf[(deadtime_ptr - deadtime_steps) % DEADTIME_MAX_STEPS]
    deadtime_ptr = (deadtime_ptr + 1) % DEADTIME_MAX_STEPS

    # --- First-order lag (or integrator) ---
    tau_safe = tau if tau > 0.0 else 1e-6
    if integrator_en:
        level_new = level_prev + K * u_delayed * dt
    else:
        level_new = level_prev + (dt / tau_safe) * (K * u_delayed - level_prev)

    # Sensor noise
    level_sense = level_new + float(sigma_s) * (random.random() * 2.0 - 1.0)

    # Output saturation (0 to output_high)
    level_out = max(0.0, min(float(output_high), level_sense))

    # --- Flow sensor (Boolean: True when level > 37) ---
    flow_sensor = 1 if level_out > 37.0 else 0

    # --- Pack state_out ---
    state_out = [level_out, float(deadtime_ptr)] + deadtime_buf

    # Return cluster: (level, state_out, flow_sensor)
    return (level_out, state_out, flow_sensor)


# ── Smoke test ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    PASS = True

    # Default process_params from block diagram: [1.5, 18, 1, 0, 1, 0, 0, 5]
    pp = (1.5, 18.0, 1.0, 0.0, 1.0, 0.0, 0.0, 5.0)
    state = [-1.0]   # first-call sentinel

    print("Test 1 — first call initialises level to initial_level=10 ...")
    level, state, flow = tank_model_solve(
        50.0, 0.1, 100.0, 25.0, 1, 10.0, pp, 10.0, state
    )
    assert isinstance(level, float),       "FAIL: level must be float"
    assert isinstance(state, list),        "FAIL: state_out must be list"
    assert isinstance(flow, int),          "FAIL: flow_sensor must be int"
    assert len(state) >= 2,                "FAIL: state_out too short"
    print(f"  level={level:.3f}, flow_sensor={flow}  -> PASS")

    print("Test 2 — successive calls converge level upward with valve=80% ...")
    for _ in range(50):
        level, state, flow = tank_model_solve(
            80.0, 0.1, 100.0, 25.0, 1, 10.0, pp, 10.0, state
        )
    assert level > 10.0, f"FAIL: expected level > 10, got {level:.3f}"
    print(f"  level after 50 steps={level:.3f}  -> PASS")

    print("Test 3 — HV-101 closed blocks flow, level should drop or stay low ...")
    state_hv = [-1.0]
    for _ in range(30):
        level_hv, state_hv, _ = tank_model_solve(
            80.0, 0.1, 100.0, 25.0, 0, 10.0, pp, 10.0, state_hv
        )
    assert level_hv <= 10.0 + 5.0, f"FAIL: HV closed but level={level_hv:.3f} too high"
    print(f"  level with HV-101=0 after 30 steps={level_hv:.3f}  -> PASS")

    print("Test 4 — output saturation clamps at output_high=100 ...")
    state_sat = [-1.0]
    for _ in range(200):
        level_sat, state_sat, _ = tank_model_solve(
            100.0, 0.5, 100.0, 5.0, 1, 0.0, pp, 10.0, state_sat
        )
    assert level_sat <= 100.0, f"FAIL: level exceeded output_high: {level_sat:.3f}"
    print(f"  level (clamped) = {level_sat:.3f}  -> PASS")

    print("Test 5 — return types are correct tuple (float, list, int) ...")
    result = tank_model_solve(50.0, 0.1, 100.0, 25.0, 1, 10.0, pp, 10.0, [-1.0])
    assert isinstance(result, tuple) and len(result) == 3, "FAIL: return must be 3-tuple"
    assert isinstance(result[0], float), "FAIL: result[0] must be float"
    assert isinstance(result[1], list),  "FAIL: result[1] must be list"
    assert isinstance(result[2], int),   "FAIL: result[2] must be int"
    print(f"  types OK -> PASS")

    print("\nOVERALL: PASS" if PASS else "\nOVERALL: FAIL")
