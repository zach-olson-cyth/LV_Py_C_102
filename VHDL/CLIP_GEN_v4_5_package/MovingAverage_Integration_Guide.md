# MovingAverage CLIP Node — Integration Guide

## Algorithm Description

This CLIP node implements a 16-sample sliding-window moving average filter.
Each enabled clock cycle the oldest sample is dropped, the newest is added,
and the running accumulator is multiplied by the pre-scaled gain `AvgGain = 1/16`
to produce the averaged output with no runtime division on the FPGA.

## Generated Files

| File | Purpose |
|---|---|
| `MovingAverage.vhd` | Synthesizable VHDL-2008 entity and RTL architecture |
| `MovingAverage.xml` | LabVIEW FPGA CLIP Declaration, FormatVersion 4.2 |
| `MovingAverage_Integration_Guide.md` | This file |
| `MovingAverage_Test_Plan.md` | Verification and compile-readiness tests |
| `MovingAverage_RT_Prescaling.md` | RT-side coefficient computation |

## Build Mode and Applied Defaults

| Default | Value |
|---|---|
| Build mode | Quick Build (files 1–5) |
| Target FPGA | xc7k70tfbg676-1 (NI cRIO-class Kintex-7) |
| Master clock | 40 MHz |
| VHDL standard | VHDL-2008 |
| Window size N | 16 samples |
| Input/Output FXP | FXP<+/-,32,16> signed, IWL=16, FWL=16, LSB≈1.526e-5 |
| AvgGain FXP | FXP<+/-,32,8> signed, IWL=8, FWL=24, LSB≈5.96e-8 |
| Reset | `aReset`, active-high, synchronous |
| Enable | `Ce`, active-high |
| Closed-loop test | None |

## Terminal Mapping Table

| Front Panel Label | VHDL Port | Direction | FXP Format | Range | Notes |
|---|---|---|---|---|---|
| Clk | Clk | ToCLIP | std_logic (clock) | 40 MHz | Wire to SCTL clock reference |
| aReset | aReset | ToCLIP | Boolean | 0/1 | High clears all state synchronously |
| Ce | Ce | ToCLIP | Boolean | 0/1 | Low freezes filter; high enables update |
| Data In (0-100%) | DataIn | ToCLIP | FXP<+/-,32,16> | 0.0–100.0 | Raw process signal in percent |
| Avg Gain (1/N) | AvgGain | ToCLIP | FXP<+/-,32,8> | ~0.0625 for N=16 | Computed on RT; write once at startup |
| Data Out (0-100%) | DataOut | FromCLIP | FXP<+/-,32,16> | 0.0–100.0 | Averaged output |
| Overflow | Overflow | FromCLIP | Boolean | 0/1 | High if accumulator exceeds guard bits |

## LabVIEW FPGA Import Procedure

1. In the LabVIEW FPGA project, right-click the FPGA target and select
   **Properties → Component-Level IP**.
2. Click **Add** and browse to `MovingAverage.xml`.
   Confirm the Declaration Name shows `MovingAverage` with no red X.
   (If a red X appears, verify `MovingAverage.vhd` is in the **same directory**
   as the `.xml` file.)
3. Click OK. The **IP Integration Node** (`MovingAverage`) will appear in the
   block diagram palette under Component-Level IP.
4. Place the node on the FPGA block diagram inside a
   **Single-Cycle Timed Loop (SCTL)**.
5. **Wire terminals:**
   - `Clk` → SCTL clock reference terminal
   - `Ce` → SCTL Loop Tick output (or wire a `TRUE` constant for always-on)
   - `aReset` → your system reset Boolean
   - `Data In (0-100%)` → FXP control or upstream data source
   - `Avg Gain (1/N)` → FPGA host DMA or front-panel FXP control
   - `Data Out (0-100%)` → FXP indicator or downstream node
   - `Overflow` → Boolean indicator
6. **IP Terminals page** (critical — skip this and constants become 32,32):
   For **every FXP terminal**, right-click the node → **IP Terminals**:
   - `Data In (0-100%)` and `Data Out (0-100%)`: Signed=true, WordLength=32, IntegerWordLength=16
   - `Avg Gain (1/N)`: Signed=true, WordLength=32, IntegerWordLength=8
7. Compile. Expected resource usage on xc7k70tfbg676-1: ~18 FFs, ~1 DSP48 slice.

## Pipeline Latency

| Stage | Latency (cycles) |
|---|---|
| Input latch + shift register update | 1 |
| Accumulator update | 1 |
| Gain multiply + shift | 1 |
| Output register | 1 |
| **Total end-to-end** | **4 clock cycles at 40 MHz = 100 ns** |

`DataOut` reflects the average of the 16 samples ending 4 cycles after `DataIn` is presented
with `Ce` high.

## Ce Rate vs. Master Clock

The CLIP operates at the full 40 MHz master clock. `Ce` should be driven
by your loop tick at whatever rate the algorithm needs to sample (e.g., 1 kHz,
10 kHz). When `Ce` is low the shift register and accumulator are frozen; the
node consumes clock power but produces no state change. `DataOut` holds its
last value.

## What NOT to Do

- **Do not write a runtime `1/N` divide inside the SCTL.** Always pre-compute
  `AvgGain` on the RT side and write it once at startup (or whenever N changes).
- **Do not drive `Ce` with a fast free-running signal if your process runs slower
  than the master clock.** Use the SCTL loop tick to pace the filter correctly.
- **Do not leave `AvgGain` undriven.** An undriven FXP terminal defaults to 0,
  producing a zero output regardless of input.
- **Do not set FXP terminal formats after placing constants.** Set IP Terminals
  first, then place controls and wire them.

## Pre-Compile Checklist

- [ ] `MovingAverage.vhd` and `MovingAverage.xml` are in the same directory
- [ ] CLIP Declaration Name shows `MovingAverage` with no red X
- [ ] IP Terminals set: DataIn/DataOut IWL=16, AvgGain IWL=8
- [ ] `Clk` wired to SCTL clock reference
- [ ] `Ce` wired to SCTL loop tick or TRUE constant
- [ ] `aReset` wired to system reset Boolean
- [ ] `Avg Gain (1/N)` written from RT on startup (value ≈ 0.0625 for N=16)
- [ ] `Overflow` indicator monitored during initial test
- [ ] No red broken wires on FPGA block diagram
- [ ] Run GHDL analysis before Vivado compile: `ghdl -a --std=08 MovingAverage.vhd`
