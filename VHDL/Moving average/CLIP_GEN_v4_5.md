# CLIP_GEN_v4_5 — AI Instruction File for LabVIEW FPGA CLIP Node Generation

## What This File Is

This file is a machine-readable instruction set for an AI assistant.
When a user attaches this file to a prompt, the AI follows every rule below
and generates a complete, compile-ready LabVIEW FPGA CLIP package without
requiring the user to understand HDL, fixed-point arithmetic, NI XML schemas,
or Vivado synthesis rules.

**The user answers five questions. The AI does the rest.**

**v4.5 changes from v4.4:** All v4.4 rules kept verbatim. Phase 4 XML
templates and rules updated to reflect the NI-validated CLIP XML schema.
Specific corrections: (1) `<DataType>` must use child element form, never
text content; (2) every `<FXP>` must contain `<Signed>true</Signed>`;
(3) clock signals require `<DataType><Boolean/></DataType>`; (4)
`<ImplementationList>` must use `<Path>` with `<TopLevel>true</TopLevel>`
as a child element, not as an attribute; (5) `<FreqInHertz>` must have
`<Max>` and `<Min>` as child elements; (6) entity name is max 31 chars.
Phase 8 XML checklist updated to match. Phase 9 error table updated.
New Phase 10 added: Python preflight checker that AI must run and pass
before delivering any file.

---

## PHASE 0 — ACTIVATION

When this file is attached to any prompt, output **exactly** this message
and nothing else until the user responds:

> I have loaded the CLIP generation instruction set (v4.5). I will generate
> a complete LabVIEW FPGA CLIP package — VHDL, XML, integration guide,
> test plan, and RT pre-scaling notes.
>
> Before I build, please answer five quick questions:
>
> 1. **Algorithm** — What algorithm do you want?
>    (Examples: PID, biquad filter, moving average, state observer,
>    rate limiter, phase detector, or describe your own.)
>
> 2. **Inputs and outputs** — List them by name. If you have a front panel
>    image or connector pane, attach it or describe it.
>    If not, say "propose them for me."
>
> 3. **Numeric ranges** — What are the ranges for your main signals?
>    (Example: process variable 0–100 %, output –100 to +100 %)
>    If unknown, say "use defaults."
>
> 4. **Build mode** — Quick Build (five core files, fast) or
>    Full Validated Build (core files + testbench + Python reference model
>    + closed-loop plant simulation)?
>
> 5. **Closed-loop test** — Do you want a scenario that shows the algorithm
>    controlling a simulated process? (yes / no / describe your plant)

Do not generate any files until the user answers all five questions.
If the user skips a question, apply Phase 1 defaults and state every
assumed default clearly before generating.

---

## PHASE 1 — DEFAULTS

Use these whenever the user does not specify.
State every applied default in the integration guide.

| Item | Default |
|---|---|
| Target FPGA | NI cRIO-class Kintex-7, part xc7k70tfbg676-1 |
| Master clock | 40 MHz, 25 ns period |
| VHDL standard | VHDL-2008; use `--std=08` for GHDL |
| Entity port types | `std_logic` and `std_logic_vector` only |
| Arithmetic library | `ieee.numeric_std` only |
| FXP for engineering values | FXP<+/-,32,16> signed, IWL=16, FWL=16, LSB=1.526e-5 |
| FXP for gains and time constants | FXP<+/-,32,8> signed, IWL=8, FWL=24, LSB=5.96e-8 |
| FXP for normalized coefficients 0..1 | FXP<+/-,32,2> signed, IWL=2, FWL=30, LSB=9.31e-10 |
| Boolean terminals | `std_logic` in VHDL, `<Boolean/>` child element in XML |
| Reset | `aReset`, active-high, **synchronous** (inside `rising_edge`) |
| Enable | `Ce`, active-high, gates the algorithm update |
| Pipeline depth | Minimum to close 40 MHz timing; documented in guide |
| RT pre-scaling | Applied to every division by a user-adjustable parameter |
| Build mode | Quick Build unless user says Full |
| Default test plant | First-order lag: y[k+1]=y[k]+(dt/tau)*(K*u[k]-y[k]), K=0.8, tau=5 s |
| Entity name max length | 31 characters (Vivado synthesis limit) |

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
6. `test_EntityName.py`  *(Full only — cocotb behavioral testbench)*
7. `EntityName_reference_model.py`  *(Full only — Python floating-point reference)*

**Name rule:** PascalCase, no spaces, derived from the algorithm name,
maximum 31 characters.

---

## PHASE 3 — VHDL RULES

Every rule is mandatory. Fix violations before delivering the file.

### Structure rules

- Entity name: PascalCase, max 31 chars. Must match XML `Entity` element and
  `CLIPDeclaration Name` attribute **exactly** (case-sensitive).
- Architecture name: `RTL`. Always `RTL`.
- Library clause: `ieee.std_logic_1164.all` and `ieee.numeric_std.all` only.
- Entity boundary ports: `std_logic` or `std_logic_vector(N downto 0)` only.
  **No exceptions.**
- Internal arithmetic: use `signed` or `unsigned` variables.
  Never arithmetic directly on `std_logic_vector`.
- No `real`, no `float`, no vendor-specific non-synthesis types anywhere.

### Process template — copy for every entity

```vhdl
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
```

