import math
import random

# =============================================================================
#  tank.py  —  LabVIEW Python Node  |  LV_Py_C_102
#  Function : tank_model_solve
#
#  Physics-based liquid tank model using first-principles mass balance.
#  Replaces the earlier FOPDT approximation with accurate valve and leak
#  dynamics derived from the LabVIEW Plant System.vi baseline.
#
#  Model overview
#  ---------------
#   Inlet  (HV-101, pump-driven) : Q_in  = process_load  (%/s) when open
#   Outlet (HV-102, gravity)     : Q_out = drain_rate * sqrt(L/100)  (%/s)
#   Leak   (passive, gravity)    : Q_lk  = leak_load  * sqrt(L/100)  (%/s)
#
#   Mass balance (Euler):  L[k] = L[k-1] + dt * (Q_in - Q_out - Q_lk)
#   Hard limits:           L clamped to [0.0, 100.0] %
#
#  Why Torricelli for outlet and leak?
#    Torricelli’s theorem: v = Cv * sqrt(2*g*h)
#    In %-level units this becomes Q = Q_max * sqrt(L / 100).
#    This gives realistic nonlinear drain-rate (faster when full, slower when low)
#    and a natural floor (Q → 0 as L → 0) that prevents negative levels without
#    a hard clamp alone.
#
#  Inlet is pump-driven so Q_in is constant when the valve is open.
#
#  PARAMETER ORDER IS LOCKED to the LabVIEW block-diagram terminal order.
#  Do NOT reorder parameters once the VI is wired.
#  Append new parameters at END only; create a _v2 function for restructuring.
#
#  Pre-integration test:
#    python tank.py          <- must print OVERALL: PASS before wiring to LabVIEW
# =============================================================================


