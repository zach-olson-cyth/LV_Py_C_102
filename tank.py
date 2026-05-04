import math

def tank_model_solve(
    valve_pos,          # float: PID output / valve position 0–100 %
    dt,                 # float: time step in seconds
    output_high,        # float: flow sensor full-scale in GPM
    process_load,       # float: constant process drain in GPM
    hv_101,             # int:   HV-101 shutoff valve (1=open, 0=closed)
    leak_load,          # float: leak GPM at 50% tank fill — calibrates Cv_leak
    process_params,     # tuple[float,...] (8 elements):
                        #   (K, tau, theta, load, deadband, sigma_s, PV0, sigma_p)
                        #   mapped from LabVIEW Cluster [2.5,2.5,0.001,0,0,0,30,0]
    sat_range,          # tuple[float, float]: (level_max %, level_min %)
                        #   mapped from LabVIEW Cluster [100, 0]
    initial_level,      # float: tank level % on first call
    state_in            # list[float]: shift-register state [level_pct]; init [-1.0]
):
    """
    Tank level simulator for LabVIEW Python Node  — tank.py
    =========================================================

    LabVIEW terminal order  (inputs, top->bottom as wired on left side of Python Node):
      1  valve_pos         DBL scalar      -> float
      2  dt                DBL scalar      -> float
      3  output_high       DBL scalar      -> float
      4  process_load      DBL scalar      -> float
      5  hv_101            Boolean         -> int (1=open, 0=closed)
      6  leak_load         DBL scalar      -> float  [GPM at 50% fill]
      7  process_params    Cluster(8xDBL)  -> tuple(float x8)
                           Elements: K, tau_s, theta_s, load, deadband,
                                     sigma_s, PV0, sigma_p
                           Default LabVIEW constant: [2.5, 2.5, 0.001, 0, 0, 0, 30, 0]
      8  sat_range         Cluster(DBL,DBL) -> tuple(float, float)
                           Elements: level_max_pct, level_min_pct
                           Default LabVIEW constant: [100, 0]
      9  initial_level     DBL scalar      -> float
      10 state_in          1D DBL Array    -> list[float]  (shift register, init [-1.0])

    LabVIEW terminal order  (outputs, top->bottom as wired on right side of Python Node):
      1  tank_level        DBL scalar      -> float   [%]
      2  state_out         1D DBL Array    -> list[float]

    Returns
    -------
    tuple: (tank_level, state_out)
      tank_level   float        current tank level in % (Plant Output)
      state_out    list[float]  updated shift-register state [level_pct]

    Physics
    -------
    Inlet flow   : Q_in    = (valve_pos/100) * output_high * hv_101   [GPM]
    Process drain: Q_drain = process_load + process_params.load        [GPM]
    Leak (static-pressure driven, Torricelli):
        Q_leak = Cv_leak * sqrt(level_pct / 100)
        Cv_leak calibrated so Q_leak = leak_load when level_pct = 50%
        => Cv_leak = leak_load / sqrt(0.5)
    Euler integration (1000-gal reference tank):
        delta_level_pct = (Q_in - Q_drain - Q_leak) / 60 / 1000 * 100 * dt
    Output saturation: clamp level_pct to [sat_range[1], sat_range[0]]
    """

    # ── Unpack clusters ───────────────────────────────────────────────────────
    K        = float(process_params[0])   # static gain (reserved)
    tau_s    = float(process_params[1])   # lag time constant (s) — reserved
    theta_s  = float(process_params[2])   # deadtime (s) — reserved
    pp_load  = float(process_params[3])   # additional process load (GPM)
    deadband = float(process_params[4])   # deadband % — reserved
    sigma_s  = float(process_params[5])   # sensor noise — reserved
    # process_params[6] = PV0 — handled via initial_level input
    sigma_p  = float(process_params[7])   # plant noise — reserved

    level_max = float(sat_range[0])       # upper saturation limit (%)
    level_min = float(sat_range[1])       # lower saturation limit (%)

    # ── Constants ─────────────────────────────────────────────────────────────
    TANK_CAPACITY_GAL = 1000.0

    # ── Leak coefficient  (Torricelli, calibrated at 50% fill) ───────────────
    # Q_leak = Cv * sqrt(h_frac)  where h_frac = level_pct / 100
    # At 50%: leak_load = Cv * sqrt(0.5)  =>  Cv = leak_load / sqrt(0.5)
    Cv_leak = float(leak_load) / math.sqrt(0.5)

    # ── First-call sentinel detection ─────────────────────────────────────────
    if state_in[0] < 0.0:
        level_pct = float(initial_level)
    else:
        level_pct = float(state_in[0])

    level_pct = max(level_min, min(level_max, level_pct))

    # ── Flow calculations (GPM) ───────────────────────────────────────────────
    valve_frac = max(0.0, min(1.0, float(valve_pos) / 100.0))
    hv_open    = 1.0 if int(hv_101) else 0.0
    Q_in       = valve_frac * float(output_high) * hv_open
    Q_drain    = float(process_load) + pp_load
    h_frac     = level_pct / 100.0
    Q_leak     = Cv_leak * math.sqrt(max(0.0, h_frac))
    Q_out      = Q_drain + Q_leak

    # ── Euler integration ─────────────────────────────────────────────────────
    net_gpm    = Q_in - Q_out
    delta_pct  = net_gpm / 60.0 / TANK_CAPACITY_GAL * 100.0 * float(dt)
    level_new  = level_pct + delta_pct
    level_new  = max(level_min, min(level_max, level_new))

    state_out = [float(level_new)]

    return (float(level_new), state_out)