- Exactly **one** clocked process per entity.
- Sensitivity list is `(Clk)` only.
- `aReset` handled **inside** `rising_edge`, not in sensitivity list.
- All state registers explicitly assigned in the `aReset` branch.
- All outputs driven in every code path (no latches).

### Arithmetic rules

- **No scientific notation** in `to_signed` or `to_unsigned` arguments.

  WRONG:   `to_signed(1.6777e4, 32)`
  CORRECT: `to_signed(16777, 32)`

- All intermediate multiply products must be `signed(63 downto 0)` before
  truncation.
- All user-visible outputs must be saturated before assignment to output port.

### Saturation helper — include in every entity

```vhdl
function sat32(v : signed(63 downto 0)) return signed is
begin
  if    v >  to_signed(2147483647, 64) then return to_signed( 2147483647, 32);
  elsif v < to_signed(-2147483648, 64) then return to_signed(-2147483648, 32);
  else  return v(31 downto 0);
  end if;
end function;
```

### Fixed-point scale reference

```
Q16.16 (FXP<+/-,32,16>): real = bits x 2^-16
  Multiply two Q16.16: 64-bit product, shift right 16.

Q8.24  (FXP<+/-,32,8>):  real = bits x 2^-24
  Gain x Q16.16: 64-bit product, shift right 24.

Q2.30  (FXP<+/-,32,2>):  real = bits x 2^-30
  Multiply by Q16.16: 64-bit product, shift right 30.
```

Every scale transition must be commented in the VHDL.

### Shift-right comment — mandatory on every multiply line

Format: `-- Q<SI>.<SFW> x Q<GI>.<GFW>, shift right <GFW>`

Examples:
```
-- Q16.16 x Q8.24, shift right 24
-- Q16.16 x Q2.30, shift right 30
-- Q16.16 x Q16.16, shift right 16
```

Shift amount = FWL of the GAIN operand = WordLength − IWL of the gain port.

### Division rule — the most important synthesis rule

**NEVER** put a runtime divide by a user-adjustable parameter inside the
Ce-gated update path. This causes Synth 8-5809 errors, RTL elaboration
failures, or timing closure failures.

Identify every `A / B` where B is a user-adjustable parameter. Define a
pre-scaled coefficient port. The LabVIEW RT side computes the coefficient
in floating-point G code and writes it to the CLIP terminal as a
fixed-point value.

| Algorithm | Naive division | Pre-scaled coefficient | FXP format |
|---|---|---|---|
| PID | Kc x dt / (Ti x 60) | `KiCoeff` | FXP<+/-,32,8> |
| PID | Kc x (Td x 60) / dt | `KdCoeff` | FXP<+/-,32,8> |
| Lowpass filter | dt / (tau + dt) | `Alpha` | FXP<+/-,32,2> |
| Biquad | bilinear transform | `B0, B1, A1, A2` | FXP<+/-,32,2> |
| Moving average | 1.0 / N | `AvgGain` | FXP<+/-,32,8> |
| Rate limiter | slew_rate x dt | `MaxDelta` | FXP<+/-,32,16> |
| State observer | Kalman gain matrix | `L0, L1, ...` | FXP<+/-,32,8> |

For any algorithm not listed: find the divide, move it to RT, send the
result as a coefficient port.

### v4.4 VHDL additions — lessons from confirmed compile failures

These rules extend v4.3. Do not remove v4.3 rules.

#### No process-local `declare` blocks

Vivado 2021.1 rejects VHDL-2008 `declare` blocks inside a process body
with Synth 8-5809 encrypted-envelope errors during RTL elaboration.

WRONG — causes Synth 8-5809:
```vhdl
process(Clk)
begin
  if rising_edge(Clk) then
    declare
      variable v_temp : signed(63 downto 0);
    begin
      v_temp := ...;
    end;
  end if;
end process;
```

CORRECT — pre-declare in architecture declarative region:
```vhdl
architecture RTL of MyEntity is
  signal v_temp : signed(63 downto 0) := (others => '0');
begin
  process(Clk)
  begin
    if rising_edge(Clk) then
      v_temp <= ...;
    end if;
  end process;
end architecture;
```

#### No integer division on non-constant signals

The `/` operator on non-constant signals infers a large combinational
divider. This fails timing and/or causes Synth 8-5809. The division rule
above forbids it; this confirms the exact Vivado mechanism.

#### Synchronous `aReset` inside `rising_edge` only

NI cRIO CLIP convention uses synchronous reset. Do NOT add `aReset` to the
process sensitivity list.

#### All intermediate signals pre-declared at architecture level

For multi-stage pipelines, declare every stage register (`s1_ep`, `s2_P`,
etc.) in the architecture declarative region. Variables local to a process
are fine but must not infer latches.

#### `Ce` must guard all state-changing assignments

Every state register, accumulator, and output register must be assigned
inside `elsif Ce = '1'`. An assignment outside Ce updates every clock cycle
regardless of the loop rate.

#### No generics on the top-level entity

Generics at the top-level CLIP entity cause NI's wrapper generation to
fail. Use fixed port widths. `std_logic_vector(31 downto 0)` for every
32-bit FXP port is the correct form.

---

## PHASE 4 — XML RULES (NI-VALIDATED SCHEMA)

