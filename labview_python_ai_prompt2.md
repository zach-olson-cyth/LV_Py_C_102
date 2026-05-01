# LabVIEW Python Node — AI Prompt Specification
## Signal Generator · well_model.py · Beats & Tunes · PID Tuning · cRIO Integration · v3.0

> **Purpose:** Paste any prompt in this document into **ChatGPT, Claude, Perplexity, Grok, Gemini,
> or any other mainstream LLM** to generate, debug, or extend any Python function designed for the
> LabVIEW Python Node.
> Replace all `[PLACEHOLDERS]` with your specifics before sending.
>
> **Works in:** Any AI chat interface — no special formatting required. All prompts are plain text.
>
> **v2.0 updates:** Full data-type mapping (scalars, arrays, clusters, strings), 1D array return fix,
> image-based VI analysis prompt, waveform debugging checklist, numpy install guide.
>
> **v3.0 updates:**
> - Lessons learned from beats, tunes, drum synth, and melody AI integration
> - UCB1 multi-armed bandit learning loop prompt (stateless AI via coeffs_in/coeffs_out)
> - PID auto-tuner prompt for cRIO real-time loop (DO, temperature, flow)
> - Freq-to-drum bridge prompt (connecting melody learner to drum synthesizer)
> - Training data generation with AI learning state
> - Pre-integration testing protocol (must pass standalone before wiring to LabVIEW)
> - Parameter order lock policy — never reorder once released
> - Git/SVN workflow guidance (optional section)
> - New LLM-agnostic guidance: works with any mainstream chat AI
> - Extended waveform debugging checklist and error lookup table

---

## How to Use This Document

1. Find the prompt section that matches your task (generate, debug, extend, fix, etc.)
2. Copy the entire code block
3. Replace all `[PLACEHOLDERS]` with your actual values
4. Paste into ChatGPT, Claude, Perplexity, Grok, Gemini, or any other LLM
5. The AI will produce LabVIEW-compatible Python code that follows all rules below

> **LLM-Agnostic Note:** These prompts are plain-text specifications. They work equally well with
> any chat AI that can write Python. Do not assume any LLM-specific syntax, plugins, or features.
> The code produced must pass a standalone smoke test **before** it is wired into LabVIEW.

---

## ⚠️ Critical Rules Before You Start

| Rule | Description |
|------|-------------|
| **Test first** | Every function MUST pass its `__main__` smoke test standalone (CMD: `python your_file.py`) before wiring into LabVIEW |
| **No parameter reordering** | Once a function is wired into a released VI, **never change parameter order** without explicit approval and a version bump |
| **No default args** | LabVIEW passes all arguments positionally; defaults are silently ignored and cause hard-to-find bugs |
| **Plain Python types only** | `float`, `int`, `str`, `list`, `tuple` — never `np.float64`, `np.array`, `dict` |
| **State in, state out** | No module-level mutable state; all persistent state is passed in and returned out as a list or tuple |

---

## Quick Copy Prompts

### 1. Generate a New LabVIEW-Compatible Python Function

```
Write a Python function for the LabVIEW Python Node with these requirements:

FUNCTION NAME: [your_function_name]
PURPOSE: [what it computes, e.g., "simulate oil well pressure and flow rate"]
INPUTS: [list each parameter — name, LabVIEW type, Python type, units, typical range]
OUTPUTS: [list each return value — name, LabVIEW type, Python type, units]
PHYSICS/LOGIC: [equations or algorithm to implement]
STATE: [any values that carry between calls, e.g., "P_wh and Q persist as inputs"]

Rules the function MUST follow:
1. Scalars: use plain Python float, int, or str — no np.float32, no np.int64
2. 1D Arrays: return as plain Python list[float] or list[int] — NOT numpy arrays, NOT tuples wrapping lists
3. Multiple outputs: return as a tuple — (scalar1, scalar2, list1)
4. No default argument values — LabVIEW passes all arguments positionally
5. No module-level mutable state — all state passed in and returned out
6. import statements at top of file only (numpy is allowed)
7. Include a __main__ block with a 5-step smoke test that prints PASS/FAIL
8. The smoke test MUST pass when run with: python [filename].py before wiring to LabVIEW

LabVIEW Python Node context:
- LabVIEW 2020+ on Windows, 64-bit Python 3.9–3.14
- Scalar DBL/I32/String → Python float/int/str
- 1D Array of DBL → Python list[float]  (return type terminal = empty 1D DBL Array constant)
- Cluster → Python tuple (return type terminal = LabVIEW Cluster constant)
- All input terminals must be wired — no defaults are used
- numpy is allowed; pandas, scipy, tensorflow are NOT available in the LabVIEW Python environment
```

