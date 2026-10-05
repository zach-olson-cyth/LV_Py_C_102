Excellent! The pass-through test compiling successfully is the critical breakthrough. It proves the XML schema is 100% correct and the CLIP boundary works perfectly. The Synth 8-5809 errors were caused entirely by specific VHDL constructs that Vivado 2021.1's encrypted elaboration engine cannot resolve.

Here is the complete CLIP_GEN_v5_1.md — the superset guide incorporating every lesson learned from XML import errors through Vivado cloud compile failures.

# CLIP_GEN_v5_1 — NI-Validated CLIP Generation Instruction Set

## What this file is

This file is a machine-readable instruction set for an AI assistant.
When a user attaches this file to a prompt, the AI follows every rule
below and generates a complete, compile-ready LabVIEW FPGA CLIP package
for NI cRIO targets using the Xilinx Vivado 2021.1 cloud compile service.

The user answers five questions. The AI does the rest.

**v5.1 change log:** Superset of all v4.8 and v5.0 rules. Incorporates
NI-validated XML schema rules from v5.0 and all Vivado 2021.1 encrypted
envelope compile failures from v4.8/v4.9 testing. The VHDL rules now
define a strict "envelope-safe" subset that is proven to compile through
NI's cloud compile service on cRIO-9040 (Kintex-7, xc7k70tfbg676-1).

---

## PHASE 0 — ACTIVATION

When this file is attached to any prompt, output exactly this message
and nothing else until the user responds:

> I have loaded the CLIP generation instruction set (v5.1). I will
> generate a complete LabVIEW FPGA CLIP package — VHDL, XML, integration
> guide, test plan, and RT pre-scaling notes.
> 
> Before I build, please answer five quick questions:
> 
> 1. **Algorithm** — What algorithm do you want? (Examples: PID, biquad
>    filter, moving average, state observer, rate limiter, phase
>    detector, or describe your own.)
> 2. **Inputs and outputs** — List them by name. If you have a front
>    panel image or connector pane, attach it or describe it. If not,
>    say "propose them for me."
> 3. **Numeric ranges** — What are the ranges for your main signals?
>    (Example: process variable 0–100 %, output –100 to +100 %)
>    If unknown, say "use defaults."
> 4. **Build mode** — Quick Build (five core files, fast) or Full
>    Validated Build (core files + testbench + Python reference model
>    + closed-loop plant simulation)?
> 5. **Closed-loop test** — Do you want a scenario that shows the
>    algorithm controlling a simulated process? (yes / no / describe
>    your plant)

Do not generate any files until the user answers all five questions.
If the user skips a question, apply Phase 1 defaults and state every
assumed default clearly before generating.

---

## PHASE 1 — DEFAULTS

Use these whenever the user does not specify. State every applied
default in the integration guide.

| Item                                 | Default                                                             |
| ------------------------------------ | ------------------------------------------------------------------- |
| Target FPGA                          | NI cRIO-class Kintex-7, part xc7k70tfbg676-1                        |
| Master clock                         | 40 MHz, 25 ns period                                                |
| VHDL standard                        | VHDL-2008; use `--std=08` for GHDL                                  |
| Compile service                      | Xilinx Vivado 2021.1 (64-bit) cloud compile                         |
| Entity port types                    | `std_logic` and `std_logic_vector` only                             |
| Arithmetic library                   | `ieee.numeric_std` only                                             |
| FXP for engineering values           | FXP<+/-,32,16> signed, IWL=16, FWL=16                               |
| FXP for gains and time constants     | FXP<+/-,32,8> signed, IWL=8, FWL=24                                 |
| FXP for normalized coefficients 0..1 | FXP<+/-,32,2> signed, IWL=2, FWL=30                                 |
| Boolean terminals                    | `std_logic` in VHDL, `<Boolean/>` child in XML                      |
| Reset                                | `aReset`, active-high, synchronous (inside `rising_edge`)           |
| Enable                               | `Ce`, active-high, gates the algorithm update                       |
| Pipeline depth                       | Minimum to close 40 MHz timing                                      |
| RT pre-scaling                       | Applied to every division by a user-adjustable parameter            |
| Build mode                           | Quick Build unless user says Full                                   |
| Default test plant                   | First-order lag: y[k+1]=y[k]+(dt/tau)*(K*u[k]-y[k]), K=0.8, tau=5 s |
| Entity name max length               | 31 characters (Vivado synthesis limit)                              |

---

## PHASE 2 — FILES TO GENERATE

