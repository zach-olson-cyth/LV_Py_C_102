# LabVIEW C / .so — AI Prompt Specification
## Call Library Function Node · NI Linux RT · cRIO Integration · v1.0

> **Purpose:** Paste any prompt in this document into **ChatGPT, Claude, Perplexity, Grok, Gemini,
> or any other mainstream LLM** to generate, debug, build, or extend any C shared library (.so)
> designed for the LabVIEW **Call Library Function Node (CLFN)** on NI Linux RT (CompactRIO).
> Replace all `[PLACEHOLDERS]` with your specifics before sending.
>
> **Works in:** Any AI chat interface — no special formatting required.
>
> **v1.0 contents:**
> - Complete CLFN parameter-mapping rules (C types → LabVIEW types)
> - Function generation, audio synth, AI learning, and PID controller prompts
> - Cross-compilation guide (WSL + x86_64-linux-gnu-gcc)
> - Makefile and PowerShell build scripts
> - Smoke test pattern (`#ifdef SMOKE_TEST`) — **must pass before deploying to cRIO**
> - Parameter order lock policy
> - Git/SVN workflow (optional)
> - Full CLFN error and wiring reference

---

## How to Use This Document

1. Find the prompt section that matches your task
2. Copy the entire code block
3. Replace all `[PLACEHOLDERS]` with your actual values
4. Paste into any mainstream LLM
5. Compile and run `make test` **before** deploying to cRIO or wiring into LabVIEW

---

## ⚠️ Critical Rules Before You Start

| Rule | Description |
|------|-------------|
| **Test first** | Every .c file MUST pass `make test` on the host before copying the .so to cRIO |
| **No parameter reordering** | Once a CLFN is wired into a released VI, **never change parameter order** |
| **void return** | CLFN functions almost always return void; outputs go via caller-allocated pointers |
| **Caller allocates arrays** | LabVIEW pre-allocates with `Initialize Array`; C writes into that buffer — never malloc in loops |
| **EXPORT macro required** | `__attribute__((visibility("default")))` on Linux RT; `__declspec(dllexport)` on Windows |
| **C calling convention** | Set Calling Convention = C in the CLFN dialog; never C++ |
| **No C++ headers** | Compile as C99; never `#include <iostream>` |
| **No static mutable state** | No `static` vars that survive VI restarts; use in/out pointer params for state |

---

## Quick Copy Prompts

### 1. Generate a New CLFN-Compatible C Function

```
Write a C function for the LabVIEW Call Library Function Node (CLFN) with these requirements:

FUNCTION NAME: [your_function_name]
PURPOSE: [what it computes]
INPUTS (by value):
  [name]  [C type]  [units / range]
OUTPUT ARRAYS (by pointer — caller allocates):
  [name]  [C type]*  [description]
RETURN TYPE: void

Rules:
1. Only stdint.h, math.h, string.h — no stdlib malloc in per-sample loops
2. Guard all pointer args: if (ptr == NULL || n <= 0) return;
3. EXPORT macro:
   #ifdef _WIN32
     #define EXPORT __declspec(dllexport)
   #else
     #define EXPORT __attribute__((visibility("default")))
   #endif
4. Compile as C99 (-std=c99), position-independent (-fPIC)
5. No C++ features
6. Smoke test under #ifdef [FUNCNAME]_SMOKE_TEST:
   - malloc output buffers, call function, check values, print PASS/FAIL, free buffers
   - return 0 on pass, 1 on fail
7. Build and run smoke test BEFORE deploying to cRIO:
   gcc -O2 -std=c99 -D[FUNCNAME]_SMOKE_TEST -o test_[funcname] [file].c -lm && ./test_[funcname]

LabVIEW CLFN context:
- Target: NI Linux RT x86-64 (cRIO-904x)
- Cross-compiler: x86_64-linux-gnu-gcc (WSL or Linux host)
- Scalar inputs: Pass by Value
- Array outputs: Array Data Pointer (LabVIEW pre-allocates with Initialize Array)
- Calling convention: C
```

---

### 2. Generate a Waveform Generator .so

> **Based on:** `waveform_gen.c` in LV_Py_101 — the minimal proven CLFN waveform pattern.