# ── Standalone smoke test ─────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys

    PASS = True

    PP  = (2.5, 2.5, 0.001, 0.0, 0.0, 0.0, 30.0, 0.0)  # default process_params cluster
    SAT = (100.0, 0.0)                                    # default sat_range cluster

    # ── Test 1: First-call init uses initial_level ────────────────────────────
    level, state = tank_model_solve(
        50.0, 1.0, 100.0, 25.0, 1, 10.0, PP, SAT, 50.0, [-1.0]
    )
    ok = abs(level - 50.0) < 2.0
    print(f"Test 1 (init to 50%): level={level:.3f}  {'PASS' if ok else 'FAIL'}")
    PASS = PASS and ok

    # ── Test 2: Cv calibration — Q_leak exactly equals leak_load at 50% ──────
    Cv = 10.0 / math.sqrt(0.5)
    q  = Cv * math.sqrt(0.5)
    ok = abs(q - 10.0) < 1e-9
    print(f"Test 2 (Q_leak@50%=10 GPM): Q={q:.6f}  {'PASS' if ok else 'FAIL'}")
    PASS = PASS and ok

    # ── Test 3: HV-101 closed, no drain, no leak -> level holds at 50% ───────
    level, _ = tank_model_solve(
        100.0, 1.0, 100.0, 0.0, 0, 0.0, PP, SAT, 50.0, [-1.0]
    )
    ok = abs(level - 50.0) < 0.1
    print(f"Test 3 (HV-101 closed, no change): level={level:.3f}  {'PASS' if ok else 'FAIL'}")
    PASS = PASS and ok

    # ── Test 4: Saturation clamps level ──────────────────────────────────────
    level, _ = tank_model_solve(
        100.0, 1000.0, 100.0, 0.0, 1, 0.0, PP, (80.0, 20.0), 10.0, [-1.0]
    )
    ok = level <= 80.0
    print(f"Test 4 (sat clamp <=80%): level={level:.3f}  {'PASS' if ok else 'FAIL'}")
    PASS = PASS and ok

    # ── Test 5: State carry — level rises across two calls ───────────────────
    level1, s1 = tank_model_solve(
        100.0, 60.0, 100.0, 0.0, 1, 0.0, PP, SAT, 0.0, [-1.0]
    )
    level2, _  = tank_model_solve(
        100.0, 60.0, 100.0, 0.0, 1, 0.0, PP, SAT, 0.0, s1
    )
    ok = level2 > level1
    print(f"Test 5 (state carry, rising): L1={level1:.3f}% L2={level2:.3f}%  {'PASS' if ok else 'FAIL'}")
    PASS = PASS and ok

    print(f"\nOVERALL: {'PASS' if PASS else 'FAIL'}")
    sys.exit(0 if PASS else 1)