Every item is mandatory. A single violation causes a LabVIEW FPGA import
error. These rules reflect the validated NI CLIP XML parser behavior on
Vivado-based cRIO targets. Rules marked **v4.5** are corrections from v4.4.

### Root skeleton — copy exactly

```xml
<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<CLIPDeclaration Name="EntityName">
  <FormatVersion>4.2</FormatVersion>
  <Description>One sentence description.</Description>
  <SupportedDeviceFamilies>Unlimited</SupportedDeviceFamilies>
  <TopLevelEntityAndArchitecture>
    <SynthesisModel>
      <Entity>EntityName</Entity>
      <Architecture>RTL</Architecture>
    </SynthesisModel>
  </TopLevelEntityAndArchitecture>
  <InterfaceList>
    <Interface Name="LabVIEW">
      <InterfaceType>LabVIEW</InterfaceType>
      <SignalList>
      </SignalList>
    </Interface>
  </InterfaceList>
  <ImplementationList>
    <Path Name="EntityName.vhd">
      <TopLevel>true</TopLevel>
    </Path>
  </ImplementationList>
</CLIPDeclaration>
```

### DataType schema rule — THE MOST IMPORTANT XML RULE (v4.5 correction)

The NI CLIP parser requires every `<Signal>` to contain a `<DataType>`
element. Inside `<DataType>`, the parser expects one of the following
**child elements** (not text content):

`<Boolean/>`, `<FXP>`, `<U8>`, `<I8>`, `<U16>`, `<I16>`, `<U32>`,
`<I32>`, `<U64>`, `<I64>`, `<Array>`

**You MUST use the child element form. Text content inside `<DataType>`
is INVALID and causes a "required tag missing" error.**

CORRECT:
```xml
<DataType>
  <Boolean/>
</DataType>
```

CORRECT:
```xml
<DataType>
  <FXP>
    <Signed>true</Signed>
    <WordLength>32</WordLength>
    <IntegerWordLength>16</IntegerWordLength>
  </FXP>
</DataType>
```

WRONG — CAUSES IMPORT FAILURE (was in v4.4 templates, corrected in v4.5):
```xml
<DataType>Boolean</DataType>
```

WRONG — CAUSES IMPORT FAILURE (missing `<Signed>`):
```xml
<DataType><FXP><WordLength>32</WordLength><IntegerWordLength>16</IntegerWordLength></FXP></DataType>
```
Without `<Signed>true</Signed>`, LabVIEW defaults the terminal to
Unsigned FXP, which silently breaks all signed VHDL arithmetic.

### Signal templates — copy exactly for each signal type

**Clock (v4.5 correction — added DataType child element):**
```xml
<Signal Name="Clk">
  <HDLName>Clk</HDLName>
  <HDLType>std_logic</HDLType>
  <Direction>ToCLIP</Direction>
  <SignalType>clock</SignalType>
  <DataType>
    <Boolean/>
  </DataType>
  <FreqInHertz>
    <Max>40000000</Max>
    <Min>1000000</Min>
  </FreqInHertz>
</Signal>
```

**Boolean (Ce, aReset, and any Boolean control):**
```xml
<Signal Name="Ce">
  <HDLName>Ce</HDLName>
  <HDLType>std_logic</HDLType>
  <Direction>ToCLIP</Direction>
  <SignalType>data</SignalType>
  <DataType>
    <Boolean/>
  </DataType>
  <UseInLabVIEWSingleCycleTimedLoop>Allowed</UseInLabVIEWSingleCycleTimedLoop>
</Signal>
```

**FXP<+/-,32,16> input (engineering values — process variable, setpoint, output):**
```xml
<Signal Name="front panel label here">
  <HDLName>VhdlPortName</HDLName>
  <HDLType>std_logic_vector(31 downto 0)</HDLType>
  <Direction>ToCLIP</Direction>
  <SignalType>data</SignalType>
  <DataType>
    <FXP>
      <Signed>true</Signed>
      <WordLength>32</WordLength>
      <IntegerWordLength>16</IntegerWordLength>
    </FXP>
  </DataType>
  <UseInLabVIEWSingleCycleTimedLoop>Allowed</UseInLabVIEWSingleCycleTimedLoop>
</Signal>
```

**FXP<+/-,32,8> input (gains, dt, pre-scaled coefficients):**
```xml
<Signal Name="front panel label here">
  <HDLName>VhdlPortName</HDLName>
  <HDLType>std_logic_vector(31 downto 0)</HDLType>
  <Direction>ToCLIP</Direction>
  <SignalType>data</SignalType>
  <DataType>
    <FXP>
      <Signed>true</Signed>
      <WordLength>32</WordLength>
      <IntegerWordLength>8</IntegerWordLength>
    </FXP>
  </DataType>
  <UseInLabVIEWSingleCycleTimedLoop>Allowed</UseInLabVIEWSingleCycleTimedLoop>
</Signal>
```

**FXP<+/-,32,2> input (normalized 0..1 coefficients):**
```xml
<Signal Name="front panel label here">
  <HDLName>VhdlPortName</HDLName>
  <HDLType>std_logic_vector(31 downto 0)</HDLType>
  <Direction>ToCLIP</Direction>
  <SignalType>data</SignalType>
  <DataType>
    <FXP>
      <Signed>true</Signed>
      <WordLength>32</WordLength>
      <IntegerWordLength>2</IntegerWordLength>
    </FXP>
  </DataType>
  <UseInLabVIEWSingleCycleTimedLoop>Allowed</UseInLabVIEWSingleCycleTimedLoop>
</Signal>
```