```
Write a C shared library for the LabVIEW CLFN that generates a [waveform type].

FUNCTION NAME: generatewaveform
TARGET: NI Linux RT x86-64

CLFN TERMINAL MAPPING (in order — DO NOT CHANGE once wired):
  1: amp          double    Value
  2: freq_start   double    Value    (Hz)
  3: freq_stop    double    Value    (Hz; == freq_start for fixed frequency)
  4: dt           double    Value    (sample interval, e.g., 1/44100)
  5: length_pts   int32_t   Value    (number of samples)
  6: out_array    double*   Pointer to Value  (pre-allocated by LabVIEW)

Algorithm: phase accumulation (not substitution):
  phase += 2 * M_PI * f_inst * dt;
  out_array[i] = amp * sin(phase);

Rules:
1. void return
2. Guard: if (length_pts <= 0 || out_array == NULL) return;
3. EXPORT macro
4. -std=c99, -fPIC, -shared
5. #ifdef WAVEFORM_SMOKE_TEST: fixed freq test, ascending sweep, descending sweep
   Each checks peak > 0.5 * amp

LabVIEW wiring:
- Parameters 1–5: Numeric Value (DBL or I32)
- Parameter 6: Array Data Pointer (DBL*)
- Pre-allocate output: Initialize Array [length_pts] DBL → wire to Parameter 6
```

---

### 3. Generate a Piano Synthesizer .so

> **Based on:** `piano_synth.c` in LV_Py_101.

```
Write a C shared library for the LabVIEW CLFN: piano note synthesizer.

FUNCTION: render_note
CLFN TERMINALS (frozen once released):
  1: freq         double    Value    (Hz)
  2: velocity     double    Value    (0.0–1.0)
  3: duration_s   double    Value
  4: dt           double    Value    (1/sample_rate)
  5: out          double*   Pointer to Value  (pre-allocated)
  6: n_samples    int32_t   Value

Model: 16 additive harmonics + ADSR envelope (attack=0.5%, decay=8%, sustain=70%,
release=15%) + inharmonicity B=0.00015 + velocity-dependent harmonic rolloff.

SECOND FUNCTION: mix_notes(double* tracks, int32_t n_tracks, int32_t n_samples, double* out)
  Sum all tracks, peak-normalize output to 0.92.

Rules: void returns, NULL guards, no malloc in loops, EXPORT macro,
#ifdef PIANO_SMOKE_TEST: render C4 (261.63 Hz), check peak > 0.01.
```

---

### 4. Generate a Drum Synthesizer .so

> **Based on:** `drum_synth.c` in LV_Py_101.

```
Write a C shared library for the LabVIEW CLFN: drum synthesizer.

FUNCTION: render_drum_hit
CLFN TERMINALS (frozen once released):
  1: drum_id      int32_t   Value    (0=kick,1=snare,2=hihat,3=tom-hi,4=tom-mid,5=tom-lo,6=crash,7=ride)
  2: velocity     double    Value    (0.0–1.0)
  3: n_samples    int32_t   Value
  4: sample_rate  int32_t   Value
  5: out          double*   Pointer to Value  (pre-allocated)

Drum models:
  Kick:  sine sweep 80→40 Hz over 80ms + noise transient + exponential decay
  Snare: 190 Hz tone + filtered noise + HP(600Hz)/LP(9000Hz)
  Hi-hat: noise + HP(5000Hz)/LP(12000Hz) + short decay
  Tom:   sine pitch sweep + exponential decay (varies per tom)
  Crash/Ride: 6 inharmonic partials (ratios 1.0,1.48,1.72,2.0,2.55,3.15) + noise

Helpers required:
  - LCG pseudo-random (avoid stdlib rand on RT):
    static uint32_t lcg_state = 0x12345678u;
    static double lcg_rand(void) { ... }
  - One-pole LP and HP filters (in-place)
  - Exponential decay: exp(-t / decay_s)
  - Normalize output to peak 0.95

SECOND FUNCTION: freq_to_drum_id(double freq) -> int32_t
  Nearest match from: {65.41, 82.41, 98.00, 123.47, 146.83, 174.61, 220.00, 261.63}

Rules: void return for render_drum_hit, int32_t for freq_to_drum_id,
NULL guards, no malloc in loops, EXPORT on both,
#ifdef DRUM_SMOKE_TEST: all 8 drums, freq_to_drum_id(82.41)=1, NULL guard.
```

---

### 5. Generate a UCB1 Adaptive Melody Learner .so

> **Based on:** `melody_learn_v3.c` in LV_Py_101 — the proven AI state-via-coefficients pattern.