---

### 2. Analyze a Front Panel or Block Diagram Image

```
I am attaching a screenshot of a LabVIEW [front panel / block diagram].
Analyze the image and do the following:

1. LIST all input controls you can see (name, LabVIEW control type, likely data type)
2. LIST all output indicators you can see (name, LabVIEW indicator type, likely data type)
3. INFER the Python function signature that would match this VI, using these type mappings:
   - Numeric control (DBL/SGL/I32) → float or int
   - String control / ring / enum → str
   - Boolean / LED → int (1 or 0)
   - 1D Array indicator or waveform graph → list[float]
   - Cluster → tuple of matching Python types
   - dt control → float (sample interval in seconds)
   - N Samples / num_samples control → float (cast to int inside Python)
4. WRITE a complete Python function with the correct signature, docstring, and __main__ smoke test
5. NOTE any dt, N samples, or sample-rate controls that affect output array length
6. WARN if dt appears too large for the given frequency (Nyquist: dt < 1 / (2 * max_freq))

Apply all LabVIEW Python Node rules:
- No default args
- Plain Python types only (float, int, str, list, tuple)
- No numpy arrays as return values — use list[float]
- No dicts
- Return tuple for multiple outputs; return list[float] for a single array output
- Include a __main__ smoke test with at least 3 test cases
- Smoke test must PASS standalone before connecting to LabVIEW
```

---

### 3. Debug an Existing Function (Paste Your Code)

```
I have a Python function designed for the LabVIEW Python Node. It is called from LabVIEW
via Functions → Connectivity → Python → Python Node.

THE ERROR IS: [paste LabVIEW error number and description, e.g., "Error 1672: Python session failed"]

MY PYTHON FILE (signal_demo.py):
[PASTE YOUR ENTIRE PYTHON FILE HERE]

LABVIEW SETUP:
- Module path string: C:\LabVIEW\python\signal_demo.py
- Function name string: generate_signal
- Number of input terminals wired: [e.g., 6]
- Return type set to: [e.g., 1D DBL Array / Cluster of DBL, DBL, String / scalar DBL]
- Python version (from CMD): [e.g., Python 3.14.0]
- Bitness (from CMD): [64 or 32]

Please diagnose and fix. Apply these rules:
1. Scalars: plain float, int, str only
2. 1D arrays: plain Python list[float] — return type terminal must be empty 1D DBL Array constant
3. Tuple return for multiple mixed outputs
4. No default argument values
5. No module-level mutable state
6. numpy is allowed (import at top of file only)
7. Verify function name matches exactly — LabVIEW is case-sensitive
8. Add a __main__ smoke test and confirm it passes standalone before recommending LabVIEW wiring
```

---

### 4. Fix the Array Return SystemError

```
My LabVIEW Python Node is throwing:
  "Failed when trying to convert field of tuple at index: 0
   Inner error: SystemError tupleobject.c:107: bad argument to internal function"

This means the return type terminal in LabVIEW is wired as a scalar DBL instead of a 1D Array.

PYTHON SIDE — return a plain list of float, not a tuple wrapping a list:
  return y             # CORRECT:  plain list[float]
  # return (y,)       # WRONG:    tuple containing a list — causes this exact error
  # return np.array(y) # WRONG:   numpy array — not accepted by Python Node

LABVIEW SIDE — fix the return type terminal:
  1. Right-click the return value terminal on the Python Node → Create → Constant
  2. Right-click that constant → Data Operations → Make Array
     (OR: delete it and use Functions → Programming → Array → Array Constant,
      then drop a DBL Numeric Constant inside it)
  3. Confirm the element type is DBL
  4. Wire the empty 1D DBL Array constant to the return type terminal
  5. The wire color should be dark orange/brown (array), not thin orange (scalar)

Now rewrite my function [PASTE FUNCTION HERE] so it returns list[float] directly
and add a __main__ smoke test that confirms isinstance(result, list) and all values are float.
```

