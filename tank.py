import math

# =============================================================================
#  tank.py  —  LabVIEW Python Node  |  LV_Py_C_102  |  "LV PID" folder
#  Function : tank_model_solve
#  v3.0 — parameter order locked to block-diagram terminal trace (Apr 2026)
#
#  Liquid tank simulation — first-principles mass balance.
#
#  TERMINAL ORDER (top->bottom, Python Node left side, state_in LAST):
#  +-----+--------------+--------------------------------------------+
#  |  #  |  Name        |  Source in block diagram                   |
#  +-----+--------------+--------------------------------------------+
#  |  1  | valve_pos    | DBL constant / control  "Valve Pos"        |
#  |  2  | dt           | DBL control             "dt"               |
#  |  3  | output_high  | Index Array [100 0] -> index 0 -> 100.0    |
#  |  4  | process_load | DBL constant            "Process load 25"  |
#  |  5  | hv_101       | Boolean control         "HV-101 TF"        |
#  |  6  | leak_load    | DBL constant            "Leak load 10"     |
#  |  7  | initial_level| DBL constant            "Initial level 30" |
#  |  8  | state_in     | Shift-register left terminal (init [-1.0]) |
#  +-----+--------------+--------------------------------------------+
#
#  NOTE on Index Array:
#    The [100 0] array constant feeds an Index Array function.
#    Only index 0 (output_high = 100) is wired to the Python node.
#    Index 1 (output_low = 0) is NOT connected and is NOT a parameter.
#    Rule: only count Index Array outputs that have a wire connected.
#
#  RETURN ORDER (top->bottom, Python Node right side) — 4 outputs only:
#  +-----+----------------+------------------------------------------+
#  |  1  | level          | DBL  current tank level                  |
#  |  2  | flow_sensor_in | TF   1 if HV-101 open and Q_in > 0       |
#  |  3  | flow_sensor_out| TF   1 if valve_pos > 0 and Q_out > 0    |
#  |  4  | state_out      | 1D DBL Array -> shift register right      |
#  +-----+----------------+------------------------------------------+
#
#  PARAMETER ORDER FROZEN once VI is wired.
#  Append new params at END only; use _v2 suffix for restructuring.
#
#  Pre-integration test:  python tank.py   (must print OVERALL: PASS)
# =============================================================================