def tank_model_solve(
    state_in,       # list[float]  Shift-register state: [tank_level_pct]
                    #              Init shift register to [initial_level].
    reinitialize,   # int          1 = reset level to initial_level; 0 = run
    process_load,   # float        HV-101 inlet flow rate (%/s at full open)
    hv_101,         # int          Inlet  valve HV-101: 1 = open, 0 = closed
    leak_load,      # float        Passive leak rate coefficient (%/s at 100% level)
                    #              Actual leak = leak_load * sqrt(level / 100)
    hv_102,         # int          Outlet valve HV-102: 1 = open, 0 = closed
    drain_rate,     # float        HV-102 drain rate coefficient (%/s at 100% level)
                    #              Actual drain = drain_rate * sqrt(level / 100)
    initial_level,  # float        Initial tank level (%)
    sensor_noise,   # float        Peak sensor noise amplitude (%)
    dt              # float        Sample interval (s).  Must be > 0.
):
    """
    Physics-based liquid tank model for the LabVIEW Python Node.

    Derived from the Plant System.vi baseline (LV PID / subVIs) but replaces
    the FOPDT transfer-function approximation with a true mass-balance ODE
    integrated with forward Euler.

    Two controllable valves
    -----------------------
    HV-101 (inlet)  — pump-driven: constant Q_in when open
    HV-102 (outlet) — gravity:     Q_out = drain_rate  * sqrt(level / 100)

    Passive leak
    ------------
    Always active.  Gravity-driven: Q_leak = leak_load * sqrt(level / 100)
    Models a small orifice, crack, or weep hole in the tank wall.
    At 100% level  : Q_leak = leak_load  (maximum)
    At   0% level  : Q_leak = 0          (no head, no flow)

    Inputs (positional, in block-diagram terminal order)
    -------------------------------------------------------
    state_in       list[float]  [level_pct] — length-1 list
    reinitialize   int          1 = reset; 0 = run from state_in
    process_load   float        Inlet flow coefficient (%/s)       [terminal 3]
    hv_101         int          1 = inlet  valve open              [terminal 4]
    leak_load      float        Leak coefficient (%/s at 100%)     [terminal 5]
    hv_102         int          1 = outlet valve open              [terminal 6]
    drain_rate     float        Drain coefficient (%/s at 100%)    [terminal 7]
    initial_level  float        Starting level (%)                 [terminal 8]
    sensor_noise   float        Sensor noise amplitude (%)         [terminal 9]
    dt             float        Sample time (s)                    [terminal 10]

    Returns  (tuple — 4 elements)
    -------------------------------------------------------
    tank_level       float        Measured level with sensor noise (%)
    flow_sensor_in   int          1 if HV-101 open and Q_in  > 0; else 0
    flow_sensor_out  int          1 if HV-102 open and Q_out > 0; else 0
    state_out        list[float]  Updated state [new_level_pct] — wire to shift reg
    """
    # ------------------------------------------------------------------
    # 1. Sanitise scalars
    # ------------------------------------------------------------------
    dt_s   = max(float(dt), 1e-6)          # guard against zero or negative dt
    L0     = float(initial_level)
    sn     = float(sensor_noise)
    ql_max = max(float(leak_load),  0.0)   # leak coeff cannot be negative
    qd_max = max(float(drain_rate), 0.0)   # drain coeff cannot be negative
    qi_max = max(float(process_load), 0.0) # inlet flow cannot be negative

    # ------------------------------------------------------------------
    # 2. Restore or reinitialise state
    #    State vector is length-1: [tank_level_%]
    # ------------------------------------------------------------------
    if int(reinitialize) or len(state_in) < 1:
        level = L0
    else:
        level = max(0.0, min(100.0, float(state_in[0])))

    # ------------------------------------------------------------------
    # 3. Torricelli helper
    #    sqrt_head = sqrt(level / 100) — range [0, 1]
    #    Represents normalised hydraulic head driving gravity flows.
    # ------------------------------------------------------------------
    sqrt_head = math.sqrt(max(level, 0.0) / 100.0)

    # ------------------------------------------------------------------
    # 4. Case structure: HV-101 inlet valve (pump-driven, constant Q)
    #
    #    TRUE  (hv_101 == 1): valve open  — constant inflow
    #    FALSE (hv_101 == 0): valve closed — no inflow
    # ------------------------------------------------------------------
    if int(hv_101):
        Q_in           = qi_max        # %/s, constant (pump-driven)
        flow_sensor_in = 1
    else:
        Q_in           = 0.0
        flow_sensor_in = 0

    # ------------------------------------------------------------------
    # 5. Case structure: HV-102 outlet valve (gravity-driven, Torricelli)
    #
    #    TRUE  (hv_102 == 1): valve open  — Q_out = drain_rate * sqrt(L/100)
    #    FALSE (hv_102 == 0): valve closed — no outlet flow
    # ------------------------------------------------------------------
    if int(hv_102):
        Q_out           = qd_max * sqrt_head   # %/s, decreases as level drops
        flow_sensor_out = 1 if Q_out > 0.0 else 0
    else:
        Q_out           = 0.0
        flow_sensor_out = 0

    # ------------------------------------------------------------------
    # 6. Passive leak — always active, gravity-driven (Torricelli)
    #    Q_leak = leak_load * sqrt(level / 100)
    #    Naturally goes to zero as the tank empties.
    # ------------------------------------------------------------------
    Q_leak = ql_max * sqrt_head

    # ------------------------------------------------------------------
    # 7. Mass balance Euler integration
    #    dL/dt = Q_in - Q_out - Q_leak
    #    L[k] = L[k-1] + dt * dL_dt
    # ------------------------------------------------------------------
    dL_dt     = Q_in - Q_out - Q_leak
    new_level = level + dt_s * dL_dt

    # ------------------------------------------------------------------
    # 8. Hard tank limits — clamp to [0, 100] %
    #    The Torricelli model already soft-limits draining to zero,
    #    but the pump fill can still overflow without this clamp.
    # ------------------------------------------------------------------
    new_level = max(0.0, min(100.0, new_level))

    # ------------------------------------------------------------------
    # 9. Sensor noise on measured output
    # ------------------------------------------------------------------
    noise_s        = sn * (2.0 * random.random() - 1.0) if sn > 0.0 else 0.0
    measured_level = max(0.0, min(100.0, new_level + noise_s))

    # ------------------------------------------------------------------
    # 10. Pack updated state for shift register
    # ------------------------------------------------------------------
    state_out = [new_level]

    return (float(measured_level), int(flow_sensor_in), int(flow_sensor_out), state_out)