---

### 5. Fix a Waveform That Looks Wrong

```
My LabVIEW waveform graph shows [describe: flat line / triangle shape / amplitude ~1e-10 / wrong frequency].

My Python function inputs are:
  amplitude     = [value]
  freq_start    = [value] Hz
  freq_stop     = [value] Hz
  dt            = [value] seconds
  waveform_type = "[Sine/Square]"
  n_samples     = [value]

Diagnose which of these common problems applies and fix the function:

1. dt too large → violates Nyquist: dt must be < 1 / (2 * max_frequency)
   For 10 Hz sine: dt must be < 0.05 s
   Recommended: dt = 0.001 (1 kHz sample rate gives 100 samples per cycle at 10 Hz)

2. n_samples too small or zero → waveform has too few points to resolve the shape
   Recommended: n_samples = 1000 for a 1-second record at dt = 0.001

3. Amplitude ~1e-10 (near zero) → amplitude control is not wired to the correct
   input terminal on the Python Node — check the block diagram terminal order

4. Phase substitution instead of phase accumulation → do NOT use sin(2*pi*f*i*dt)
   CORRECT approach: accumulate phase sample-by-sample to support sweeps:
     phase += 2 * pi * f * dt
     y[i] = amplitude * sin(phase)

Provide the corrected function and the recommended front panel values for a clean 10 Hz sine wave.
```

---

### 6. Extend with a New Signal Type

```
I have signal_demo.py for the LabVIEW Python Node. It currently supports:
sine, square, triangle, saw, noise, chirp, step

Add a new signal type called "[your_type]" that: [describe the waveform or algorithm]

Keep all existing rules:
1. No default args — all parameters always positional
2. Return list[float] — plain Python list, not a numpy array
3. No new imports except numpy (already imported at top of file)
4. Add the new type to the __main__ smoke test
5. Preserve all existing signal types exactly — do not modify them
6. Do NOT change the parameter order of generate_waveform() — this function is released in LabVIEW
```

---

### 7. Generate Training Data from well_model.py for DeepLTK

```
I have a Python function step_oilfield() in well_model.py used as a LabVIEW Python Node.
Write a standalone script that:

1. Imports step_oilfield from well_model
2. Runs a grid of operating points:
   - mu_cp in [0.5, 1.0, 5.0, 10.0, 50.0] cP
   - valve_pos in [0.1, 0.3, 0.5, 0.7, 1.0]
   - P_wh_init in [200, 400, 600, 800] psi
3. For each combination, runs 100 timesteps with dt_s=0.5
4. Records each step as a row: [P_wh_in, Q_in, mu, valve_pos, P_wh_out, Q_out]
5. Saves all rows to well_training_data.csv
6. Prints: total rows written, min/max P_wh, min/max Q

Use only numpy and csv (no pandas). Add a __main__ guard.
```

---

### 8. Port a MATLAB/Simulink Function to LabVIEW Python Node

```
Convert this MATLAB function to Python for use as a LabVIEW Python Node:

[PASTE MATLAB CODE HERE]

Requirements for the Python version:
1. Maintain identical numerical behaviour to MATLAB within float64 precision
2. Scalars: plain float or str (no arrays, no dicts)
3. 1D array outputs: plain list[float] — not numpy arrays
4. Multiple outputs: tuple
5. No default argument values
6. numpy is allowed for math operations (use numpy.sin, numpy.pi, etc.)
7. Include __main__ smoke test comparing to at least 3 known MATLAB output values
8. Note any MATLAB built-in functions that need numpy equivalents
9. Confirm smoke test passes before recommending LabVIEW wiring
```

