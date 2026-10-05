# MovingAverage CLIP Node — Test Plan

Target entity: `MovingAverage`
Window size: N = 16 samples
FXP input/output: FXP<+/-,32,16>  (Q16.16, IWL=16, FWL=16)
FXP gain: FXP<+/-,32,8>  (Q8.24, IWL=8, FWL=24)

---

## 1. Logic Tests

### 1.1 Reset clears all state
- Assert `aReset = '1'` for 5 cycles with arbitrary data on `DataIn`.
- Deassert reset. Hold `Ce = '0'` for 3 cycles.
- **Expected:** `DataOut = 0x00000000`, `Overflow = '0'`.

### 1.2 Ce freeze
- Fill the filter with known data (Ce = '1', constant input = 50.0 %).
- Assert `Ce = '0'` for 20 cycles while changing `DataIn` to 0.0 %.
- **Expected:** `DataOut` unchanged throughout the 20 frozen cycles.
- Release `Ce = '1'`. Verify the filter begins updating on the next cycle.

### 1.3 Overflow flag
- Set `AvgGain` to 1.0 (Q8.24 representation: 0x01000000) instead of 1/16.
- Drive `DataIn` = 100.0 % (Q16.16: 0x00640000) for 16 cycles.
- **Expected:** `Overflow = '1'` because the accumulator exceeds the guard bits
  for a gain of 1.0 applied to a sum of 16 × 100.0 %.

### 1.4 Boolean controls
- Confirm `aReset = '1'` overrides `Ce = '1'` (reset wins).
- Confirm `Ce = '0'` freezes even when `DataIn` is toggling.

---

## 2. Numeric Tests

### 2.1 DC steady-state
- Input: constant 50.0 % for 20+ cycles.
- AvgGain: Q8.24 = 1/16 = 0x00100000 (= 16777216 / 256 × (1/16) × 2^24 = 1048576).
  Exact bit pattern: `int(0.0625 * 2**24)` = `1048576` = `0x00100000`.
- **Expected after 16 cycles:** `DataOut` = 50.0 % ± 2 LSB (LSB = 1.526e-5 %).

### 2.2 Step response
- Pre-fill filter with 0.0 % for 16 cycles, then step to 100.0 %.
- **Expected convergence:** after k new samples at 100.0 %, output =
  (k / 16) × 100.0 %. Reaches full 100.0 % after exactly 16 enabled cycles.

### 2.3 Quantization error bound
- Compare Q16.16 CLIP output against floating-point reference:
  `avg = sum(samples[-16:]) / 16.0`
- **Pass criterion:** |CLIP output − reference| ≤ 2 LSB = 3.052e-5 %.

### 2.4 Saturation
- Drive `DataIn` = maximum positive (0x7FFFFFFF).
- **Expected:** `DataOut` saturates at 0x7FFFFFFF; no wraparound.
- Drive `DataIn` = maximum negative (0x80000000).
- **Expected:** `DataOut` saturates at 0x80000000; no wraparound.

---

## 3. Algorithm-Specific Tests

### 3.1 Moving average time constant
- Step input from 0.0 % to 100.0 %. Record output each cycle.
- Verify the ramp is linear: output[k] = k × (100.0 / 16) for k = 1..16.

### 3.2 Low-frequency sine pass, high-frequency rejection
- Drive `DataIn` with a sine wave at f_s / 32 (below filter corner).
- **Expected:** `DataOut` amplitude ≈ input amplitude.
- Drive `DataIn` with a sine wave at f_s / 2 (Nyquist).
- **Expected:** `DataOut` amplitude ≈ 0 (strong attenuation).

### 3.3 Reinitialize
- Run filter to steady state at 75.0 %.
- Assert `aReset = '1'` for 2 cycles.
- **Expected:** `DataOut` immediately returns to 0 on the next Ce cycle;
  no residual average from prior history.

---

## 4. Compile-Readiness Tests

```bash
# GHDL behavioral analysis (VHDL-2008)
ghdl -a --std=08 MovingAverage.vhd

# GHDL elaboration check
ghdl -e --std=08 MovingAverage

# XML well-formedness (requires xmllint)
xmllint --noout MovingAverage.xml

# Check for forbidden XML patterns
grep -n "xmlns"              MovingAverage.xml  # must return nothing
grep -n "FormatVersion"      MovingAverage.xml  # must return "4.2"
grep -n "InterfaceType"      MovingAverage.xml  # must be inside <Interface>
grep -n "SignalType.*reset"  MovingAverage.xml  # must return nothing
grep -n "Direction.*Input\b" MovingAverage.xml  # must return nothing
grep -n "Direction.*Output\b"MovingAverage.xml  # must return nothing
```

All four commands must complete with zero errors and zero warnings before
submitting to Vivado.
