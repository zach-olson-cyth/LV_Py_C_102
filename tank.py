import math
import random

# =============================================================================
#  tank.py  —  LabVIEW Python Node  |  LV_Py_C_102
#  Function : tank_model_solve
#
#  Implements a First-Order-Plus-Dead-Time (FOPDT) tank model with:
#    - HV-101 valve case structure (True = fill, False = drain-only)
#    - Deadtime FIFO buffer
#    - Deadband on net input
#    - Plant and sensor noise injection
#    - Stateless design: all state passed in and returned out
#
#  PARAMETER ORDER IS LOCKED to the block-diagram terminal order.
#  Do NOT reorder parameters once the VI is wired.
#  To add new parameters, append at END only and create a _v2 function.
#
#  Pre-integration test:
#    python tank.py          <- must print OVERALL: PASS before wiring to LabVIEW
# =============================================================================


def tank_model_solve(
    state_in,      # list[float]  Shift-reg state: [level, *deadtime_buf]
                   #              Initialise shift register to match expected length.
                   #              For Td=0 and dt=0.1 => length 2: [initial_pv, initial_pv]
    reinitialize,  # int          1 = reset state to initial_pv; 0 = run normally
    process_load,  # float        Inflow rate applied when HV-101 valve is open (%)
    hv_101,        # int          HV-101 valve: 1 = open, 0 = closed
    leak_load,     # float        Constant drain/leak rate, always active (%)
    initial_pv,    # float        Initial tank level (%)          [process params cluster 1]
    static_gain,   # float        FOPDT static gain K              [process params cluster 2]
    lag_s,         # float        FOPDT time constant tau (s)      [process params cluster 3]
    deadtime_s,    # float        FOPDT dead time Td (s)           [process params cluster 4]
    load,          # float        Steady-state load/bias           [process params cluster 5]
    deadband,      # float        Input deadband — blocks small signals (%) [cluster 6]
    sensor_noise,  # float        Peak sensor noise amplitude (%)  [process params cluster 7]
    plant_noise,   # float        Peak plant disturbance amp. (%)  [process params cluster 8]
    dt             # float        Sample interval (s). Pass real elapsed time; must be > 0.
):
    """
    Tank Model — FOPDT plant with deadtime buffer and HV-101 case-structure.

    Mirrors the LabVIEW Plant System.vi FOPDT block (NI PID Toolkit) plus the
    True/False case structure for the HV-101 valve shown in the block diagram.

    Inputs (positional, in block-diagram terminal order)
    -------------------------------------------------------
    state_in      list[float]  [level, dt_buf_0, dt_buf_1, ...]
                               Length must equal 1 + buf_len (see below).
                               buf_len = max(1, round(deadtime_s / dt) + 1)
    reinitialize  int          1 = reset; 0 = continue from state_in
    process_load  float        Inflow when HV-101 is open (%)
    hv_101        int          1 = valve open; 0 = valve closed
    leak_load     float        Constant drain rate, always active (%)
    initial_pv    float        Starting tank level (%)            [cluster 1]
    static_gain   float        Plant gain K                       [cluster 2]
    lag_s         float        Lag time constant tau (s)          [cluster 3]
    deadtime_s    float        Dead time Td (s)                   [cluster 4]
    load          float        Load bias added to net input       [cluster 5]
    deadband      float        Deadband on net input (%)          [cluster 6]
    sensor_noise  float        Sensor noise amplitude (%)         [cluster 7]
    plant_noise   float        Plant disturbance amplitude (%)    [cluster 8]
    dt            float        Sample time (s). Must be > 0.

    Returns  (tuple)
    -------------------------------------------------------
    tank_level    float        Measured tank level with sensor noise (%)
    flow_sensor   int          1 if HV-101 open (flow active); 0 if closed
    state_out     list[float]  Updated state [new_level, *updated_dt_buf]
                               Wire back to the shift register each iteration.
    """
    # ------------------------------------------------------------------
    # 1. Sanitise scalars
    # ------------------------------------------------------------------
    dt_s    = max(float(dt), 1e-6)           # guard against zero / negative dt
    tau     = max(float(lag_s), 1e-9)        # prevent div-by-zero
    K       = float(static_gain)
    Td      = max(float(deadtime_s), 0.0)
    pv0     = float(initial_pv)
    db      = float(deadband)
    sn      = float(sensor_noise)
    pn      = float(plant_noise)
    ld      = float(load)

    # ------------------------------------------------------------------
    # 2. Deadtime buffer length
    #    buf_len >= 1: even with Td=0 a one-element FIFO preserves the
    #    one-sample transport delay that mirrors the LabVIEW shift register.
    # ------------------------------------------------------------------
    buf_len   = max(1, int(round(Td / dt_s)) + 1)
    state_len = 1 + buf_len   # [level, dt_buf_0, ..., dt_buf_{n-1}]

    # ------------------------------------------------------------------
    # 3. Restore state or reinitialise
    # ------------------------------------------------------------------
    if int(reinitialize) or len(state_in) != state_len:
        level  = pv0
        dt_buf = [pv0] * buf_len
    else:
        level  = float(state_in[0])
        dt_buf = [float(state_in[1 + i]) for i in range(buf_len)]

    # ------------------------------------------------------------------
    # 4. Case structure: HV-101 valve determines net tank input
    #
    #    TRUE  case (hv_101 == 1): valve open
    #      net_input = process_load - leak_load + load_bias
    #      Flow sensor = 1 (flow active)
    #
    #    FALSE case (hv_101 == 0): valve closed
    #      net_input = -leak_load + load_bias  (drain only)
    #      Flow sensor = 0
    # ------------------------------------------------------------------
    if int(hv_101):
        # TRUE: main valve open — fill minus drain
        net_input  = float(process_load) - float(leak_load) + ld
        flow_sensor = 1
    else:
        # FALSE: main valve closed — drain only
        net_input  = -float(leak_load) + ld
        flow_sensor = 0

    # ------------------------------------------------------------------
    # 5. Deadband on net input
    #    Mirrors the deadband block in the Plant System VI block diagram.
    #    Signals within [-deadband, +deadband] are treated as zero.
    # ------------------------------------------------------------------
    if abs(net_input) <= db:
        net_input = 0.0

    # ------------------------------------------------------------------
    # 6. Deadtime FIFO — shift oldest value out, push new value in
    #    u_delayed is the input the plant 'sees' this tick.
    # ------------------------------------------------------------------
    u_delayed = dt_buf[0]
    dt_buf    = dt_buf[1:] + [net_input]

    # ------------------------------------------------------------------
    # 7. Plant noise injection (uniform distribution, amplitude = plant_noise)
    # ------------------------------------------------------------------
    noise_p = pn * (2.0 * random.random() - 1.0) if pn > 0.0 else 0.0

    # ------------------------------------------------------------------
    # 8. FOPDT first-order Euler integration
    #    tau * dy/dt = K * u(t - Td) + noise_p - y
    #    Euler forward:
    #      y[k] = y[k-1] + (dt / tau) * (K * u_delayed + noise_p - y[k-1])
    # ------------------------------------------------------------------
    new_level = level + (dt_s / tau) * (K * u_delayed + noise_p - level)

    # ------------------------------------------------------------------
    # 9. Sensor noise on measured output
    # ------------------------------------------------------------------
    noise_s       = sn * (2.0 * random.random() - 1.0) if sn > 0.0 else 0.0
    measured_level = new_level + noise_s

    # ------------------------------------------------------------------
    # 10. Pack updated state for shift register
    # ------------------------------------------------------------------
    state_out = [new_level] + dt_buf

    return (float(measured_level), int(flow_sensor), state_out)


