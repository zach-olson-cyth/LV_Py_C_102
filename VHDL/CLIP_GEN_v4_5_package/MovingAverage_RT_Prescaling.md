# MovingAverage CLIP Node — RT Pre-Scaling Notes

## Why Pre-Scaling Is Required

The moving average formula is:

    output = (1/N) * sum(samples)

The division `1/N` must **not** execute as a runtime divide on the FPGA.
A combinational divide infers a large divider circuit, fails Vivado timing
closure at 40 MHz, and/or causes **Synth 8-5809** encrypted-envelope RTL
elaboration errors on the xc7k70tfbg676-1.

Instead, the RT host computes `1/N` in floating-point and writes the result
as a fixed-point value to the `Avg Gain (1/N)` terminal once at startup.
The FPGA only multiplies — which maps to a single DSP48 slice.

---

## Coefficient: AvgGain

| Property | Value |
|---|---|
| Description | Reciprocal of window size: 1/N |
| Port name | `AvgGain` |
| FXP format | FXP<+/-,32,8> — signed, WordLength=32, IntegerWordLength=8 |
| FWL (fractional bits) | 24 |
| LSB | 2^-24 ≈ 5.96e-8 |
| Value for N=16 | 0.0625 |
| Bit pattern for N=16 | `int(0.0625 × 2^24)` = **1,048,576** = `0x00100000` |
| Valid range | N = 1..128 (AvgGain stays within IWL=8 range: 1.0..0.0078) |
| When to update | At startup; again if N is changed at runtime |

---

## LabVIEW RT Pseudocode

```
-- Compute AvgGain at RT startup (or on N change)
N_dbl     = DBL(N)                         -- cast window size to double
AvgGain_f = 1.0 / N_dbl                    -- floating-point reciprocal
AvgGain_fxp = To Fixed-Point(
                  AvgGain_f,
                  Signed    = TRUE,
                  WordLength        = 32,
                  IntegerWordLength = 8     -- IWL=8, FWL=24
              )
Write AvgGain_fxp --> CLIP terminal "Avg Gain (1/N)"
```

Run this code in the RT initialization sequence, **before** the FPGA SCTL
begins processing live data. If the SCTL is already running, write the
coefficient and then assert `aReset` for 1–2 cycles to flush the shift
register with a consistent gain.

---

## Exact Bit Patterns for Common N Values

| N | AvgGain (float) | Bit pattern (hex) | Bit pattern (decimal) |
|---|---|---|---|
| 1 | 1.0 | 0x01000000 | 16,777,216 |
| 2 | 0.5 | 0x00800000 | 8,388,608 |
| 4 | 0.25 | 0x00400000 | 4,194,304 |
| 8 | 0.125 | 0x00200000 | 2,097,152 |
| **16** | **0.0625** | **0x00100000** | **1,048,576** |
| 32 | 0.03125 | 0x00080000 | 524,288 |
| 64 | 0.015625 | 0x00040000 | 262,144 |
| 128 | 0.0078125 | 0x00020000 | 131,072 |

All values fit within the IWL=8 range (–128.0 to +127.9999999).

---

## Optional C Shared Library (for RT loops > 1 kHz)

If the RT update rate is above 1 kHz and you prefer a C implementation:

```c
// mavg_prescale.c
// Compile: gcc -O2 -shared -fPIC -o mavg_prescale.so mavg_prescale.c
#include <stdint.h>

// Returns AvgGain as FXP<+/-,32,8> bit pattern (IWL=8, FWL=24)
// N must be 1..128
int32_t compute_avg_gain(int32_t N) {
    if (N < 1)   N = 1;
    if (N > 128) N = 128;
    double gain = 1.0 / (double)N;
    int32_t bits = (int32_t)(gain * 16777216.0);  // 2^24
    return bits;
}
```

Call via LabVIEW RT **Call Library Function Node**:
- Library: `mavg_prescale.so`
- Function: `compute_avg_gain`
- Parameters: I32 N → return I32 bit pattern
- Cast the returned I32 to FXP<+/-,32,8> before writing to the CLIP terminal.