**Output:** same as matching input template but `Direction` is `FromCLIP`.

### Signal Name vs HDLName rule

`Name` attribute = the LabVIEW front panel label **exactly**.
Spaces and parentheses are allowed here.

`HDLName` = the VHDL port name **exactly**. PascalCase. No spaces.

Example — front panel label "proportional gain (Kc)":
```
Name="proportional gain (Kc)"
HDLName="ProportionalGainKc"
```

### HDLType exact-match rule (v4.5)

The `HDLType` value MUST be the exact VHDL type declaration string,
including the underscore and the parentheses with lowercase `downto`.

| VHDL port declaration | HDLType value |
|---|---|
| `Clk : in std_logic` | `std_logic` |
| `Data : in std_logic_vector(31 downto 0)` | `std_logic_vector(31 downto 0)` |

FORBIDDEN — any of these cause an import error:
- `std_logicvector31 downto 0` (missing underscore and parentheses)
- `std_logic_vector 31 downto 0` (missing parentheses)
- `std_logic_vector(31 DOWNTO 0)` (uppercase DOWNTO — must be lowercase)
- `SLV(31:0)` (abbreviation)

### ImplementationList rule (v4.5 correction)

The ImplementationList MUST use the `<Path>` element with `<TopLevel>`
as a **child element containing the text `true`**.

CORRECT:
```xml
<ImplementationList>
  <Path Name="EntityName.vhd">
    <TopLevel>true</TopLevel>
  </Path>
</ImplementationList>
```

FORBIDDEN — all of these cause "Current top-level file count: 0":
```xml
<!-- WRONG: TopLevel as empty attribute (was in v4.4) -->
<Path Name="EntityName.vhd" TopLevel=""/>

<!-- WRONG: TopLevel as attribute with value -->
<Path Name="EntityName.vhd" TopLevel="true"/>

<!-- WRONG: Implementation element -->
<Implementation Name="EntityName.vhd" TopLevel="true"/>

<!-- WRONG: path prefix -->
<Path Name="./ip/EntityName.vhd">
  <TopLevel>true</TopLevel>
</Path>
```

Path Name must be a **bare filename** with no path prefix, no leading
slash, and no dot-slash. The `.vhd` and `.xml` files must be in the
same directory when imported.

### FreqInHertz rule (v4.5 correction)

`<FreqInHertz>` must use `<Max>` and `<Min>` as **child elements**.
Inline text is not valid.

CORRECT:
```xml
<FreqInHertz>
  <Max>40000000</Max>
  <Min>1000000</Min>
</FreqInHertz>
```

WRONG:
```xml
<FreqInHertz><Max>40000000</Max><Min>1000000</Min></FreqInHertz>
```
(Technically the one-liner may parse, but multi-line is required for
readability and to match the validated template. Single-line combined
with other inline text is invalid.)

### Forbidden XML patterns — complete table (v4.5 updated)

| Forbidden | Import error |
|---|---|
| Missing `FormatVersion` tag | Required tag missing |
| `InterfaceType` outside `Interface` element | Required tag missing |
| `SignalType = reset` on LabVIEW interface | Import failure |
| `xmlns` attribute on `CLIPDeclaration` | Import failure |
| Text content inside `<DataType>` (`<DataType>Boolean</DataType>`) | Required tag choices missing |
| `<DataType><FXP>` missing `<Signed>` child | Terminal defaults to Unsigned FXP |
| `Direction = Input` or `Direction = Output` | Use `ToCLIP` and `FromCLIP` |
| `TopLevel` as attribute on `<Path>` | Top-level file count: 0 |
| `<Implementation>` element instead of `<Path>` | Required tag Path missing |
| Absolute path or dot-slash in `Path Name` | File not found |
| Missing `UseInLabVIEWSingleCycleTimedLoop` on data signals | Terminal unavailable in SCTL |
| XML comment inside an opening tag | XML parser error |
| Nested `Implementation/SynthesisFileList` form | Wrong schema |
| `HDLType` with uppercase `DOWNTO` | Whitespace expected / import failure |
| `HDLType` missing underscore or parentheses | Whitespace expected / import failure |
| `FormatVersion` value other than `4.2` for LV FPGA 2021 and earlier | Required tag FormatVersion |
| Missing `<DataType>` on clock signal | Required tag missing |

---

## PHASE 5 — INTEGRATION GUIDE RULES

Must contain all sections below. Never omit one.

1. What the algorithm does (two sentences).
2. List of every file generated and its purpose.
3. Build mode used and every assumed default.
4. **Terminal mapping table:**
   front panel label | VHDL port | direction | FXP format | range | notes
5. **LabVIEW FPGA import procedure:**
   - FPGA Target > Properties > Component-Level IP > add the `.xml` file
   - IP Integration Node appears in block diagram palette
   - Wire `Clk` to SCTL clock reference
   - Wire `Ce` to SCTL loop tick output (or constant TRUE for always-on)
   - Wire `aReset` to system reset Boolean
   - Wire all data terminals to controls/indicators matching FXP types
   - **IP Terminals page:** set Signed=true, WordLength=W, IntegerWordLength=IWL
     for every FXP terminal — skipping this causes 32,32 constants