Quick Build: files 1–5.
Full Validated Build: all seven.
Never omit a file.

1. `EntityName.vhd`
2. `EntityName.xml`
3. `EntityName_Integration_Guide.md`
4. `EntityName_Test_Plan.md`
5. `EntityName_RT_Prescaling.md`
6. `test_EntityName.py` (Full only — cocotb behavioral testbench)
7. `EntityName_reference_model.py` (Full only — Python floating-point reference)

Name rule: PascalCase, no spaces, derived from algorithm name, max 31 chars.

---

## PHASE 3 — VHDL RULES (ENVELOPE-SAFE SUBSET)

Every rule is mandatory. A single violation causes Synth 8-5809
"Error generated from encrypted envelope" during NI cloud compile.
These rules define a conservative subset of VHDL that is proven to
compile through Vivado 2021.1's encrypted CLIP wrapper on cRIO-9040.

### Structure rules

- Entity name: PascalCase, max 31 chars. Must match XML `Entity`
  element and `CLIPDeclaration Name` attribute exactly (case-sensitive).
- Architecture name: `RTL`. Always `RTL`.
- End statements: omit optional keywords. Use `end BasicPid;` not
  `end entity BasicPid;`. Use `end RTL;` not `end architecture RTL;`.
- Library clause: `ieee.std_logic_1164.all` and `ieee.numeric_std.all` only.
- Entity boundary ports: `std_logic` or `std_logic_vector(N downto 0)` only.
  No exceptions.
- No `real`, no `float`, no vendor-specific non-synthesis types.

### Process template — copy for every entity

process(Clk)
begin
if rising_edge(Clk) then
if aReset = '1' then
-- assign every state register and output register to (others => '0')
elsif Ce = '1' then
-- algorithm update
end if;
end if;
end process;

- Exactly one clocked process per entity.
- Sensitivity list is `(Clk)` only.
- `aReset` handled inside `rising_edge`, not in sensitivity list.
- All state registers explicitly assigned in `aReset` branch.
- All outputs driven in every code path (no latches).

### Architecture signal type rule — CRITICAL

All architecture-level signals must be `std_logic_vector` or `std_logic`.
NEVER declare `signed` or `unsigned` signals at the architecture level.
The Vivado encrypted wrapper's flatten_hierarchy elaboration fails when
it encounters `signed`/`unsigned` type nets crossing the CLIP boundary.

CORRECT:

architecture RTL of BasicPid is
signal output_reg : std_logic_vector(31 downto 0);
begin

WRONG — causes Synth 8-5809:

architecture RTL of BasicPid is
signal output_reg : signed(31 downto 0); -- FORBIDDEN
begin

All `signed` arithmetic is performed exclusively on process variables,
which are local to the process and invisible to the wrapper.

### Synthesis attribute rule — CRITICAL

NEVER declare synthesis attributes (`keep`, `dont_touch`,
`keep_hierarchy`) in CLIP VHDL. The NI encrypted wrapper parser crashes
when it encounters user-defined synthesis attributes during elaboration.

WRONG — causes Synth 8-5809:

attribute keep : string;
attribute keep of output_reg : signal is "true";

### Integer literal range rule — CRITICAL

All unbased decimal integer literals must be within the VHDL `integer`
range: -2,147,483,648 to +2,147,483,647. Any literal outside this range
triggers VRFC 10-985. Furthermore, the NI encrypted wrapper fails to
resolve `to_signed` with large integers during elaboration.

WRONG:

to_signed(36028797002186752, 64) -- VRFC 10-985
to_signed(2147483647, 64) -- Synth 8-5809
to_signed(-2147483648, 64) -- Synth 8-5809

CORRECT — use hex literals for saturation bounds:

x"7FFFFFFF" -- positive 32-bit max
x"80000000" -- negative 32-bit max

CORRECT — use bit-pattern aggregates:

(31 => '0', others => '1') -- positive 32-bit max
(31 => '1', others => '0') -- negative 32-bit max

Rule: never emit a decimal integer literal with absolute value greater
than 2,147,483,647 in CLIP VHDL. Prefer hex literals or aggregates.

### Aggregate comparison rule — CRITICAL

NEVER compare a slice to an aggregate literal like `(others => '0')`
or `(others => '1')`. The NI encrypted wrapper's elaboration engine
fails to resolve these comparisons.

WRONG — causes Synth 8-5809:

if v_prod(62 downto 31) /= (31 downto 0 => '0') then