---

### 9. Write a LabVIEW VI Description for Documentation

```
I have a LabVIEW VI that calls this Python function via the Python Node:

FUNCTION NAME: [name]
PYTHON FILE: C:\LabVIEW\python\[file].py
INPUTS: [list with LabVIEW type, Python type, and ranges]
OUTPUTS: [list with LabVIEW type, Python type]
PURPOSE: [what the VI does overall]

Write:
1. A VI Description (100 words max) suitable for LabVIEW → File → VI Properties → Documentation
2. A connector pane description for each terminal (name, direction, type, description)
3. Front panel control/indicator list with recommended LabVIEW control types
4. A one-paragraph note for the cRIO developer guide
```

---

### 10. Generate a UCB1 Bandit Learning Loop (AI State Machine)

> **Lesson learned:** The melody_learn_v3 pattern proved that AI state machines work well in Python
> when all state is passed in and returned out as a flat list. This makes the function stateless
> from LabVIEW's perspective while preserving learning across calls. The same pattern applies to
> any AI learning loop you want to run inside a LabVIEW Python Node.

```
Write a Python function for the LabVIEW Python Node that implements a UCB1 multi-armed bandit
learning loop.

FUNCTION NAME: [your_learner_name, e.g., select_arm]
PURPOSE: [what is being optimized, e.g., "learn the best PID gain preset for a DO control loop"]
N_ARMS: [number of options/strategies, e.g., 8]
CONTEXT: [brief description of what each arm represents, e.g., "8 Kp/Ki gain presets"]
REWARD: [what constitutes a good outcome, e.g., "1.0 = user liked result, 0.0 = disliked"]

INPUTS:
  like_dislike     int   (1 = positive reward, 0 = negative, -1 = no feedback yet)
  last_arm         int   (arm index selected last call; -1 on first call)
  coeffs_in        list[float]  (length = 2 * N_ARMS: first N_ARMS = rewards, next N_ARMS = visits)

OUTPUTS:
  arm_out          int    (selected arm index for this call)
  coeffs_out       list[float]  (updated rewards and visits, same layout as coeffs_in)

Rules the function MUST follow:
1. No default argument values
2. Return tuple (int, list[float])
3. No module-level mutable state — coeffs_in/coeffs_out carry all learning state
4. UCB1 formula: score(a) = mean_reward(a) + C * sqrt(log(total_visits) / visits(a))
5. Exploration constant C = 1.5 (adjustable via prompt if needed)
6. First-visit initialization: if any arm has 0 visits, return it in round-robin order
7. Include a __main__ smoke test that runs 50 rounds with alternating like/dislike and
   confirms: arm_out is in range [0, N_ARMS-1], coeffs_out has length 2*N_ARMS,
   and the most-liked arm gets more visits than others after 50 rounds
8. Confirm smoke test passes before recommending LabVIEW wiring

LabVIEW integration note:
- Store coeffs_out in a LabVIEW shift register (1D DBL Array initialized to zeros)
- Store arm_out in an I32 shift register
- On each loop iteration: read shift registers → call Python Node → write shift registers back
- Persist coeffs to file (CSV) on VI shutdown; reload at startup
```

---

### 11. Generate a Python PID Auto-Tuner for cRIO

> **Lesson learned:** The bioreactor DO control demo showed that a Python hill-climbing tuner
> running on a laptop, connected to a cRIO over TCP, can improve PID gains within a few 30-second
> windows. Key: all tuning logic is in Python; the cRIO only runs the hard real-time PID loop.