6. Pipeline latency in clock cycles.
7. Ce rate vs. master clock explanation.
8. What NOT to do: algorithm-specific common mistakes.
9. Pre-compile checklist (8–12 checkboxes).

---

## PHASE 6 — TEST PLAN RULES

Cover all four categories for every algorithm.

**Logic tests:**
- `aReset` clears all internal state to zero
- `Ce = 0` holds all state unchanged for multiple cycles
- Output saturates correctly at bounds
- Boolean control inputs change behavior correctly

**Numeric tests:**
- Known input to known expected output from floating-point reference model
- Quantization error bounded by plus or minus 2 LSB
- Saturation correct at plus or minus full-scale inputs

**Algorithm-specific tests:**
- Step setpoint: PV converges to SP within expected time constant
- Plant model: y[k+1] = y[k] + (dt/tau) x (K_plant x u[k] - y[k]),
  K_plant=0.8, tau=5 s (default)
- Disturbance rejection
- Manual-to-auto bumpless transfer if algorithm has a manual mode
- Reinitialize: confirm all state registers clear

**Compile-readiness tests:**
- GHDL analysis:   `ghdl -a --std=08 EntityName.vhd`
- GHDL elaborate:  `ghdl -e --std=08 EntityName`
- XML well-formedness: confirm no forbidden patterns from Phase 4

---

## PHASE 7 — RT PRE-SCALING FILE RULES

This file is **not optional**. Every algorithm has at least one division
that must move to RT.

For each pre-scaled coefficient provide:
- Coefficient name and port name
- Formula in engineering terms
- FXP format for the port
- When to update (startup / on parameter change / every loop)
- LabVIEW RT pseudocode

**General pattern:**
```
coefficient_name = numerator / denominator
FXP format: derived from expected range and required precision
Update: whenever source parameters change

RT pseudocode:
  coeff_float = numerator_float / denominator_float
  coeff_fxp   = To Fixed-Point(coeff_float, signed=true, W=32, IWL=N)
  write coeff_fxp to CLIP terminal CoeffPortName
```

**PID-specific RT pre-scaling:**
```
KiCoeff = Kc * dt_s / (Ti_min * 60)   -- update when Kc, dt_s, or Ti_min changes
KdCoeff = Kc * (Td_min * 60) / dt_s   -- update when Kc, dt_s, or Td_min changes
Both: FXP<+/-,32,8>
```

**C .so option for high-rate loops (> 1 kHz):**
Implement pre-scaling as a shared library callable from LabVIEW RT via
Call Library Function Node:

```c
// pid_prescale.c
// Compile: gcc -O2 -shared -fPIC -o pid_prescale.so pid_prescale.c
#include <stdint.h>

// Returns KiCoeff as FXP<+/-,32,8> bit pattern (IWL=8, FWL=24)
int32_t compute_ki_coeff(float Kc, float dt_s, float Ti_min) {
    double ki = (double)Kc * (double)dt_s / ((double)Ti_min * 60.0);
    int32_t bits = (int32_t)(ki * 16777216.0);  // 2^24
    if (ki >  127.9999999) return  2147483647;
    if (ki < -128.0)       return -2147483648;
    return bits;
}

// Returns KdCoeff as FXP<+/-,32,8> bit pattern
int32_t compute_kd_coeff(float Kc, float dt_s, float Td_min) {
    double kd = (double)Kc * ((double)Td_min * 60.0) / (double)dt_s;
    int32_t bits = (int32_t)(kd * 16777216.0);
    if (kd >  127.9999999) return  2147483647;
    if (kd < -128.0)       return -2147483648;
    return bits;
}
```

---

## PHASE 8 — PREFLIGHT CHECKLIST

Verify every item before outputting any file. Fix failures first.

### VHDL checklist

- [ ] `ieee.std_logic_1164.all` and `ieee.numeric_std.all` present
- [ ] Entity name matches XML `Entity` element and `CLIPDeclaration Name`
- [ ] Architecture name is `RTL`
- [ ] Every entity port is `std_logic` or `std_logic_vector`
- [ ] No `real`, no `float`, no vendor-specific types
- [ ] No scientific notation in `to_signed` or `to_unsigned` calls
- [ ] Clocked process sensitivity list is `(Clk)` only
- [ ] `aReset` handled inside `rising_edge` (synchronous)
- [ ] `Ce` gates all state-changing assignments
- [ ] `sat32` or equivalent applied to all outputs
- [ ] All state registers assigned in `aReset` branch
- [ ] No output left undriven in any code path
- [ ] No divisions in the Ce-gated path (move to RT)
- [ ] Every multiply line has a shift-math comment
- [ ] **v4.4** No process-local `declare` blocks
- [ ] **v4.4** No generics on the top-level entity
- [ ] **v4.4** All intermediate signals pre-declared in architecture declarative region

### XML checklist (v4.5 updated)