# =============================================================================
#  Standalone smoke test
#  Run: python tank.py
#  All steps must print PASS before wiring into LabVIEW.
# =============================================================================
if __name__ == "__main__":
    import sys

    _PASS_ALL = True

    def _chk(label, condition, detail=None):
        global _PASS_ALL
        tag = "PASS" if condition else "FAIL"
        if not condition:
            _PASS_ALL = False
        suffix = f"  (got: {detail})" if (detail is not None and not condition) else ""
        print(f"  {tag}: {label}{suffix}")

    # Default parameters matching Plant System.vi front-panel values
    _proc  = 25.0   # HV-101 inlet flow  (%/s)
    _leak  =  5.0   # passive leak coeff (%/s at 100 %)
    _drain = 30.0   # HV-102 drain coeff (%/s at 100 %)
    _L0    = 30.0   # initial level (%)
    _sn    =  0.0   # sensor noise (off for deterministic tests)
    _dt    =  0.1   # 100 ms sample time

    def _run(state, reinit, hv1, hv2,
             proc=_proc, leak=_leak, drain=_drain,
             L0=_L0, sn=_sn, dt=_dt):
        return tank_model_solve(
            state, reinit, proc, hv1, leak, hv2, drain, L0, sn, dt
        )

    print("=" * 64)
    print("tank_model_solve (physics model) — smoke test (6 steps)")
    print("=" * 64)

    # ------------------------------------------------------------------
    # Step 1: Return-type checks and reinitialize resets to initial_level
    # ------------------------------------------------------------------
    print("\nStep 1: return types and reinitialize")
    lv, fi, fo, s = _run([99.0], 1, 1, 0)   # reinit forces level = _L0
    _chk("tank_level is float",        isinstance(lv, float),  type(lv))
    _chk("flow_sensor_in  is int",     isinstance(fi, int),    type(fi))
    _chk("flow_sensor_out is int",     isinstance(fo, int),    type(fo))
    _chk("state_out is list",          isinstance(s,  list),   type(s))
    _chk("state_out length == 1",      len(s) == 1,            len(s))
    _chk("level near initial after reinit", abs(s[0] - _L0) < 1.0, s[0])

    # ------------------------------------------------------------------
    # Step 2: HV-101 open, HV-102 closed — tank fills toward 100 %
    # ------------------------------------------------------------------
    print("\nStep 2: HV-101 open, HV-102 closed — tank fills")
    state = [_L0]
    for _ in range(300):                     # 30 s simulation
        lv, fi, fo, state = _run(state, 0, 1, 0)
    _chk("level rose above initial",   state[0] > _L0,           round(state[0], 2))
    _chk("flow_sensor_in  == 1",       fi == 1,                  fi)
    _chk("flow_sensor_out == 0",       fo == 0,                  fo)

    # ------------------------------------------------------------------
    # Step 3: HV-101 closed, HV-102 open — gravity drain from 80 %
    # ------------------------------------------------------------------
    print("\nStep 3: HV-101 closed, HV-102 open — tank drains")
    state = [80.0]
    for _ in range(200):
        lv, fi, fo, state = _run(state, 0, 0, 1)
    _chk("level dropped below 80 %",   state[0] < 80.0,          round(state[0], 2))
    _chk("flow_sensor_in  == 0",       fi == 0,                  fi)

    # ------------------------------------------------------------------
    # Step 4: Both valves closed — only passive leak drains tank
    # ------------------------------------------------------------------
    print("\nStep 4: both valves closed — leak drains tank slowly")
    state = [60.0]
    start_level = state[0]
    for _ in range(100):
        lv, fi, fo, state = _run(state, 0, 0, 0)
    _chk("level dropped due to leak",  state[0] < start_level,   round(state[0], 2))
    _chk("flow_sensor_in  == 0",       fi == 0,                  fi)
    _chk("flow_sensor_out == 0",       fo == 0,                  fo)

    # ------------------------------------------------------------------
    # Step 5: Level approaches nonlinear steady state
    #   SS condition (both valves open):
    #     Q_in = (drain_rate + leak_load) * sqrt(L_ss/100)
    #     L_ss = 100 * (Q_in / (drain_rate + leak_load))^2
    # ------------------------------------------------------------------
    print("\nStep 5: steady state with both valves open")
    L_ss_theory = 100.0 * (_proc / (_drain + _leak)) ** 2
    state = [_L0]
    for _ in range(3000):                    # 300 s — long enough to converge
        _, _, _, state = _run(state, 0, 1, 1)
    _chk("level near theoretical SS (within 3 %)",
         abs(state[0] - L_ss_theory) < 3.0,
         f"got={round(state[0],2)}  theory={round(L_ss_theory,2)}")

    # ------------------------------------------------------------------
    # Step 6: Level clamped — cannot exceed 100 % or go below 0 %
    # ------------------------------------------------------------------
    print("\nStep 6: hard level limits [0, 100] %")
    state = [99.0]
    for _ in range(500):
        lv_hi, _, _, state = _run(state, 0, 1, 0, leak=0.0, drain=0.0)
    _chk("level does not exceed 100 %", state[0] <= 100.0, round(state[0], 4))
    state = [1.0]
    for _ in range(500):
        lv_lo, _, _, state = _run(state, 0, 0, 1)
    _chk("level does not go below 0 %",  state[0] >= 0.0,  round(state[0], 4))

    print()
    print("=" * 64)
    overall = "PASS" if _PASS_ALL else "FAIL"
    print(f"OVERALL: {overall}")
    print("=" * 64)
    sys.exit(0 if _PASS_ALL else 1)