def tank_model_solve(
    valve_pos,       # float        HV-102 outlet drain coeff (%/s at output_high)    [t1]
    dt,              # float        Sample interval (s)                                 [t2]
    output_high,     # float        Max tank level — Index Array [100 0] index 0        [t3]
    process_load,    # float        HV-101 inlet flow rate (%/s, pump-driven constant)  [t4]
    hv_101,          # int          Inlet valve HV-101: 1 = open, 0 = closed            [t5]
    leak_load,       # float        Passive leak coeff (%/s at output_high, Torricelli) [t6]
    initial_level,   # float        Starting level (same units as output_high)          [t7]
    state_in,        # list[float]  Shift-register state: [level]  LAST terminal        [t8]
                     #              *** Init LabVIEW shift register to [-1.0] ***
                     #              state_in[0] < 0 triggers first-call initialisation
):
    """
    Physics-based tank model for the LabVIEW Python Node.

    Terminal / parameter order is LOCKED to the LV PID block diagram.
    See module header table for the exact wire-trace mapping.

    Model physics
    -------------
    HV-101 inlet  (pump-driven)  : Q_in   = process_load           when hv_101 = 1
    HV-102 outlet (gravity)      : Q_out  = valve_pos  * sqrt(L / output_high)
    Passive leak  (gravity)      : Q_leak = leak_load  * sqrt(L / output_high)

    Euler integration:
        dL/dt  = Q_in - Q_out - Q_leak
        L[k]   = L[k-1] + dt * dL/dt
        L clamped to [0, output_high]

    First-call initialization (no reinitialize boolean needed)
    ----------------------------------------------------------
    Set the LabVIEW shift register left-terminal constant to [-1.0].
    On the first iteration state_in[0] < 0, so Python resets level
    to initial_level automatically.  All subsequent calls use the
    fed-back state value.

    Inputs (positional, block-diagram terminal order, state_in LAST)
    -----------------------------------------------------------------
    valve_pos      float        HV-102 drain coeff (%/s at output_high)   [t1]
    dt             float        Sample interval (s)                        [t2]
    output_high    float        Max tank level (from Index Array index 0)  [t3]
    process_load   float        HV-101 inlet flow rate (%/s)               [t4]
    hv_101         int          1 = inlet valve open                       [t5]
    leak_load      float        Passive leak coeff (%/s at output_high)    [t6]
    initial_level  float        Starting level                             [t7]
    state_in       list[float]  [level] shift register -- LAST             [t8]

    Returns (tuple, 4 elements -- matches right-side terminal order)
    ----------------------------------------------------------------
    level           float        Current tank level
    flow_sensor_in  int          1 if HV-101 open and Q_in > 0; else 0
    flow_sensor_out int          1 if valve_pos > 0 and Q_out > 0; else 0
    state_out       list[float]  [level] -- wire to shift-register right terminal
    """
    # ------------------------------------------------------------------
    # 1. Sanitise inputs
    # ------------------------------------------------------------------
    dt_s = max(float(dt), 1e-6)
    oh   = max(float(output_high), 1e-6)     # prevent divide-by-zero
    vp   = max(float(valve_pos),    0.0)
    qi   = max(float(process_load), 0.0)
    ql   = max(float(leak_load),    0.0)
    L0   = float(initial_level)

    # ------------------------------------------------------------------
    # 2. First-call detection via sentinel
    #    Shift register must be initialised to [-1.0] in LabVIEW.
    #    Any negative state_in[0] resets level to initial_level.
    # ------------------------------------------------------------------
    if len(state_in) < 1 or float(state_in[0]) < 0.0:
        level = L0
    else:
        level = max(0.0, min(oh, float(state_in[0])))

    # ------------------------------------------------------------------
    # 3. Torricelli head factor   sqrt(L / output_high)  in [0, 1]
    #    Gravity-driven flows scale with hydraulic head.
    # ------------------------------------------------------------------
    sqrt_head = math.sqrt(max(level, 0.0) / oh)

    # ------------------------------------------------------------------
    # 4. Case structure -- HV-101 inlet valve (pump-driven, constant Q)
    #    TRUE  : valve open  -- constant inflow Q_in = process_load
    #    FALSE : valve closed -- no inflow
    # ------------------------------------------------------------------
    if int(hv_101):
        Q_in           = qi
        flow_sensor_in = 1
    else:
        Q_in           = 0.0
        flow_sensor_in = 0

    # ------------------------------------------------------------------
    # 5. HV-102 outlet valve (gravity-driven, Torricelli)
    #    valve_pos is the drain coefficient in %/s at output_high level.
    #    Q_out = valve_pos * sqrt(level / output_high)
    # ------------------------------------------------------------------
    Q_out           = vp * sqrt_head
    flow_sensor_out = 1 if Q_out > 0.0 else 0

    # ------------------------------------------------------------------
    # 6. Passive leak -- always active, gravity-driven (Torricelli)
    #    Q_leak = leak_load * sqrt(level / output_high)
    # ------------------------------------------------------------------
    Q_leak = ql * sqrt_head

    # ------------------------------------------------------------------
    # 7. Euler mass balance and hard level clamp
    # ------------------------------------------------------------------
    new_level = level + dt_s * (Q_in - Q_out - Q_leak)
    new_level = max(0.0, min(oh, new_level))

    # ------------------------------------------------------------------
    # 8. Return -- order matches Python Node right-side terminal order
    # ------------------------------------------------------------------
    return (
        float(new_level),       # 1  level
        int(flow_sensor_in),    # 2  flow_sensor_in
        int(flow_sensor_out),   # 3  flow_sensor_out
        [new_level],            # 4  state_out  (list[float] -> shift register)
    )