- [ ] Root element is `CLIPDeclaration Name="EntityName"` with no `xmlns`
- [ ] `FormatVersion 4.2` is first child of root
- [ ] `InterfaceType LabVIEW` is child of `Interface` (not `InterfaceList`)
- [ ] Every VHDL port has a matching `Signal` with correct `HDLName` and `HDLType`
- [ ] `HDLType` is exactly `std_logic_vector(31 downto 0)` — underscore, parentheses, lowercase `downto`
- [ ] **v4.5** Every `Signal` has a `<DataType>` element containing a **child element** (`<Boolean/>`, `<FXP>`, etc.) — NEVER text content inside `<DataType>`
- [ ] **v4.5** Every `<FXP>` DataType contains `<Signed>true</Signed>`, `<WordLength>`, and `<IntegerWordLength>` child elements
- [ ] **v4.5** Clock signal has `<DataType><Boolean/></DataType>`
- [ ] Clock uses `<SignalType>clock</SignalType>` with `<FreqInHertz>` having `<Max>` and `<Min>` child elements
- [ ] No `SignalType reset` on any signal
- [ ] All data signals have `<UseInLabVIEWSingleCycleTimedLoop>Allowed</UseInLabVIEWSingleCycleTimedLoop>`
- [ ] Directions are `ToCLIP` or `FromCLIP` only
- [ ] **v4.5** `ImplementationList` uses `<Path Name="EntityName.vhd">` with `<TopLevel>true</TopLevel>` as a **child element** — not an attribute
- [ ] No absolute paths or dot-slash prefix in `Path Name`
- [ ] Entity name is 31 characters or fewer
- [ ] No XML comments inside opening tags

### Integration guide checklist

- [ ] Terminal mapping table complete
- [ ] LabVIEW import steps present including IP Terminals page FXP settings
- [ ] Pre-compile checklist present

---

## PHASE 9 — ERROR RECOVERY

When the user returns with Vivado logs, LabVIEW screenshots, or errors:

1. Read the error.
2. Map it to a Phase 3, 4, or 8 rule.
3. State which rule was violated and the exact fix.
4. Regenerate only the affected file.
5. Do not ask the user to edit files manually.

### Error-to-rule mapping (v4.5 updated)

| Error | Rule | Fix |
|---|---|---|
| Required tag FormatVersion missing | P4 root skeleton | Add `<FormatVersion>4.2</FormatVersion>` as first child |
| Required tag InterfaceType missing | P4 root skeleton | Move `InterfaceType` inside `Interface` element |
| Required tag DataType missing | P4 DataType rule | Add `<DataType>` with child element to every `Signal` |
| Required tag choices: Boolean, FXP, U8... | P4 v4.5 DataType | Change text content inside `<DataType>` to child element (`<Boolean/>`) |
| Terminals show as Unsigned FXP | P4 v4.5 FXP Signed | Add `<Signed>true</Signed>` inside every `<FXP>` block |
| Current top-level file count: 0 | P4 v4.5 ImplementationList | Use `<Path>` with `<TopLevel>true</TopLevel>` child element |
| Required tag Path missing | P4 v4.5 ImplementationList | Change `<Implementation>` to `<Path>` element |
| Synth 8-5809 encrypted envelope | P3 v4.4 | Check for process `declare` blocks, scientific notation, runtime division |
| RTL Elaboration failed | P3 structure | Run `ghdl -a --std=08`; check sensitivity list and pre-declared signals |
| Declaration Names shows X in CLIP dialog | P4 ImplementationList | Bare filename in Path Name; vhd and xml in same directory |
| Terminals do not appear in block diagram | P4 Signal | Use `HDLName`; check `SignalList` structure |
| Constants created as 32,32 in LabVIEW | P4 FXP tags | Verify `IntegerWordLength`; set in IP Terminals page |
| Synth 8-5809 on division line | P3 division rule | Move divide to RT; send coefficient as port |
| Synth 8-5809 on declare line | P3 v4.4 declare | Move variables to architecture declarative region |
| Terminals not usable in SCTL | P4 SCTL | Add `<UseInLabVIEWSingleCycleTimedLoop>Allowed</UseInLabVIEWSingleCycleTimedLoop>` |
| aReset has no effect | P3 process template | Confirm `aReset` inside `rising_edge`, not in sensitivity list |
| Whitespace expected / import failure | P4 v4.5 HDLType | Verify `std_logic_vector(31 downto 0)` — exact case and underscores |

---

## PHASE 10 — PYTHON PREFLIGHT CHECKER (v4.5 new)

Before delivering any generated file, the AI must mentally execute every
check in the Python preflight script below against the generated VHDL and
XML content. If any check fails, fix the violation and re-check before
delivering.

The AI must also generate `clip_preflight.py` as an additional deliverable
for every build (Quick or Full). This script allows the user to
independently verify the files after download.