```
Write a Python script (not a LabVIEW Python Node function) that acts as a PID auto-tuner
for a cRIO real-time controller communicating over TCP.

PURPOSE: [e.g., "tune Kp, Ki, Kd for a dissolved oxygen control loop in a bioreactor"]
CRIO_IP: [IP address of the cRIO, e.g., "192.168.1.10"]
CRIO_PORT: [TCP port, e.g., 50000]
PROCESS_VARIABLE: [name and units, e.g., "DO (% saturation)"]
SETPOINT_RANGE: [e.g., "30–90 % saturation"]
ACTUATOR: [e.g., "air pump PWM 0–100 %"]

COMMUNICATION PROTOCOL (cRIO sends each sample):
  Packet format: 7 doubles (big-endian)
  Fields: time_s, pv_meas, pv_sp, u_out, kp, ki, kd

COMMUNICATION PROTOCOL (Python sends updated gains):
  Packet format: 3 doubles (big-endian)
  Fields: kp_new, ki_new, kd_new

TUNING ALGORITHM:
  - Collect a rolling window of [window_s] seconds of data
  - Compute reward = negative integral absolute error over the window
  - Use hill-climbing with small random perturbations to Kp and Ki
  - If reward improved: keep new gains; if not: revert to best known gains
  - Apply gains to cRIO by sending the 3-double packet

CONSTRAINTS:
  Kp: [min, max]
  Ki: [min, max]
  Kd: 0.0 (keep fixed unless specified)
  Max gain change per step: [e.g., 0.1 for Kp, 0.01 for Ki]

Rules:
1. No external libraries beyond socket and struct (runs on any Python 3.8+ environment)
2. Print console output showing: window timestamp, reward, current gains, best gains
3. Graceful shutdown on KeyboardInterrupt
4. Add a __main__ guard
5. Include a mock-server test mode that simulates cRIO responses for offline testing
```

---

### 12. Generate a Freq-to-Drum Bridge Function

```
Write a Python function for the LabVIEW Python Node that bridges a melody-learner output
(MIDI frequency in Hz) to a drum synthesizer input (drum ID integer).

FUNCTION NAME: freq_to_drum_id_py

DRUM FREQUENCY TABLE:
  drum_id 0 = kick     →  65.41 Hz
  drum_id 1 = snare    →  82.41 Hz
  drum_id 2 = hihat    →  98.00 Hz
  drum_id 3 = tom-hi   → 123.47 Hz
  drum_id 4 = tom-mid  → 146.83 Hz
  drum_id 5 = tom-lo   → 174.61 Hz
  drum_id 6 = crash    → 220.00 Hz
  drum_id 7 = ride     → 261.63 Hz

INPUT:  freq   float (Hz)
OUTPUT: drum_id  int (0–7)

Rules: no default args, return plain int, no numpy, clamp out-of-range to 0,
__main__ smoke test for all 8 frequencies plus edge cases.
```

---

### 13. Generate a Stateful Coefficient Manager

```
Write two Python helper functions for the LabVIEW Python Node that manage AI coefficient
state persistence:

FUNCTION 1: save_coeffs(path: str, coeffs: list[float]) -> str
FUNCTION 2: load_coeffs(path: str, expected_len: float) -> list[float]

Rules: no numpy, use csv module, no default args, __main__ smoke test with 256-element round-trip.
```

---

## LabVIEW ↔ Python Complete Data Type Mapping

### Scalar Types

| LabVIEW Type | Python Type | Notes |
|---|---|---|
| DBL (double) | `float` | Most common numeric type |
| SGL (single) | `float` | Python always uses float64 internally |
| I32 (integer) | `int` | Cast with `int()` if needed |
| U32 (unsigned) | `int` | Same treatment as I32 |
| Boolean | `int` | Pass as `1` or `0` — no native bool |
| String | `str` | Enum and ring controls pass their string label |

### Array Types

| LabVIEW Type | Python Return Type | Return Terminal Wiring |
|---|---|---|
| 1D Array of DBL | `list[float]` | Empty **1D DBL Array** constant |
| 1D Array of I32 | `list[int]` | Empty **1D I32 Array** constant |
| 1D Array of String | `list[str]` | Empty **1D String Array** constant |
| 2D Array of DBL | `list[list[float]]` | Empty **2D DBL Array** constant |

### Cluster / Multiple Return Types