```
Write a C shared library for the LabVIEW CLFN: UCB1 adaptive melody and rhythm generator.

FUNCTION: generate_melody_learn
CLFN TERMINALS (frozen once released):
  1:  n_notes           int32_t   Value
  2:  sample_rate       int32_t   Value
  3:  style             int32_t   Value    (0=lyrical,1=upbeat,2=mixed,3=jazz,4=rock,5=beat)
  4:  like_dislike      int32_t   Value    (1=like, 0=dislike, -1=no feedback)
  5:  last_arm_contour  int32_t   Value    (-1 on first call)
  6:  last_arm_rhythm   int32_t   Value    (-1 on first call)
  7:  coeffs_in         double*   Pointer to Value  (256 doubles, zeros on first call)
  8:  freqs_out         double*   Pointer to Value  (pre-allocated n_notes doubles)
  9:  durs_out          int32_t*  Pointer to Value  (pre-allocated n_notes int32_t)
  10: coeffs_out        double*   Pointer to Value  (256 doubles output)
  11: arm_contour_out   int32_t*  Pointer to Value
  12: arm_rhythm_out    int32_t*  Pointer to Value

Config: N_ARMS=8, N_STYLES=6, COEFF_LEN=256, UCB_C=1.5

Coefficient layout (256 doubles):
  [0–47]:   CONT_REW[style][arm]
  [48–95]:  CONT_VIS[style][arm]
  [96–143]: RHYT_REW[style][arm]
  [144–191]: RHYT_VIS[style][arm]
  [192–255]: reserved

Scales:
  C major (0–2): CMAJ[8] = {60,62,64,65,67,69,71,72}
  C Dorian (3):  CDOR[8] = {60,62,63,65,67,69,70,72}
  A pentatonic (4): APEN[8] = {57,60,62,64,67,69,72,76}
  Drum MIDI (5): DRUM[8] = {36,40,43,47,50,53,57,60}

UCB1: score(a) = mean_reward(a) + UCB_C * sqrt(log(total) / visits(a))
Pending credit: +0.5 visits on selected arm before reward is known.
memcpy(coeffs_out, coeffs_in, COEFF_LEN*sizeof(double)) at start.

Rules: void return, NULL guards, stdint.h/math.h/string.h only,
EXPORT macro, #ifdef LEARN_SMOKE_TEST: all 6 styles × 3 rounds with like=1,
verify freqs > 30.0 and durs > 100.
```

---

### 6. Generate a PID Controller .so for cRIO

```
Write a C shared library for the LabVIEW CLFN: discrete-time PID controller.

FUNCTION: pid_step
CLFN TERMINALS (frozen once released):
  1:  setpoint     double    Value
  2:  pv           double    Value    (measured process variable)
  3:  kp           double    Value
  4:  ki           double    Value
  5:  kd           double    Value
  6:  dt           double    Value    (sample interval, seconds)
  7:  out_min      double    Value
  8:  out_max      double    Value
  9:  integrator   double*   Pointer to Value  (state in/out, 1 element)
  10: prev_error   double*   Pointer to Value  (state in/out, 1 element)
  11: u_out        double*   Pointer to Value  (control output)

Algorithm:
  error = setpoint - pv
  P = kp * error
  integrator += ki * error * dt   // anti-windup: clamp to [out_min, out_max]
  D = kd * (error - prev_error) / dt
  u = clamp(P + integrator + D, out_min, out_max)
  prev_error = error

Rules: void return, NULL guards, anti-windup clamp on integrator, EXPORT macro,
#ifdef PID_SMOKE_TEST: step test 100 iterations, verify output stays in [out_min, out_max]
and error decreases over time.

LabVIEW integration:
- integrator and prev_error: DBL shift registers (single-element, Pointer to Value)
- Wire Kp/Ki/Kd from front panel controls for runtime gain changes
- Python TCP auto-tuner sends new gains; apply on next CLFN call
```

---

### 7. Debug a CLFN Error

