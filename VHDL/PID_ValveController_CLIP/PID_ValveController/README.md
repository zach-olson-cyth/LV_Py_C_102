# PID_ValveController  —  LabVIEW FPGA CLIP Node

Fixed-point 2-DOF PID for valve flow control. 5-stage pipeline, 40 MHz Kintex-7.

## File Index

| File | Purpose |
|------|---------|
| `PID_ValveController.vhd`  | VHDL CLIP entity — 5-stage pipelined FXP PID |
| `PID_ValveController.xml`  | NI CLIP descriptor for LabVIEW FPGA import |
| `test_pid_valve_cocotb.py` | Cocotb testbench — 9 tests, valve plant closed-loop |
| `pid_fxp_reference.py`     | Python FXP reference model + CSV test vector gen |
| `Makefile`                 | GHDL simulation runner |

## NI FXP Port Formats

| Signal | NI Format | VHDL bits | LSB | Range |
|--------|-----------|-----------|-----|-------|
| setpoint, PV, output, Ti(min), Td(min), SP/output limits, manual control | `FXP<+/-,32,16>` | 32 | 1.53e-5 | ±32767 |
| proportional gain (Kc), dt(s), dt out(s) | `FXP<+/-,32,8>` | 32 | 5.96e-8 | ±127 |
| alpha, beta, gamma, linearity | `FXP<+/-,32,2>` | 32 | 9.31e-10 | ±2 |
| auto? (T), reinitialize? (F) | Boolean | 1 | — | — |

## Bit Patterns (LabVIEW wiring / GHDL stimulus reference)

| Signal | Value | Hex | Decimal |
|--------|-------|-----|---------|
| setpoint | 75.0 | 0x004B0000 | 4915200 |
| output high | 100.0 | 0x00640000 | 6553600 |
| output low | -100.0 | 0xFF9C0000 | 4288413696 |
| Kc | 1.0 | 0x01000000 | 16777216 |
| Kc | 5.0 | 0x05000000 | 83886080 |
| dt | 0.1 s | 0x0019999A | 1677722 |
| Ti | 0.1 min | 0x00001999 | 6553 |
| beta | 1.0 | 0x40000000 | 1073741824 |
| alpha (NaN→0) | 0.0 | 0x00000000 | 0 |

## Pipeline Stages

| Stage | Operation | Critical path |
|-------|-----------|---------------|
| 1 | SP clamp, dt/Ti guard, beta×SP, ep/ei | comparators |
| 2 | P = Kc × ep  (32×32 DSP >> 24 → 32) | DSP48 multiply |
| 3 | dI = Kc·ei·dt/(Ti·60·256)  ;  D_raw = -Kc·pv_delta·Td·60/(dt·65536) | divider chain |
| 4 | D_filt = α·D_prev + (1-α)·D_raw  ;  u_raw = P+I+D | adder tree |
| 5 | saturate, anti-windup, auto/manual mux | comparator + mux |

**Latency**: 5 clock cycles.

## Alpha = NaN (Front Panel)

FXP has no NaN encoding. The NaN on the front panel means the control is
**unconnected** — wire a constant `FXP<+/-,32,2> = 0.0` (0x00000000) to the
Alpha CLIP port. This sets α=0 → D passes unfiltered (D = D_raw).

## LabVIEW FPGA Import

1. Copy `PID_ValveController.vhd` and `PID_ValveController.xml` into your CLIP IP folder.
2. Right-click FPGA target → **New → CLIP IP Node** → browse to the XML file.
3. LabVIEW reads all `LvName` strings and FXP types from the XML automatically.
4. Wire controls using `LvName` labels — they match your front panel exactly.

## Division Note

Stage 3 uses integer `/` to compute I/D coefficients.
GHDL simulates this correctly. For production LabVIEW FPGA synthesis:
- **Option A** (recommended): pre-compute `Ki_coeff = Kc*dt/(Ti*60)` and
  `Kd_coeff = Kc*Td*60/dt` on the RT side and pass as extra FXP ports.
- **Option B**: accept LabVIEW FPGA's auto-pipelining of the divider — the
  compiler adds pipeline stages automatically to meet timing.

## Running the Testbench

```bash
pip install cocotb pytest
sudo apt install ghdl
make sim          # 9 tests, ~30 s GHDL sim time
make vectors      # writes pid_test_vectors.csv (401 rows)
```

Expected output:
```
T1 PASS: aReset drives Output=0
T2 PASS: manual mode passthrough
T3 PASS: saturation output=100.0000
T4 PASS: P-only output=20.xxxx
T5 PASS: reinitialize output=0.0000
T6 PASS: setpoint clamping output=0.0000
T7 PASS: closed-loop valve PV=74.xxx SP=75.0 maxDiff<2.0
T8 PASS: bumpless manual->auto transfer
T9 PASS: DtOut sanitization
```