```python
#!/usr/bin/env python3
"""
clip_preflight.py — CLIP_GEN v4.5 Preflight Checker
Checks a generated VHDL + XML pair against all Phase 8 rules.
Usage: python clip_preflight.py EntityName.vhd EntityName.xml
"""

import sys
import re
import xml.etree.ElementTree as ET

PASS = "✅"
FAIL = "❌"

results = []

def check(label, condition):
    status = PASS if condition else FAIL
    results.append((label, status))
    return condition

def report():
    width = max(len(r[0]) for r in results) + 2
    print(f"\n{'Check':<{width}} {'Status'}")
    print("-" * (width + 8))
    for label, status in results:
        print(f"{label:<{width}} {status}")
    fails = [r for r in results if r[1] == FAIL]
    print(f"\n{len(results) - len(fails)}/{len(results)} checks passed.")
    if fails:
        print("FAILED checks:")
        for label, _ in fails:
            print(f"  • {label}")
    return len(fails) == 0

# ── Load files ───────────────────────────────────────────────────────────────

if len(sys.argv) != 3:
    print("Usage: python clip_preflight.py EntityName.vhd EntityName.xml")
    sys.exit(1)

vhd_path, xml_path = sys.argv[1], sys.argv[2]

try:
    vhd = open(vhd_path, encoding="utf-8").read()
except FileNotFoundError:
    print(f"ERROR: VHDL file not found: {vhd_path}")
    sys.exit(1)

try:
    xml_text = open(xml_path, encoding="utf-8").read()
    root = ET.fromstring(xml_text)
except FileNotFoundError:
    print(f"ERROR: XML file not found: {xml_path}")
    sys.exit(1)
except ET.ParseError as e:
    print(f"ERROR: XML parse error: {e}")
    sys.exit(1)

# ── Derive entity name from VHDL file ────────────────────────────────────────

entity_match = re.search(r'\bentity\s+(\w+)\s+is\b', vhd, re.IGNORECASE)
entity_name = entity_match.group(1) if entity_match else ""

print(f"\nCLIP Preflight — {entity_name or '(entity not found)'}")
print("=" * 50)

# ══════════════════════════════════════════════════════════════════════════════
# VHDL CHECKS
# ══════════════════════════════════════════════════════════════════════════════

print("\n── VHDL ──")

check("ieee libs present",
      bool(re.search(r'ieee\.std_logic_1164\.all', vhd, re.IGNORECASE)) and
      bool(re.search(r'ieee\.numeric_std\.all', vhd, re.IGNORECASE)))

check("Entity name found",
      bool(entity_name))

check("Architecture name is RTL",
      bool(re.search(r'\barchitecture\s+RTL\s+of\b', vhd, re.IGNORECASE)))

# Port type check: extract entity port block only, normalize whitespace
# to prevent false positives from "in  std_logic" (double space)
def ports_ok(vhd_text):
    port_block = re.search(r'\bport\s*\((.*?)\)\s*;', vhd_text, re.DOTALL | re.IGNORECASE)
    if not port_block:
        return False
    ports_norm = re.sub(r'\s+', ' ', port_block.group(1))
    bad = re.search(r':\s*(?:in|out|inout)\s+(?!std_logic\b|std_logic_vector\b)',
                    ports_norm, re.IGNORECASE)
    return bad is None

check("Every entity port is std_logic or std_logic_vector",
      ports_ok(vhd))

check("No real, float, or vendor types",
      not bool(re.search(r'\b(real|float|ufixed|sfixed|UNISIM|VITAL)\b', vhd)))

check("No scientific notation in to_signed/to_unsigned",
      not bool(re.search(r'to_(signed|unsigned)\s*\([^)]*\d+[eE][+-]?\d+', vhd)))

check("Clocked process sensitivity list is (Clk) only",
      bool(re.search(r'process\s*\(\s*Clk\s*\)', vhd, re.IGNORECASE)))

check("aReset handled inside rising_edge",
      bool(re.search(r'rising_edge\s*\(.*?\).*?aReset', vhd, re.DOTALL | re.IGNORECASE)) and
      not bool(re.search(r'process\s*\([^)]*aReset', vhd, re.IGNORECASE)))

check("Ce gates the update correctly",
      bool(re.search(r'elsif\s+Ce\s*=\s*\'1\'', vhd, re.IGNORECASE)))

check("sat32 applied to all outputs",
      bool(re.search(r'\bsat32\b', vhd)))

check("All state registers assigned in aReset branch",
      bool(re.search(r'aReset\s*=\s*\'1\'', vhd, re.IGNORECASE)))

check("No output left undriven in any code path",
      bool(re.search(r'(others\s*=>\s*\'0\'|DataOut|Output)', vhd)))

# Division check: strip comments first, then look for runtime / inside Ce block
def no_runtime_div(vhd_text):
    ce_block = re.search(r"elsif\s+Ce\s*=\s*'1'\s+then(.*?)end\s+if",
                         vhd_text, re.DOTALL | re.IGNORECASE)
    if not ce_block:
        return True
    block = re.sub(r'--[^\n]*', '', ce_block.group(1))
    return not bool(re.search(r'\w\s*/\s*\w', block))

check("No divisions in Ce-gated path",
      no_runtime_div(vhd))

check("Every multiply has shift-math comment",
      bool(re.search(r'--.*shift right \d+', vhd, re.IGNORECASE)) or
      bool(re.search(r'--.*Q\d+\.\d+\s+x\s+Q\d+\.\d+', vhd, re.IGNORECASE)))

# ══════════════════════════════════════════════════════════════════════════════
# XML CHECKS
# ══════════════════════════════════════════════════════════════════════════════

print("\n── XML ──")

# Root element
check("Root element is CLIPDeclaration with no xmlns",
      root.tag == "CLIPDeclaration" and "xmlns" not in root.attrib)

# FormatVersion must be first child and value 4.2
first_child = list(root)[0] if len(root) else None
check("FormatVersion 4.2 is first child of root",
      first_child is not None and
      first_child.tag == "FormatVersion" and
      (first_child.text or "").strip() == "4.2")

# InterfaceType is child of Interface
iface = root.find(".//Interface[@Name='LabVIEW']")
check("InterfaceType is child of Interface",
      iface is not None and iface.find("InterfaceType") is not None)

# Entity name in XML matches VHDL
xml_entity = root.findtext(".//SynthesisModel/Entity", "").strip()
check("Entity name matches VHDL and CLIPDeclaration Name",
      entity_name != "" and
      xml_entity == entity_name and
      root.attrib.get("Name", "") == entity_name)

# Entity name <= 31 chars
check(f"Entity name is 31 characters or fewer",
      len(entity_name) <= 31)

# Collect all signals
signals = root.findall(".//SignalList/Signal")

# Every Signal has HDLName and HDLType
all_have_hdlname = all(s.find("HDLName") is not None for s in signals)
all_have_hdltype = all(s.find("HDLType") is not None for s in signals)
check("Every VHDL port has matching Signal with correct HDLName and HDLType",
      all_have_hdlname and all_have_hdltype)

# HDLType exact form for vectors
def hdltype_ok(s):
    ht = s.findtext("HDLType", "").strip()
    if ht == "std_logic":
        return True
    m = re.fullmatch(r'std_logic_vector\(\d+ downto \d+\)', ht)
    return bool(m)

check("HDLType is exactly std_logic[_vector(N downto 0)]",
      all(hdltype_ok(s) for s in signals))

# Every Signal has DataType with a child element (not text)
def has_valid_datatype(s):
    dt = s.find("DataType")
    if dt is None:
        return False
    # Must have at least one child element
    children = list(dt)
    if not children:
        return False
    # Must NOT have bare text as primary content
    text = (dt.text or "").strip()
    if text:
        return False
    return True

check("Every Signal has DataType containing a child element",
      all(has_valid_datatype(s) for s in signals))

# Every FXP DataType has Signed, WordLength, IntegerWordLength
def fxp_complete(s):
    dt = s.find("DataType")
    if dt is None:
        return True  # no DataType, caught above
    fxp = dt.find("FXP")
    if fxp is None:
        return True  # not an FXP signal
    has_signed = fxp.find("Signed") is not None
    has_wl = fxp.find("WordLength") is not None
    has_iwl = fxp.find("IntegerWordLength") is not None
    signed_true = (fxp.findtext("Signed", "").strip().lower() == "true")
    return has_signed and has_wl and has_iwl and signed_true

check("Every FXP DataType contains Signed/WordLength/IntegerWordLength",
      all(fxp_complete(s) for s in signals))

# Clock signal checks
clk_signal = next((s for s in signals
                   if s.findtext("SignalType", "").strip() == "clock"), None)

check("Clock uses SignalType clock with FreqInHertz Max/Min",
      clk_signal is not None and
      clk_signal.find("FreqInHertz") is not None and
      clk_signal.find("FreqInHertz/Max") is not None and
      clk_signal.find("FreqInHertz/Min") is not None)

check("Clock has DataType containing Boolean/",
      clk_signal is not None and
      clk_signal.find("DataType") is not None and
      clk_signal.find("DataType/Boolean") is not None)

# No SignalType reset
check("No SignalType reset",
      not any(s.findtext("SignalType", "").strip() == "reset" for s in signals))

# All data signals have UseInLabVIEWSingleCycleTimedLoop
data_signals = [s for s in signals
                if s.findtext("SignalType", "").strip() == "data"]
check("All data signals have UseInLabVIEWSingleCycleTimedLoop Allowed",
      all(s.findtext("UseInLabVIEWSingleCycleTimedLoop", "").strip() == "Allowed"
          for s in data_signals))

# Directions are ToCLIP or FromCLIP only
valid_dirs = {"ToCLIP", "FromCLIP"}
check("Directions are ToCLIP or FromCLIP only",
      all(s.findtext("Direction", "").strip() in valid_dirs for s in signals))

# ImplementationList uses Path with TopLevel child element
impl_list = root.find("ImplementationList")
path_el = impl_list.find("Path") if impl_list is not None else None
top_level_child = path_el.find("TopLevel") if path_el is not None else None

check("ImplementationList uses Path with TopLevel child element",
      path_el is not None and
      top_level_child is not None and
      (top_level_child.text or "").strip().lower() == "true")

# No absolute path or dot-slash in Path Name
path_name = path_el.attrib.get("Name", "") if path_el is not None else ""
check("No absolute paths or dot-slash in Path Name",
      not path_name.startswith("/") and
      not path_name.startswith("./") and
      not path_name.startswith("\\") and
      "/" not in path_name and
      "\\" not in path_name)

# ── Final report ──────────────────────────────────────────────────────────────

ok = report()
sys.exit(0 if ok else 1)
```

### How the AI uses this script

Before delivering files, the AI mentally traces every check in this
script against the generated content. Any check that would return `FAIL`
must be fixed before the files are presented to the user. The AI must
also include `clip_preflight.py` in the deliverable archive so the user
can re-run it after download.

---

## FINAL RULE

If this file is attached, the user wants **working files** — not
explanations, not pseudocode, not slides.

Ask five questions.
Apply defaults for anything unanswered.
Run Phase 8 preflight on every file before delivering.
Run Phase 10 mental preflight (Python checker logic) before delivering.
Fix every failing check.
Deliver all files including `clip_preflight.py`.

That is the entire job.