```
My LabVIEW Call Library Function Node is throwing:
  [paste error, e.g., "Error 1097: Shared library failed to load"]

MY C FILE:
[PASTE ENTIRE C FILE HERE]

CLFN CONFIGURATION:
- Library path: [e.g., /home/lvuser/waveform_gen.so]
- Function name: [e.g., generatewaveform]
- Calling convention: [C / stdcall]
- Parameters (in order): [list each with type and pass-by]

PLATFORM:
- Target: [NI Linux RT x86-64 / Windows 64-bit]
- Cross-compiler: [e.g., x86_64-linux-gnu-gcc in WSL]
- Build command: [paste gcc command or make output]

Diagnose and fix:
1. EXPORT macro must be present
2. Calling convention: C (no C++ mangling)
3. Array outputs: Array Data Pointer, LabVIEW pre-allocates
4. NULL guards on all pointer params
5. -std=c99 -fPIC -shared
6. Confirm smoke test passes standalone before rewiring
7. Never change parameter order without a new function name
```

---

### 8. Write a Makefile and Build Script

> **Based on:** `Makefile` and `scripts/build_rt_sos.ps1` in LV_Py_101.

```
Write a Makefile and PowerShell build script for cross-compiling C to .so for NI Linux RT.

SOURCES: [e.g., waveform_gen.c, piano_synth.c, drum_synth.c, melody_learn_v3.c, pid_step.c]
CROSS-COMPILER: x86_64-linux-gnu-gcc (WSL)
CFLAGS: -O2 -fPIC -Wall -Wextra -std=c99 -D_GNU_SOURCE
LDFLAGS: -shared -lm

Makefile:
1. 'all' target builds all .so files
2. 'test' target builds each with SMOKE_TEST define and runs the test binary
3. 'clean' removes .so and test binaries
4. Pattern rules for multiple .so files

PowerShell (build_rt_sos.ps1):
1. Params: $RepoRoot, $Compiler (default "wsl x86_64-linux-gnu-gcc"), -GitCommit switch
2. Build each .so from c/ into rt-so/
3. Create rt-so/ if missing
4. Error on non-zero exit code
5. Optional git add rt-so/*.so + commit + push if -GitCommit set

Deployment:
- Copy .so to cRIO: sftp admin@[crio-ip] then put file.so /home/lvuser/
- Restart LabVIEW RT engine after replacing a loaded .so
```

---

### 9. Port a Python LabVIEW Node Function to C CLFN

```
Convert this Python LabVIEW Node function to C CLFN (.so):

[PASTE PYTHON FUNCTION HERE]

Type mapping:
  float (Python) → double (C)
  int (Python)   → int32_t (C)
  str (Python)   → int32_t enum index (add lookup table)
  list[float]    → double* with int32_t length param (Array Data Pointer)
  tuple (Python) → separate out pointer params

Rules:
1. Identical numerical behaviour within float64 precision
2. void return; all outputs via pointer params
3. NULL guards
4. EXPORT macro
5. No malloc in per-sample loops
6. Smoke test with ≥3 cases vs known Python output
7. PARAMETER ORDER NOTE: The Python parameter order defines CLFN terminal order.
   Once released, it is FROZEN. If Python order changed after release,
   do NOT propagate that change — create a new function name instead.
```

---

### 10. Generate CLFN Documentation

```
I have a C shared library for the LabVIEW CLFN:

FUNCTION: [name]
LIBRARY: [e.g., /home/lvuser/waveform_gen.so]
PARAMETERS (in CLFN order):
  1. [name, C type, pass-by, description]
  ...
PURPOSE: [description]

Write:
1. CLFN README (Markdown): parameter table, CLFN dialog steps, Initialize Array wiring,
   deployment procedure
2. VI Description (100 words max) for LV → File → VI Properties → Documentation
3. One-paragraph cRIO developer guide note
4. Change log entry for v1.0
```

---

## LabVIEW CLFN ↔ C Complete Type Mapping

### Scalar Inputs (Pass by Value)

| LabVIEW Type | C Type | CLFN Pass-By |
|---|---|---|
| DBL | `double` | Value |
| SGL | `float` | Value |
| I32 | `int32_t` | Value |
| U32 | `uint32_t` | Value |
| Boolean | `int32_t` (0 or 1) | Value |
| String | Not directly — use `int32_t` enum | Value |

### Array Outputs (Array Data Pointer)

| LabVIEW Type | C Parameter | Pre-allocation in LabVIEW |
|---|---|---|
| 1D Array DBL | `double *out` | `Initialize Array [n] DBL` → wire to terminal |
| 1D Array I32 | `int32_t *out` | `Initialize Array [n] I32` → wire to terminal |

### Scalar Outputs (Pointer to Value)

| Usage | C Parameter | CLFN Pass-By |
|---|---|---|
| Single output DBL | `double *u_out` | Pointer to Value |
| Single output I32 | `int32_t *arm_out` | Pointer to Value |
| State round-trip | `double *integrator` | Pointer to Value |