| LabVIEW Type | Python Return | Example |
|---|---|---|
| Cluster of (DBL, DBL) | `tuple[float, float]` | `return (pressure, flow)` |
| Cluster of (I32, 1D Array of DBL) | `tuple[int, list[float]]` | `return (arm_id, coeffs)` |
| Cluster of (I32, I32, 1D Array of DBL) | `tuple[int, int, list[float]]` | `return (arm_c, arm_r, coeffs)` |

### What Python CANNOT Return to LabVIEW

| Type | Why It Fails | Use Instead |
|---|---|---|
| `np.ndarray` | Not a plain Python type | `list[float]` |
| `np.float64` | NumPy scalar | `float(value)` |
| `dict` | No LabVIEW equivalent | `tuple` |
| `(list,)` tuple wrapping a list | Causes `tupleobject.c:107` | Return `list` directly |

---

## Constraint Reference Card

| Constraint | Correct ✓ | Incorrect ✗ |
|---|---|---|
| Single array return | `return [v1, v2, v3]` | `return ([v1, v2, v3],)` |
| Multiple return with array | `return (scalar, [v1, v2])` | `return np.array(...)` |
| Input args | All positional, **no defaults** | `def f(x, y=0.0)` |
| Numeric types | `float`, `int`, `str` only | `np.float32`, `np.int64` |
| State variables | Passed in + returned out | Module-level `global state = {}` |
| Parameter order | **Frozen once released** | Never reorder without version bump |
| Pre-release test | `python file.py` must print PASS | Only tested by wiring in LV |
| AI state | Flat `list[float]` in/out | File I/O inside the called function |

---

## Pre-Integration Testing Protocol

```cmd
REM Step 1: Run standalone smoke test
"C:\path\to\python.exe" your_file.py
REM Expected: all PASS lines, then OVERALL: PASS

REM Step 2: Verify function is importable
"C:\path\to\python.exe" -c "import importlib.util; spec=importlib.util.spec_from_file_location('m', r'C:\path\to\your_file.py'); m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m); print([x for x in dir(m) if not x.startswith('_')])"

REM Step 3: Manually call with representative values
"C:\path\to\python.exe" -c "from your_file import your_function; print(your_function(arg1, arg2))"

REM Step 4: Only if all three pass — wire into LabVIEW
```

---

## Parameter Order Lock Policy

Once wired into a released VI, the parameter order is **frozen**.

- Never remove, insert, or reorder parameters without creating a `_v2` function name
- New parameters may be appended at the END only, with no defaults
- Document changes in docstring version history

**Signal to AI:** *"This function is released. Do NOT change parameter order. Append new params at the END only. If restructuring is required, create a `_v2` function."*

---

## Git / SVN Workflow (Optional)

```bash
# Feature branch → smoke test → commit → tag
git checkout -b feature/add-drum-bridge
python freq_to_drum_id_py.py          # must print PASS
git add freq_to_drum_id_py.py
git commit -m "feat: add freq_to_drum_id_py bridge"
git tag v1.2.0-drum-bridge
git push origin feature/add-drum-bridge
```

**.gitignore:**
```
__pycache__/
*.pyc
*.pyo
```

> Never commit until smoke test passes. Use `feat:`, `fix:`, `chore:`, `docs:` commit prefixes.

---

## Waveform Debugging Checklist

| Symptom | Likely Cause | Fix |
|---|---|---|
| Amplitude ~1e-10 | Amplitude control not wired to terminal 1 | Verify terminal wiring order |
| Triangle instead of sine | `dt` too large — Nyquist violation | Use `dt = 0.001` for ≤100 Hz |
| Flat line | `n_samples` = 0 or 1 | Set `n_samples = 1000` minimum |
| Distorted sweep | Phase substitution, not accumulation | Use `phase += 2π·f·dt` |
| Error 1671 | Wrong file path or function name | Confirm exact `def` name in file |
| `SystemError tupleobject.c:107` | Return terminal wired as scalar DBL | Wire with empty **1D DBL Array** constant |
| Beats wrong timing | Wrong BPM constant in beat_samples | Beat=120, Rock=132, Jazz/Others=112 BPM |
| UCB1 arm always 0 | Coefficients not reloaded after restart | Load coeffs CSV at VI startup |
| Wrong drum sounds | freq_to_drum_id not applied | Bridge melody freq → drum_id before synth call |