# =============================================================================
#  Standalone smoke test
#  Run: python tank.py
#  All steps must print PASS before wiring into LabVIEW.
# =============================================================================
if __name__ == "__main__":
    import sys

    _PASS_ALL = True

    def _check(label, condition, detail=None):
        global _PASS_ALL
        tag = "PASS" if condition else "FAIL"
        if not condition:
            _PASS_ALL = False
        suffix = f"  (got: {detail})" if (detail is not None and not condition) else ""
        print(f"  {tag}: {label}{suffix}")

    print("=" * 62)
    print("tank_model_solve — smoke test (5 steps)")
    print("=" * 62)

    # Shared defaults matching Plant System front-panel values
    _K    = 2.50
    _tau  = 2.50
    _Td   = 0.00
    _pv0  = 30.0
    _ld   = 0.0
    _db   = 0.0
    _sn   = 0.0
    _pn   = 0.0
    _dt   = 0.1    # 100 ms sample time

    # Helper to call the function with defaults
    def _run(state, reinit, proc_load, hv, leak,
             pv0=_pv0, K=_K, tau=_tau, Td=_Td,
             ld=_ld, db=_db, sn=_sn, pn=_pn, dt=_dt):
        return tank_model_solve(
            state, reinit, proc_load, hv, leak,
            pv0, K, tau, Td, ld, db, sn, pn, dt
        )

    # ------------------------------------------------------------------
    # Step 1: reinitialize=1 resets level to initial_pv
    # ------------------------------------------------------------------
    print("\nStep 1: reinitialize resets state to initial_pv")
    lv1, fs1, s1 = _run([0.0, 0.0], 1, 25.0, 1, 10.0)
    _check("tank_level is float",        isinstance(lv1, float),  type(lv1))
    _check("flow_sensor is int",         isinstance(fs1, int),    type(fs1))
    _check("state_out is list",          isinstance(s1,  list),   type(s1))
    _check("level near initial_pv after reinit", abs(s1[0] - _pv0) < 5.0, s1[0])

    # ------------------------------------------------------------------
    # Step 2: HV-101 open — level evolves from initial state over 60 ticks
    # ------------------------------------------------------------------
    print("\nStep 2: HV-101 open — level evolves and flow_sensor=1")
    buf_len2 = max(1, int(round(_Td / _dt)) + 1)
    s2 = [_pv0] + [0.0] * buf_len2           # initial shift-register value
    lv_start = s2[0]
    for _ in range(60):
        lv2, fs2, s2 = _run(s2, 0, 25.0, 1, 10.0)
    _check("level changed after 60 ticks",   abs(s2[0] - lv_start) > 0.01, s2[0])
    _check("flow_sensor=1 when HV-101 open", fs2 == 1, fs2)
    _check("state_out length stable",        len(s2) == 1 + buf_len2, len(s2))

    # ------------------------------------------------------------------
    # Step 3: HV-101 closed — only leak active, level drops from 50 %
    # ------------------------------------------------------------------
    print("\nStep 3: HV-101 closed — level drops (leak only)")
    s3 = [50.0] + [0.0] * buf_len2
    for _ in range(40):
        lv3, fs3, s3 = _run(s3, 0, 25.0, 0, 10.0)   # hv_101=0
    _check("level < 50 % after 40 ticks with valve closed", s3[0] < 50.0, s3[0])
    _check("flow_sensor=0 when HV-101 closed",              fs3 == 0, fs3)

    # ------------------------------------------------------------------
    # Step 4: Deadband blocks small inputs (visible after 2-step delay)
    # ------------------------------------------------------------------
    print("\nStep 4: Deadband blocks small net inputs")
    s_db  = [_pv0, _pv0]           # 1 element deadtime buf initialised to pv0
    s_ndb = [_pv0, _pv0]
    # Step 4a — first tick: both see same u_delayed (pv0 from buf)
    _, _, s_db  = _run(s_db,  0, 0.5, 1, 0.4, db=0.5)   # net=0.1 < db → blocked
    _, _, s_ndb = _run(s_ndb, 0, 0.5, 1, 0.4, db=0.0)   # net=0.1, no deadband
    # Step 4b — second tick: u_delayed now differs (0 vs 0.1)
    lv_db2, _, _ = _run(s_db,  0, 0.5, 1, 0.4, db=0.5)
    lv_ndb2, _, _ = _run(s_ndb, 0, 0.5, 1, 0.4, db=0.0)
    _check("deadband case level differs from no-deadband after 2 ticks",
           lv_db2 != lv_ndb2, (round(lv_db2, 4), round(lv_ndb2, 4)))

    # ------------------------------------------------------------------
    # Step 5: State vector length correct for various deadtimes
    # ------------------------------------------------------------------
    print("\nStep 5: state_out length correct for Td = 0, 0.5, 1.0, 2.0 s")
    for Td_test in [0.0, 0.5, 1.0, 2.0]:
        buf_exp = max(1, int(round(Td_test / _dt)) + 1)
        exp_len = 1 + buf_exp
        _, _, s_td = tank_model_solve(
            [_pv0], 1, 10.0, 1, 5.0,          # len-1 state triggers reset
            _pv0, _K, _tau, Td_test,
            _ld, _db, _sn, _pn, _dt
        )
        _check(f"Td={Td_test}s → state_out length={exp_len}",
               len(s_td) == exp_len, len(s_td))

    print()
    print("=" * 62)
    overall = "PASS" if _PASS_ALL else "FAIL"
    print(f"OVERALL: {overall}")
    print("=" * 62)
    sys.exit(0 if _PASS_ALL else 1)