---

## CLFN Configuration Reference

1. Drop `Call Library Function Node` (Functions → Connectivity → Libraries & Executables)
2. Double-click → Library name: `/home/lvuser/waveform_gen.so`
3. Function name: `generatewaveform` (exact, case-sensitive)
4. Calling convention: **C**
5. Parameters tab — add in exact C signature order:
   - Scalar input: Type=Numeric, Data Type=DBL/I32, Pass=Value
   - Array output: Type=Array, Data Type=DBL/I32, Pass=Array Data Pointer
   - Scalar output: Type=Numeric, Data Type=DBL/I32, Pass=Pointer to Value
6. Return type: Void

**Wiring output arrays:**
```
1. Initialize Array → wire length control to dimension size, DBL to element
2. Wire Initialize Array output to CLFN array terminal
3. Wire CLFN array output to indicator
```

---

## Constraint Reference Card

| Constraint | Correct ✓ | Incorrect ✗ |
|---|---|---|
| EXPORT macro | `EXPORT void func(...)` | Missing EXPORT (symbol not visible) |
| Calling convention | `C` in CLFN dialog | `stdcall` (crashes on Linux) |
| Return type | `void` | `double[]` |
| Array output | Caller allocates; C writes | `malloc` inside exported func |
| Scalar output | `double *u_out; *u_out = val;` | `return val;` |
| C standard | `-std=c99` | C++ features |
| Position-independent | `-fPIC` | No `-fPIC` (segfault) |
| NULL guard | `if (!ptr \|\| n<=0) return;` | Assume valid |
| Smoke test | `#ifdef FUNCNAME_SMOKE_TEST` | No test at all |
| Parameter order | **Frozen once released** | Reorder after wiring |
| Random number (RT) | Custom LCG | `rand()` |
| Memory in audio | No malloc per sample | `malloc(n*sizeof(double))` per call |
| State persistence | In/out double* array | `static double state;` |
| Pre-integration | `make test` PASS | Deploy without smoke test |

---

## Pre-Integration Testing Protocol

```bash
# Step 1: Build and run smoke test on HOST (not cRIO)
make test
# Expected: all PASS, then OVERALL: PASS

# Step 2: Build .so for NI Linux RT
make all

# Step 3: Verify exported symbols
nm -D waveform_gen.so | grep " T "
# Your function must appear as a T (text/exported) symbol

# Step 4: Deploy to cRIO
sftp admin@192.168.1.10
> put waveform_gen.so /home/lvuser/
> quit

# Step 5: Only if all above pass — wire in LabVIEW CLFN
```

---

## Parameter Order Lock Policy

Once a CLFN is wired into a released VI, parameter order is **frozen**.

- Never remove, insert, or reorder without creating a new function name (`_v2`)
- New params may be appended at END only
- Document changes in CHANGELOG at top of .c file

**Signal to AI:** *"This function is released. Do NOT change parameter order.
Append new params at END only. If restructuring, create `_v2`."*

---

## Git / SVN Workflow (Optional)

```bash
git checkout -b feature/add-pid-step-so
make test          # must print OVERALL: PASS
make all
git add c/pid_step.c rt-so/pid_step.so
git commit -m "feat: add pid_step CLFN for DO control loop"
git tag v2.0.0-pid-step
git push origin feature/add-pid-step-so
```

**PowerShell build + commit:**
```powershell
.\scripts\build_rt_sos.ps1 -GitCommit -CommitMessage "chore: rebuild RT .so after drum_synth update"
```

> Never commit a .c file until `make test` passes.

---

## Waveform / Audio Debugging Checklist

| Symptom | Likely Cause | Fix |
|---|---|---|
| All zeros output | NULL not caught; wrong pre-allocation | Add NULL guard; verify Initialize Array size |
| Error 1097 | Wrong path or wrong architecture | Verify path on cRIO; `file lib.so` must show x86-64 ELF |
| Segfault / Error 7 | NULL dereference | Add `if (!out \|\| n<=0) return;` |
| No audio | Peak near zero | Check amp input wired; verify EXPORT with `nm -D` |
| Wrong pitch | Phase substitution | Use `phase += 2*M_PI*f*dt` per sample |
| Distorted audio | No normalization | Call `normalize(out, n)` after synthesis |
| Drum always kick | freq_to_drum_id not applied | Apply before passing drum_id to render_drum_hit |
| Melody stuck on arm 0 | Coefficients not round-tripping | Verify coeffs_out → shift register → coeffs_in |
| PID saturated | No anti-windup | Clamp integrator to [out_min, out_max] |
| Crash after redeploy | Old .so still loaded | Restart LabVIEW RT engine |
| Symbol not found | Missing EXPORT or name mangling | `nm -D lib.so | grep " T "` |