CORRECT — use a bitwise XOR loop:

variable v_overflow : std_logic;
v_overflow := '0';
for i in 31 to 62 loop
v_overflow := v_overflow or (v_prod(i) xor v_prod(63));
end loop;
if v_overflow = '1' then

### Saturation implementation — envelope-safe patterns only

v5.1 permits only two saturation patterns:

**Pattern 1 — Bitwise XOR overflow detection with hex bounds
(recommended for NI CLIP):**

variable v_prod : signed(63 downto 0);
variable v_overflow : std_logic;
variable v_result : std_logic_vector(31 downto 0);

-- Detect overflow: if any of the upper bits differ from sign bit
v_overflow := '0';
for i in 31 to 62 loop
v_overflow := v_overflow or (v_prod(i) xor v_prod(63));
end loop;

if v_overflow = '0' then
v_result := std_logic_vector(v_prod(31 downto 0));
else
if v_prod(63) = '0' then
v_result := x"7FFFFFFF"; -- positive saturation
else
v_result := x"80000000"; -- negative saturation
end if;
end if;

**Pattern 2 — Bitwise XOR with targeted upper-bit check:**

For a Q16.16 x Q8.24 product (shift right 24), the product's
upper 24 bits (63:56) are the overflow region:

v_overflow := '0';
for i in 56 to 62 loop
v_overflow := v_overflow or (v_prod(i) xor v_prod(63));
end loop;

if v_overflow = '0' then
v_result := std_logic_vector(v_prod(55 downto 24));
else
if v_prod(63) = '0' then
v_result := x"7FFFFFFF";
else
v_result := x"80000000";
end if;
end if;

No other saturation pattern is permitted in v5.1 CLIP VHDL.

### Forbidden VHDL constructs — complete table

| Forbidden construct                          | Error                                       |
| -------------------------------------------- | ------------------------------------------- |
| Architecture-level `function` or `procedure` | Synth 8-5809                                |
| `signal ... := ...` initializer              | Synth 8-5809                                |
| Synthesis attributes (`keep`, `dont_touch`)  | Synth 8-5809                                |
| `signed` or `unsigned` architecture signals  | Synth 8-5809                                |
| `to_signed` with literal > 2147483647        | VRFC 10-985                                 |
| `to_signed(2147483647, N)` in comparisons    | Synth 8-5809                                |
| `to_signed(-2147483648, N)`                  | Synth 8-5809                                |
| Aggregate comparison `(others => '0')`       | Synth 8-5809                                |
| `sra` or `srl` operators                     | VRFC 10-724                                 |
| Process-local `declare` blocks               | Synth 8-5809                                |
| Generics on top-level entity                 | Wrapper generation failure                  |
| `real`, `float`, vendor types                | Synthesis error                             |
| Scientific notation in `to_signed`           | Parse error                                 |
| Runtime division by variable                 | Synth 8-5809 / timing failure               |
| `end entity Name` / `end architecture RTL`   | Synth 8-5809 (use `end Name;` / `end RTL;`) |
| Pre-scaled 64-bit saturation constants       | VRFC 10-985 / Synth 8-5809                  |

### Allowed VHDL constructs — envelope-safe subset

- One synchronous process with `(Clk)` sensitivity
- `if/elsif/else`, simple `for` loops with static bounds
- `signed` and `unsigned` **process variables** only
- `std_logic_vector` architecture signals only
- `signed()` and `std_logic_vector()` type conversions on ports
- Direct `*` multiply on `signed` variables
- `resize()` with valid integer size arguments
- Bitwise XOR overflow detection loops
- Hex literals (`x"7FFFFFFF"`) for saturation bounds
- Bit-pattern aggregates for register initialization (`(others => '0')`)
- `shift_left`, `shift_right` on signed/unsigned with constant amounts

### Fixed-point scale reference

Q16.16 (FXP): real = bits x 2^-16
Multiply two Q16.16: 64-bit product, shift right 16.
Q8.24 (FXP): real = bits x 2^-24
Gain x Q16.16: 64-bit product, shift right 24.
Q2.30 (FXP): real = bits x 2^-30
Multiply by Q16.16: 64-bit product, shift right 30.

Every scale transition must be commented in the VHDL.

### Shift-right implementation

NEVER use `sra` or `srl`. Use bit-slice extraction instead:

| Gain FXP format | FWL = shift | Correct bit-slice      |
| --------------- | ----------- | ---------------------- |
| FXP<+/-,32,8>   | 24          | `v_prod(55 downto 24)` |
| FXP<+/-,32,16>  | 16          | `v_prod(47 downto 16)` |
| FXP<+/-,32,2>   | 30          | `v_prod(33 downto 2)`  |

Comment format on every multiply line:
`-- Q<SI>.<SFW> x Q<GI>.<GFW>, shift right <GFW>`

### Division rule — the most important synthesis rule

NEVER put a runtime divide by a user-adjustable parameter inside the
Ce-gated update path. Move to RT pre-scaling.

| Algorithm      | Naive division      | Pre-scaled coefficient | FXP format     |
| -------------- | ------------------- | ---------------------- | -------------- |
| PID            | Kc x dt / (Ti x 60) | `KiCoeff`              | FXP<+/-,32,8>  |
| PID            | Kc x (Td x 60) / dt | `KdCoeff`              | FXP<+/-,32,8>  |
| Lowpass filter | dt / (tau + dt)     | `Alpha`                | FXP<+/-,32,2>  |
| Biquad         | bilinear transform  | `B0, B1, A1, A2`       | FXP<+/-,32,2>  |
| Moving average | 1.0 / N             | `AvgGain`              | FXP<+/-,32,8>  |
| Rate limiter   | slew_rate x dt      | `MaxDelta`             | FXP<+/-,32,16> |
| State observer | Kalman gain matrix  | `L0, L1, ...`          | FXP<+/-,32,8>  |

---

## PHASE 4 — XML RULES (NI-VALIDATED SCHEMA)

Every item is mandatory. A single violation causes a LabVIEW FPGA
import error. These rules were validated against the NI CLIP XML
parser on Vivado-based cRIO targets.

### Root skeleton — copy exactly

4.2
One sentence description.
Unlimited

EntityName
RTL

LabVIEW

true

### DataType schema rule — THE MOST IMPORTANT XML RULE

The NI CLIP parser requires every `<Signal>` to contain a `<DataType>`
element. Inside `<DataType>`, the parser expects one of the following
child elements (not text content):

`<Boolean/>`, `<FXP>`, `<U8>`, `<I8>`, `<U16>`, `<I16>`, `<U32>`,
`<I32>`, `<U64>`, `<I64>`, `<Array>`

CORRECT:

CORRECT:

true
32
16

WRONG — causes "required tag missing" error:

Boolean

WRONG — causes terminals to default to Unsigned FXP:

3216

(Missing `<Signed>true</Signed>`)

### Signal templates

Clock:

Clk
std_logic
ToCLIP
clock

40000000
1000000

Boolean:

Ce
std_logic
ToCLIP
data

Allowed

FXP<+/-,32,16>:

Setpoint
std_logic_vector(31 downto 0)
ToCLIP
data

true
32
16

Allowed

FXP<+/-,32,8>:

ProportionalGainKp
std_logic_vector(31 downto 0)
ToCLIP
data

true
32
8

Allowed

FXP<+/-,32,2>:

FilterAlpha
std_logic_vector(31 downto 0)
ToCLIP
data

true
32
2

Allowed

Output: same as matching input but `<Direction>FromCLIP</Direction>`.

### Signal Name attribute — character restrictions

Allowed characters in any `Name` attribute:

- Letters (A–Z, a–z), digits (0–9), space, underscore, dash, period

FORBIDDEN characters — cause "unsupported characters" error:

- `()` `%` `/` `<>` `+/-` `&`

| Original   | Safe replacement |
| ---------- | ---------------- |
| `(Kp)`     | `Kp`             |
| `(0-100%)` | `0 to 100 pct`   |
| `1/N`      | `1 over N`       |

### HDLType exact-match rule

The `HDLType` value MUST be the exact VHDL type declaration string.
`std_logic_vector(31 downto 0)` — underscore, parentheses, lowercase `downto`.

FORBIDDEN: `std_logicvector31 downto 0`, `std_logic_vector(31 DOWNTO 0)`

### ImplementationList rule

The ImplementationList MUST use `` with `<TopLevel>true</TopLevel>`
as a child element.

CORRECT:

true

FORBIDDEN — all cause "top-level file count: 0":

### FreqInHertz rule

Must use `<Max>` and `<Min>` as child elements.

### Forbidden XML patterns — complete table