# =============================================================================
#  Standalone smoke test
#  Run:  python tank.py
#  All steps must print PASS and final line must read OVERALL: PASS
#  before wiring into LabVIEW.
# =============================================================================
if __name__ == "__main__":
    import sys

    _PASS_ALL = True

    def _chk(label, cond, detail=None):
        global _PASS_ALL
        if not cond:
            _PASS_ALL = False
        tag = "PASS" if cond else "FAIL"
        sfx = f"  (got: {detail})" if detail is not None and not cond else ""
        print(f"  {tag}: {label}{sfx}")

    # Block-diagram default values
    _VP   = 30.0    # valve_pos    -- HV-102 drain coeff  (%/s at 100 %)
    _DT   =  0.1    # dt           -- 100 ms sample time
    _OH   = 100.0   # output_high  -- from [100 0] index 0
    _PL   = 25.0    # process_load -- inlet flow
    _LL   =  5.0    # leak_load
    _L0   = 30.0    # initial_level
    _SENT = [-1.0]  # shift-register sentinel (LabVIEW init value)

    def _run(state, hv1, vp=_VP, dt=_DT, oh=_OH, pl=_PL, ll=_LL, L0=_L0):
        """Convenience wrapper preserving block-diagram terminal order."""
        return tank_model_solve(vp, dt, oh, pl, hv1, ll, L0, state)

    print("=" * 60)
    print("tank_model_solve v3  --  smoke test")
    print("=" * 60)

    # ------------------------------------------------------------------
    # Step 1: Return types and first-call sentinel initialisation
    # ------------------------------------------------------------------
    print("\nStep 1: return types and first-call init via sentinel")
    lv, fi, fo, so = _run(_SENT, 0)
    _chk("level is float",            isinstance(lv, float), type(lv))
    _chk("flow_sensor_in  is int",     isinstance(fi, int),   type(fi))
    _chk("flow_sensor_out is int",     isinstance(fo, int),   type(fo))
    _chk("state_out is list",          isinstance(so, list),  type(so))
    _chk("state_out length == 1",      len(so) == 1,          len(so))
    _chk("sentinel init -> initial_level", abs(lv - _L0) < 0.5, round(lv, 3))

    # ------------------------------------------------------------------
    # Step 2: HV-101 open, valve_pos=0 -- tank fills toward output_high
    # ------------------------------------------------------------------
    print("\nStep 2: HV-101 open, valve_pos=0 -- tank fills")
    s = [_L0]
    for _ in range(200):
        lv, fi, fo, s = _run(s, 1, vp=0.0)
    _chk("level rose above initial",   s[0] > _L0,  round(s[0], 2))
    _chk("flow_sensor_in  == 1",        fi == 1,      fi)
    _chk("flow_sensor_out == 0",        fo == 0,      fo)

    # ------------------------------------------------------------------
    # Step 3: HV-101 closed, valve_pos>0 -- tank drains
    # ------------------------------------------------------------------
    print("\nStep 3: HV-101 closed, valve_pos=30 -- tank drains")
    s = [80.0]
    for _ in range(200):
        lv, fi, fo, s = _run(s, 0)
    _chk("level dropped below 80",     s[0] < 80.0, round(s[0], 2))
    _chk("flow_sensor_in  == 0",        fi == 0,      fi)

    # ------------------------------------------------------------------
    # Step 4: Both off -- only passive leak drains
    # ------------------------------------------------------------------
    print("\nStep 4: both off -- passive leak only")
    s = [60.0]; start = s[0]
    for _ in range(100):
        lv, fi, fo, s = _run(s, 0, vp=0.0)
    _chk("level dropped due to leak",  s[0] < start, round(s[0], 2))
    _chk("flow_sensor_in  == 0",        fi == 0,       fi)
    _chk("flow_sensor_out == 0",        fo == 0,       fo)

    # ------------------------------------------------------------------
    # Step 5: Steady-state with both open
    #   Q_in = (valve_pos + leak_load) * sqrt(L_ss / output_high)
    #   L_ss = output_high * (process_load / (valve_pos + leak_load))^2
    # ------------------------------------------------------------------
    print("\nStep 5: steady-state with both open")
    L_ss = _OH * (_PL / (_VP + _LL)) ** 2
    s = [_L0]
    for _ in range(5000):
        _, _, _, s = _run(s, 1)
    _chk(f"level near theory {round(L_ss, 1)} % (within 3)",
         abs(s[0] - L_ss) < 3.0,
         f"got={round(s[0], 2)}  theory={round(L_ss, 2)}")

    # ------------------------------------------------------------------
    # Step 6: Hard level limits [0, output_high]
    # ------------------------------------------------------------------
    print("\nStep 6: hard level limits [0, output_high]")
    s = [99.0]
    for _ in range(500):
        lv, _, _, s = _run(s, 1, vp=0.0, ll=0.0)
    _chk("level does not exceed output_high", s[0] <= _OH, round(s[0], 4))

    s = [1.0]
    for _ in range(500):
        lv, _, _, s = _run(s, 0, vp=_VP)
    _chk("level does not go below 0",          s[0] >= 0.0, round(s[0], 4))

    print()
    print("=" * 60)
    print(f"OVERALL: {'PASS' if _PASS_ALL else 'FAIL'}")
    print("=" * 60)
    sys.exit(0 if _PASS_ALL else 1)