---

## Smoke Test Pattern Reference

```c
#ifdef WAVEFORM_SMOKE_TEST
#include <stdio.h>
#include <stdlib.h>

int main(void) {
    int n = 4410;
    double *buf = (double *)malloc(n * sizeof(double));
    int all_ok = 1;

    generatewaveform(1.5, 440.0, 440.0, 1.0/44100.0, n, buf);
    double peak = 0.0;
    for (int i = 0; i < n; i++) if (fabs(buf[i]) > peak) peak = fabs(buf[i]);
    int ok = peak > 0.5;
    printf("fixed 440Hz: peak=%.4f  %s\n", peak, ok ? "PASS" : "FAIL");
    all_ok &= ok;

    free(buf);
    printf("OVERALL: %s\n", all_ok ? "PASS" : "FAIL");
    return all_ok ? 0 : 1;
}
#endif
```

**Build smoke test (host):**
```bash
gcc -O2 -std=c99 -DWAVEFORM_SMOKE_TEST -o waveform_gen_test waveform_gen.c -lm
./waveform_gen_test
```

**Build .so for NI Linux RT:**
```bash
x86_64-linux-gnu-gcc -O2 -shared -fPIC -std=c99 -o waveform_gen.so waveform_gen.c -lm
```

---

## Quick Error Lookup

| Error / Symptom | Meaning | Fix |
|---|---|---|
| Error 1097 | Library failed to load | Check path; verify x86-64 ELF; check permissions |
| Error 1098 | Function not found | Verify exact name; `nm -D lib.so` |
| Segfault / Error 7 | NULL or out-of-bounds | Add NULL and size guards |
| All outputs zero | EXPORT missing; wrong convention | Add EXPORT; set CLFN to C calling convention |
| Wrong audio | Amplitude zero; wrong terminal order | Verify terminal 1 = amp; check CLFN param order |
| Works on Windows, fails on cRIO | Wrong architecture | Cross-compile with x86_64-linux-gnu-gcc |
| Crash after restart | Static state from prior run | Use in/out pointer params instead of static vars |
| PID not responding | Gains wired as constants | Wire Kp/Ki/Kd from front panel controls |
| UCB1 resets on restart | Coefficients not saved | Save coeffs_out to CSV at VI shutdown |

---

## CLFN vs Python Node — When to Choose Which

| Factor | Python Node | C CLFN (.so) |
|---|---|---|
| Development speed | Fast | Slower (C + cross-compile + deploy) |
| Runtime performance | Moderate | Near-native C |
| Hard real-time loop | Not suitable | Suitable (no GIL) |
| numpy / scipy | Available | Not available — use math.h |
| State management | `list[float]` shift register | `double*` in/out pointer |
| Audio synthesis | Works but slower | Preferred at 44100 Hz |
| AI learning | Easy to prototype | Better for RT-deployed loops |
| Debugging | `python file.py` | `make test` |
| Parameter order | Frozen once released | Frozen once released |
| Best for | Prototyping, AI models, data | Audio, control loops, real-time |

---

## References

- NI CLFN docs: https://www.ni.com/docs/en-US/bundle/labview/page/lvhowto/using_clfn.html
- NI Linux RT cross-compilation: https://www.ni.com/docs/en-US/bundle/ni-linux-real-time-developers-guide/
- LV_Py_101 Repository: https://github.com/zach-olson-cyth/LV_Py_101
  - `waveform_gen.c`: minimal CLFN waveform pattern
  - `c/piano_synth.c`: ADSR + additive synthesis
  - `c/drum_synth.c`: drum synthesis + LCG + bridge function
  - `c/melody_learn_v3.c`: UCB1 AI learning with coeffs state
  - `Makefile`: cross-compile and smoke test
  - `scripts/build_rt_sos.ps1`: PowerShell build + optional Git commit
- NI Community: https://forums.ni.com/t5/LabVIEW/bd-p/170
- LAVA Forums: https://lavag.org/