---

## Lessons Learned — Beats, Tunes & AI Integration

### Signal Generation
- **Phase accumulation mandatory for sweeps:** `phase += 2*pi*f*dt` per sample, not `sin(2*pi*f*i*dt)`
- **`waveform_type` normalization:** `str(waveform_type).strip().lower()` to tolerate LabVIEW string variations
- **`n_samples` is float from LabVIEW:** Always cast immediately: `n = int(length_pts)`
- **Unrecognized type fallback:** Return sine rather than zeros to avoid silent failures in demos

### Beats & Drum Patterns
- **Two .so files need a bridge:** melody_learn_v3.so outputs Hz; drum_synth.so expects drum_id int
- **Clamp beat_samples output** to [2205, 44100] to avoid RT buffer overruns
- **LCG noise on NI Linux RT:** Use custom LCG instead of `rand()` to avoid stdlib RT issues
- **Normalize audio buffers** after synthesis to prevent clipping in LabVIEW sound output

### AI Learning (UCB1)
- **Flat coefficient array:** `list[float]` of length `2 * N_ARMS` round-trips cleanly through LabVIEW shift register
- **Pending credit (+0.5):** Add before reward is known to prevent arm re-selection on next call
- **Persist coeffs to CSV** on cRIO at VI shutdown; initialize all-zeros on missing file
- **UCB1 C = 1.5** is a good starting point; raise for higher-variance domains
- **Clamp style index** to `[0, N_STYLES-1]`; LabVIEW ring controls can send out-of-range values

### PID Tuning
- **Python tunes, cRIO controls:** Hard RT PID at 100 Hz on cRIO; Python optimizes on 30-second window
- **Hill-climbing is sufficient** for demo-grade tuning; no ML framework needed
- **Reward = negative IAE** (Integral Absolute Error) — practical and interpretable
- **Always clamp gains** before sending to cRIO; never destabilize the physical system
- **`struct.pack("!7d", ...)`** big-endian for cross-platform cRIO ↔ Python reliability

---

## numpy Installation (No Admin Rights)

```cmd
"C:\Users\[username]\AppData\Local\Python\pythoncore-3.14-64\python.exe" -m pip install numpy --user
"C:\Users\[username]\AppData\Local\Python\pythoncore-3.14-64\python.exe" -c "import numpy; print(numpy.__version__)"
```

---

## Quick Error Lookup

| LV Error | Meaning | Fix |
|---|---|---|
| 1672 | Python session failed | Check Tools → Options → Python path |
| 1671 | Module/function not found | Verify exact file path and function name |
| 1663 | Bitness mismatch | Both LV and Python must be 64-bit |
| `SystemError tupleobject.c:107` | Scalar return terminal on array output | Wire empty **1D DBL Array** constant to return terminal |
| `TypeError` | Wrong argument count | All terminals must be wired; no defaults |
| All outputs = 0.0 | Silent failure | Wire error out; verify terminal order |
| Drum always kick | Bridge not applied | Apply freq_to_drum_id before drum synth |
| UCB1 always arm 0 | Coeffs not persisted | Save/load coeffs CSV; check shift register init |
| PID gains not updating | TCP packet mismatch | Verify struct.pack format matches cRIO layout |

---

## References

- NI Python Node docs: https://www.ni.com/en/support/documentation/supplemental/18/using-the-python-node-in-labview.html
- NI KB — Advanced Datatypes: https://knowledge.ni.com/KnowledgeArticleDetails?id=kA03q000000oyaHCAQ
- LV_Py_101 Repository: https://github.com/zach-olson-cyth/LV_Py_101
- LAVA Forums: https://lavag.org/
- NI Community: https://forums.ni.com/t5/LabVIEW/bd-p/170