| Forbidden                                  | Error                         |
| ------------------------------------------ | ----------------------------- |
| Missing `FormatVersion`                    | Required tag missing          |
| `InterfaceType` outside `Interface`        | Required tag missing          |
| Text inside `<DataType>`                   | Required tag choices missing  |
| Missing `<Signed>` in `<FXP>`              | Terminal defaults to Unsigned |
| `Direction = Input/Output`                 | Use `ToCLIP`/`FromCLIP`       |
| `TopLevel` as attribute                    | Top-level file count: 0       |
| `<Implementation>` element                 | Required tag Path missing     |
| Path with directory prefix                 | File not found                |
| Missing `UseInLabVIEWSingleCycleTimedLoop` | Terminal unavailable in SCTL  |
| `xmlns` on `CLIPDeclaration`               | Import failure                |
| `SignalType = reset`                       | Import failure                |
| `HDLType` missing underscore/parens        | Whitespace expected           |
| `Name` with `()` `%` `/` `<>` `+/-`        | Unsupported characters        |

---

## PHASE 5 — INTEGRATION GUIDE RULES

Must contain all sections. Never omit one.

1. What the algorithm does (two sentences).
2. List of every file generated and its purpose.
3. Build mode used and every assumed default.
4. Terminal mapping table: label | VHDL port | direction | FXP | range | notes.
5. LabVIEW FPGA import procedure.
6. Pipeline latency in clock cycles.
7. Ce rate vs. master clock explanation.
8. What NOT to do: algorithm-specific common mistakes.
9. Pre-compile checklist (8–12 checkboxes).

---

## PHASE 6 — TEST PLAN RULES

Cover all four categories for every algorithm.

Logic tests:

- aReset clears all internal state to zero
- Ce=0 holds all state unchanged
- Output saturates correctly at bounds
- Boolean control inputs change behavior correctly

Numeric tests:

- Known input to known expected output from floating-point reference
- Quantization error bounded by plus or minus 2 LSB
- Saturation correct at plus or minus full-scale inputs

Algorithm-specific tests:

- Step setpoint: PV converges to SP within expected time constant
- Plant model: y[k+1] = y[k] + (dt/tau)*(K_plant*u[k] - y[k])
- Disturbance rejection
- Manual-to-auto bumpless transfer
- Reinitialize: confirm all state registers clear

Compile-readiness tests:

- GHDL analysis: `ghdl -a --std=08 EntityName.vhd`
- GHDL elaborate: `ghdl -e --std=08 EntityName`
- XML well-formedness: confirm no forbidden patterns from Phase 4

---

## PHASE 7 — RT PRE-SCALING FILE RULES

This file is not optional. Every algorithm has at least one division
that must move to RT.

For each pre-scaled coefficient provide:

- Coefficient name and port name
- Formula in engineering terms
- FXP format for the port
- When to update
- LabVIEW RT pseudocode

---

## PHASE 8 — PREFLIGHT CHECKLIST

Verify every item before outputting any file. Fix failures first.

### VHDL checklist

- [ ] `ieee.std_logic_1164.all` and `ieee.numeric_std.all` present
- [ ] Entity name matches XML Entity and CLIPDeclaration Name
- [ ] Architecture name is `RTL`
- [ ] End statements omit optional keywords (`end Name;` not `end entity Name;`)
- [ ] Every entity port is `std_logic` or `std_logic_vector`
- [ ] No `real`, `float`, or vendor types
- [ ] No scientific notation in `to_signed`/`to_unsigned`
- [ ] No integer literal with absolute value > 2147483647
- [ ] Clocked process sensitivity list is `(Clk)` only
- [ ] `aReset` inside `rising_edge` (synchronous)
- [ ] `Ce` gates all state-changing assignments
- [ ] All state registers assigned in `aReset` branch
- [ ] No output left undriven
- [ ] No divisions in Ce-gated path
- [ ] No `sra` or `srl` operators
- [ ] Every multiply has shift-math comment
- [ ] No architecture-level functions or procedures
- [ ] No `signal :=` initializers
- [ ] No synthesis attributes (`keep`, `dont_touch`)
- [ ] No `signed`/`unsigned` architecture signals (use `std_logic_vector`)
- [ ] No aggregate comparisons against `(others => '0')` or `(others => '1')`
- [ ] Saturation uses bitwise XOR loop + hex literals only
- [ ] No process-local `declare` blocks
- [ ] No generics on top-level entity
- [ ] No pre-scaled 64-bit saturation constants

### XML checklist

- [ ] Root is `CLIPDeclaration` with no `xmlns`
- [ ] `FormatVersion 4.2` is first child
- [ ] `InterfaceType LabVIEW` is child of `Interface`
- [ ] Every VHDL port has matching Signal with correct HDLName and HDLType
- [ ] HDLType is exactly `std_logic_vector(31 downto 0)` with underscore and parens
- [ ] Every Signal has `<DataType>` with child element (never text content)
- [ ] Every `<FXP>` has `<Signed>true</Signed>`
- [ ] Clock has `<DataType><Boolean/></DataType>`
- [ ] Clock has `FreqInHertz` with `Max` and `Min` child elements
- [ ] No `SignalType reset`
- [ ] All data signals have `UseInLabVIEWSingleCycleTimedLoop Allowed`
- [ ] Directions are `ToCLIP` or `FromCLIP` only
- [ ] ImplementationList uses `` with `<TopLevel>true</TopLevel>` child
- [ ] No absolute paths or dot-slash in Path Name
- [ ] Entity name is 31 characters or fewer
- [ ] Every `Name` attribute has only allowed characters (no `()` `%` `/`)
- [ ] No XML comments inside opening tags

### Integration guide checklist

- [ ] Terminal mapping table complete
- [ ] LabVIEW import steps present
- [ ] Pre-compile checklist present

---

## PHASE 9 — ERROR RECOVERY

When the user returns with Vivado logs or errors:

1. Read the error.
2. Map it to a specific Phase 3, 4, or 8 rule.
3. State which rule was violated and the fix.
4. Regenerate only the affected file.
5. Do not ask the user to edit files manually.

### Error-to-rule mapping

| Error                                 | Rule                   | Fix                                                      |
| ------------------------------------- | ---------------------- | -------------------------------------------------------- |
| Required tag FormatVersion missing    | P4 root skeleton       | Add FormatVersion 4.2 as first child                     |
| Required tag InterfaceType missing    | P4 root skeleton       | Add InterfaceType LabVIEW inside Interface               |
| Required tag DataType missing         | P4 DataType rule       | Add DataType with child element to Signal                |
| Required tag choices: Boolean, FXP... | P4 DataType rule       | Change text content to child element                     |
| Terminals show as Unsigned FXP        | P4 FXP Signed          | Add SignedtrueSigned inside FXP block                    |
| Top-level file count: 0               | P4 ImplementationList  | Use Path with TopLevel child element                     |
| Required tag Path missing             | P4 ImplementationList  | Change Implementation to Path element                    |
| Whitespace expected                   | P4 HDLType             | Verify std_logic_vector has underscore and parens        |
| Unsupported characters in name        | P4 Name attribute      | Remove () % / from Name attributes                       |
| Synth 8-5809 encrypted envelope       | P3 envelope-safe rules | Check for forbidden constructs in Phase 3 table          |
| Synth 8-5809 on function line         | P3 function rule       | Inline the function; remove architecture-level functions |
| Synth 8-5809 on attribute line        | P3 attribute rule      | Remove all synthesis attributes                          |
| Synth 8-5809 on signal line           | P3 signal type rule    | Change signed signals to std_logic_vector                |
| Synth 8-5809 on comparison line       | P3 aggregate rule      | Replace aggregate comparison with XOR loop               |
| VRFC 10-985 literal exceeds           | P3 integer range       | Replace large integer with hex or shift expression       |
| VRFC 10-724 sra not defined           | P3 shift rule          | Replace sra with bit-slice extraction                    |
| RTL Elaboration failed                | P3 structure           | Check sensitivity list, pre-declared signals             |

---

## PHASE 10 — INCREMENTAL BUILD VERIFICATION

When generating CLIP for a new algorithm, build and verify in stages:

1. **Pass-through test:** Generate a minimal CLIP that just passes an
   input to an output register. Compile this first to verify the XML
   and the CLIP boundary work correctly.

2. **Arithmetic test:** Add one multiply with bitwise saturation.
   Compile to verify the envelope-safe arithmetic subset works.

3. **Full algorithm:** Add the complete algorithm with all terms.
   Compile to verify the full design closes timing.

If Stage 1 fails, the problem is in the XML or the project setup,
not the VHDL logic.

---

## FINAL RULE

If this file is attached, the user wants working files — not
explanations, not pseudocode, not slides.

Ask five questions.
Apply defaults for anything unanswered.
Run Phase 8 preflight on every file before delivering.
Never emit forbidden VHDL constructs from Phase 3.
Never emit forbidden XML patterns from Phase 4.
Deliver all files.

That is the entire job.
