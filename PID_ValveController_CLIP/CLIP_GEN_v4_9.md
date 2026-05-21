# CLIP_GEN_v4_8 — AI Instruction File for LabVIEW FPGA CLIP Node Generation

## What This File Is

This file is a machine-readable instruction set for an AI assistant.
When a user attaches this file to a prompt, the AI follows every rule below
and generates a complete, compile-ready LabVIEW FPGA CLIP package without
requiring the user to understand HDL, fixed-point arithmetic, NI XML schemas,
or Vivado synthesis rules.

**The user answers five questions. The AI does the rest.**

**v4.8 changes from v4.7:** All v4.7 rules kept verbatim. One new
VHDL integer-literal rule added to Phase 3, Phase 8, Phase 9, and the
Python preflight: **never emit an integer literal outside the range
-2,147,483,648 to +2,147,483,647**. Vivado 2021.1 treats unbased decimal
literals as type `integer` with this range; any larger value causes
VRFC 10-985 ("literal ... exceeds maximum integer value"). This broke the
v4.7 attempt to precompute saturation thresholds like
`2147483647 * 2^24` = `36028797002186752`. v4.8 replaces those with
shift-based expressions (e.g. `shift_left(to_signed(2147483647, 64), 24)`)
and explicitly forbids large integer literals. Phase 3 arithmetic rules
updated with the integer-range rule and safe patterns for 64-bit
constants. Phase 8 checklist updated with a new item. Phase 9 error
mapping updated with VRFC 10-985. Phase 10 preflight updated to scan all
integer literals and fail on any value larger than 2,147,483,647.



**v4.9 changes from v4.8:** All v4.8 rules kept verbatim. Two additional rules are added based on NI compile behavior: - **Envelope-safe coding rule (Phase 3, 8, 9, 10):** CLIP VHDL must use only a conservative subset of constructs that NI’s encrypted wrapper can safely analyze. This forbids architecture-level functions, process-local `declare` blocks, signal `:=` initializers, `sra`/`srl`, and any 64-bit product-domain saturation constants. These patterns have all contributed to Synth 8-5809 “Error generated from encrypted envelope” in NI FPGA compiles.[file:39] - **Envelope-safe saturation rule (Phase 3, 8, 9, 10):** Saturation must be implemented either via the standard `sat32` helper with 32-bit bounds or via inlined `if/elsif` that compares a sign-extended slice of the product to those same 32-bit bounds. Pre-scaled 64-bit decimal saturation literals like `36028797002186752` and `36028797018963968` must never appear in CLIP VHDL. Phase 10 preflight is updated to explicitly reject these values.[file:38]

---

## PHASE 0 — ACTIVATION

When this file is attached to any prompt, output **exactly** this message
and nothing else until the user responds:

> I have loaded the CLIP generation instruction set (v4.8). I will generate
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
>    
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

| Item                                 | Default                                                             |
| ------------------------------------ | ------------------------------------------------------------------- |
| Target FPGA                          | NI cRIO-class Kintex-7, part xc7k70tfbg676-1                        |
| Master clock                         | 40 MHz, 25 ns period                                                |
| VHDL standard                        | VHDL-2008; use `--std=08` for GHDL                                  |
| Entity port types                    | `std_logic` and `std_logic_vector` only                             |
| Arithmetic library                   | `ieee.numeric_std` only                                             |
| FXP for engineering values           | FXP<+/-,32,16> signed, IWL=16, FWL=16, LSB=1.526e-5                 |
| FXP for gains and time constants     | FXP<+/-,32,8> signed, IWL=8, FWL=24, LSB=5.96e-8                    |
| FXP for normalized coefficients 0..1 | FXP<+/-,32,2> signed, IWL=2, FWL=30, LSB=9.31e-10                   |
| Boolean terminals                    | `std_logic` in VHDL, `<Boolean/>` child element in XML              |
| Reset                                | `aReset`, active-high, **synchronous** (inside `rising_edge`)       |
| Enable                               | `Ce`, active-high, gates the algorithm update                       |
| Pipeline depth                       | Minimum to close 40 MHz timing; documented in guide                 |
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

- **Integer literal range (v4.8 critical rule)** — all unbased decimal
  integer literals must be within the VHDL `integer` range supported by
  Vivado 2021.1: -2,147,483,648 to +2,147,483,647. Any literal outside
  this range triggers VRFC 10-985:
  
  ```
  ERROR: [VRFC 10-985] literal 36028797002186752 exceeds maximum integer value
  ```
  
  **FORBIDDEN:**
  
  ```vhdl
  -- WRONG: literal too large for type integer
  constant C_SAT_POS : signed(63 downto 0) :=
    to_signed(36028797002186752, 64);  -- FORBIDDEN (v4.7 bug)
  ```
  
  **CORRECT patterns:**
  
  ```vhdl
  -- Use smaller integer inside to_signed, then shift left
  constant C_SAT_POS : signed(63 downto 0) :=
    shift_left(to_signed(2147483647, 64), 24);  -- 2147483647 * 2^24
  
  constant C_SAT_NEG : signed(63 downto 0) :=
    shift_left(to_signed(-2147483648, 64), 24); -- -2147483648 * 2^24
  ```
  
  or, preferably, avoid scaled saturation constants entirely and use the
  `sat32` helper on the shifted product:
  
  ```vhdl
  -- Q16.16 x Q8.24 product in s_Product (64-bit)
  s_Result <= sat32(resize(s_Product(63 downto 24), 64));
  ```
  
  **Rule:** never emit a decimal integer literal with absolute value
  greater than 2,147,483,647 in CLIP VHDL.

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

### Shift operator rule — `sra` is FORBIDDEN in CLIP VHDL (v4.7 critical rule)

**VRFC 10-724: found '0' definitions of operator "sra"**

Vivado 2021.1 (and all NI FPGA compile chains based on Vivado) reject the
`sra` (shift right arithmetic) operator on `signed` types during the
`xelab` elaboration stage. This manifests at the LabVIEW FPGA "Check
Syntax" step, not at XML import. The entity parses successfully but
architecture elaboration fails.

**FORBIDDEN — causes VRFC 10-724 at syntax check:**

```vhdl
s_Result <= sat32(s_Product sra 24);      -- WRONG: sra not resolved by Vivado
s_Result <= sat32(s_Accum   sra 16);      -- WRONG
```

**CORRECT — explicit bit-slice idiom, synthesizes cleanly in Vivado 2021.1:**

```vhdl
-- Arithmetic shift right by SHIFT = take bits (63 downto SHIFT),
-- then resize back to 64 bits for sat32.
-- shift right 24 (gain is FXP<+/-,32,8>, FWL=24):
s_Result <= sat32(resize(s_Product(63 downto 24), 64));
-- shift right 16 (gain is FXP<+/-,32,16>, FWL=16):
s_Result <= sat32(resize(s_Product(63 downto 16), 64));
-- shift right 30 (gain is FXP<+/-,32,2>, FWL=30):
s_Result <= sat32(resize(s_Product(63 downto 30), 64));
```

**Why this is mathematically identical to sra:**
`sra N` on a signed value discards the N LSBs and sign-extends.
`slice(63 downto N)` extracts those same bits; `resize(...,64)` sign-extends.
Result: bit-for-bit identical output, zero synthesis errors.

**Shift-right to bit-slice lookup table:**

| Gain FXP format | FWL = shift amount | Correct bit-slice expression          |
| --------------- | ------------------ | ------------------------------------- |
| FXP<+/-,32,8>   | 24                 | `resize(s_Product(63 downto 24), 64)` |
| FXP<+/-,32,16>  | 16                 | `resize(s_Product(63 downto 16), 64)` |
| FXP<+/-,32,2>   | 30                 | `resize(s_Product(63 downto 30), 64)` |
| FXP<+/-,32,4>   | 28                 | `resize(s_Product(63 downto 28), 64)` |

**Preflight rule:** Before delivering any VHDL file, search for `sra` and
`srl` anywhere in the source. Zero occurrences required. Replace every
instance with the bit-slice idiom above.

---

### Architecture-level function and signal initializer rules (v4.7 Synth 8-5809)

**Synth 8-5809: Error generated from encrypted envelope**

NI FPGA wraps every CLIP entity in an encrypted Vivado IP envelope at
compile time. When Vivado synthesizes this wrapper, two VHDL constructs
cause Synth 8-5809 failures that cannot be debugged from the user side
(because the error originates inside NI's encrypted files):

**FORBIDDEN 1 — Architecture-level function declarations:**

```vhdl
-- WRONG: function in architecture declarative region
architecture RTL of MyEntity is
    function sat32(v : signed(63 downto 0)) return signed is  -- FORBIDDEN
    begin ...
    end function;
```

NI's encrypted wrapper cannot bind to locally-declared functions.
The function compiles fine in isolation (GHDL passes) but fails at
Synth 8-5809 during NI's full compile.

**CORRECT — Inline the logic explicitly:**

```vhdl
-- RIGHT: inline saturation as if/elsif — no function needed
if s_Product > C_SAT_POS then
    s_Result <= to_signed(2147483647, 32);
elsif s_Product < C_SAT_NEG then
    s_Result <= to_signed(-2147483648, 32);
else
    s_Result <= s_Product(55 downto 24);  -- shift right 24, take 32 LSBs
end if;
```

**FORBIDDEN 2 — Signal initial values with `:=`:**

```vhdl
-- WRONG: := initializers on signals in architecture declarative region
signal s_Accum    : signed(36 downto 0) := (others => '0');  -- FORBIDDEN
signal s_Product  : signed(63 downto 0) := (others => '0');  -- FORBIDDEN
```

Vivado synthesis ignores `:=` initial values on flip-flops (it cannot
program them). The NI encrypted wrapper's elaboration fails when the
inferred reset state mismatches the initial value declaration.

**CORRECT — Remove all `:=` initializers; use only the aReset branch:**

```vhdl
-- RIGHT: no initializer; aReset branch sets everything to zero
signal s_Accum   : signed(36 downto 0);  -- no :=
signal s_Product : signed(63 downto 0);  -- no :=
...
if aReset = '1' then
    s_Accum   <= (others => '0');
    s_Product <= (others => '0');
    ...
```

**Saturation threshold constants — safe pattern:**

Use pre-computed constants for saturation bounds. Constants with `:=` are
allowed (they are synthesis-time values, not flip-flop initial values):

```vhdl
-- CORRECT: constants with to_signed are fine
-- For Q16.16 x Q8.24 product (shift right 24):
-- C_SAT_POS = 2147483647 * 2^24 = 36028797002186752
-- C_SAT_NEG = -2147483648 * 2^24 = -36028797018963968
constant C_SAT_POS : signed(63 downto 0) :=
    to_signed(36028797002186752,  64);
constant C_SAT_NEG : signed(63 downto 0) :=
    to_signed(-36028797018963968, 64);
```

**Shift-right to saturation constant lookup:**

| Gain FXP format | FWL shift | C_SAT_POS                            | C_SAT_NEG                             |
| --------------- | --------- | ------------------------------------ | ------------------------------------- |
| FXP<+/-,32,8>   | 24        | `to_signed(36028797002186752, 64)`   | `to_signed(-36028797018963968, 64)`   |
| FXP<+/-,32,16>  | 16        | `to_signed(140737488355328, 64)`     | `to_signed(-140737488388096, 64)`     |
| FXP<+/-,32,2>   | 30        | `to_signed(2305843007066210304, 64)` | `to_signed(-2305843009213693952, 64)` |

**Rule summary for Phase 8:**

- Scan VHDL for any `function` keyword in the architecture declarative region → zero allowed.
- Scan all `signal` declarations for `:=` → zero allowed on signal declarations.
- Constants with `:=` are allowed.
- All initialization must be in the `aReset = '1'` branch only.

---

### Division rule — the most important synthesis rule

**NEVER** put a runtime divide by a user-adjustable parameter inside the
Ce-gated update path. This causes Synth 8-5809 errors, RTL elaboration
failures, or timing closure failures.

Identify every `A / B` where B is a user-adjustable parameter. Define a
pre-scaled coefficient port. The LabVIEW RT side computes the coefficient
in floating-point G code and writes it to the CLIP terminal as a
fixed-point value.

| Algorithm      | Naive division      | Pre-scaled coefficient | FXP format     |
| -------------- | ------------------- | ---------------------- | -------------- |
| PID            | Kc x dt / (Ti x 60) | `KiCoeff`              | FXP<+/-,32,8>  |
| PID            | Kc x (Td x 60) / dt | `KdCoeff`              | FXP<+/-,32,8>  |
| Lowpass filter | dt / (tau + dt)     | `Alpha`                | FXP<+/-,32,2>  |
| Biquad         | bilinear transform  | `B0, B1, A1, A2`       | FXP<+/-,32,2>  |
| Moving average | 1.0 / N             | `AvgGain`              | FXP<+/-,32,8>  |
| Rate limiter   | slew_rate x dt      | `MaxDelta`             | FXP<+/-,32,16> |
| State observer | Kalman gain matrix  | `L0, L1, ...`          | FXP<+/-,32,8>  |

For any algorithm not listed: find the divide, move it to RT, send the
result as a coefficient port.

### v4.4 VHDL additions — lessons from confirmed compile failures

#### Synthesis attributes — keep the CLIP RTL hierarchy (v4.7 recommendation)

Vivado sometimes optimizes away or merges registers that NI's encrypted
wrapper expects to see as distinct leaf instances. When this happens, the
error surfaces as Synth 8-5809 reported against NI-generated files (for
example `MovingAverageNiFpgaAG_...vhd`, `toplevel_gen.vhd`) even though the
user VHDL passes syntax and local GHDL checks.

To stabilize the CLIP node and keep its internal hierarchy visible to the NI
wrapper, you **may** apply conservative synthesis attributes. These
attributes are optional and should only be added **after** all other v4.7
rules (no functions, no `:=` initializers, no `sra`, correct XML) are
satisfied.

Rules:

- Do **not** attach attributes to the CLIP entity ports.
- Declare attributes in the architecture declarative region.
- Apply attributes only to internal registers and the architecture.
- Use only standard Xilinx attributes: `keep`, `dont_touch`, and
  `keep_hierarchy`.

Recommended pattern:

```vhdl
architecture RTL of MyEntity is

  attribute keep           : string;
  attribute dont_touch     : string;
  attribute keep_hierarchy : string;

  signal s_Accum   : signed(36 downto 0);
  signal s_Product : signed(63 downto 0);
  signal s_Result  : signed(31 downto 0);

  attribute keep       of s_Accum   : signal is "true";
  attribute keep       of s_Product : signal is "true";
  attribute keep       of s_Result  : signal is "true";

  attribute dont_touch of s_Accum   : signal is "true";
  attribute dont_touch of s_Product : signal is "true";
  attribute dont_touch of s_Result  : signal is "true";

  attribute keep_hierarchy of RTL   : architecture is "yes";
```

When to use attributes:

- Only after a clean design still produces Synth 8-5809 in NI's
  encrypted wrapper.
- Prefer `keep` first; add `dont_touch` only if necessary.
- Target attributes at critical state (accumulators, state machines,
  main outputs), not every signal.

Phase 8 checklist additions:

- [ ] **v4.7** If synthesis attributes are used, they follow this pattern:
  
      declared in architecture, attached only to internal signals and
      architecture, never to entity ports.
- [ ] **v4.7** No vendor-specific attributes other than `keep`,
  
      `dont_touch`, and `keep_hierarchy` are used.

Phase 9 error mapping addition:

- Error: Synth 8-5809 on NI wrapper VHDL after all v4.7 rules pass.
  Rule: v4.7 synthesis attributes.
  Fix: add `keep`/`dont_touch` on key state registers and
  `keep_hierarchy` on the CLIP architecture, then re-run compile.

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



#### v4.9 Envelope-safe coding for NI encrypted wrapper NI’s CLIP wrapper injects your entity into a protected Vivado design and then analyzes it again during full `synth_design`. Some constructs that are legal in standalone Vivado/GHDL still cause **Synth 8-5809** when the wrapper traverses them.[file:39] v4.9 defines a conservative envelope-safe subset for CLIP VHDL: **Allowed:** - Exactly one synchronous process with the template shown above. - Architecture-level signals only: `signed`, `unsigned`, `std_logic`, `std_logic_vector`. - `if/elsif/else`, simple `for` loops with static bounds. - `to_signed`, `resize`, `shift_left`, `shift_right` on `signed`/`unsigned` with constant shift amounts. - Saturation implemented via the **sat32 helper** or via inlined `if/elsif` using 32-bit bounds as defined below.[file:39] **Forbidden (v4.9 envelope-safe rule):** These patterns have contributed to Synth 8-5809 “Error generated from encrypted envelope” when NI wraps the CLIP: - Any architecture-level **function** or **procedure** declaration: ```vhdl architecture RTL of MyEntity is function sat32(v : signed(63 downto 0)) return signed is -- FORBIDDEN begin ... end function; ``` - Any `signal ... := ...;` initializer in the architecture declarative region. Signals must be declared without `:=`; all reset behavior belongs in the `aReset` branch. ```vhdl -- FORBIDDEN: signal s_Accum : signed(36 downto 0) := (others => '0'); signal s_Product : signed(63 downto 0) := (others => '0'); ``` - Any process-local `declare` blocks. - Any use of `sra` or `srl` operators on `signed`/`unsigned`. - Any pre-scaled 64-bit saturation constants, especially: ```vhdl -- FORBIDDEN product-domain constants: -- 36028797002186752 (0x007FFFFFFF000000) -- 36028797018963968 (0xFF80000000000000) ```[file:38] **Envelope-safe saturation patterns (v4.9)** v4.9 permits only two saturation styles: 1. **sat32 helper**: ```vhdl function sat32(v : signed(63 downto 0)) return signed is begin if v > to_signed(2147483647, 64) then return to_signed( 2147483647, 32); elsif v < to_signed(-2147483648, 64) then return to_signed(-2147483648, 32); else return v(31 downto 0); end if; end function; -- after multiply: Q16.16 x Q8.24 => shift right 24 s_Result <= sat32(resize(s_Product(63 downto 24), 64)); ``` 2. **Inlined `if/elsif` using only 32‑bit bounds**: ```vhdl -- Q16.16 x Q8.24, shift right 24 via s_Product(63 downto 24) if resize(s_Product(63 downto 24), 64) > to_signed(2147483647, 64) then s_Result <= to_signed(2147483647, 32); elsif resize(s_Product(63 downto 24), 64) < to_signed(-2147483648, 64) then s_Result <= to_signed(-2147483648, 32); else s_Result <= s_Product(55 downto 24); -- lower 32 bits of shifted value end if; ``` No other saturation pattern is permitted in v4.9 CLIP VHDL.[file:38] ### Saturation helper — include in every entity ```vhdl function sat32(v : signed(63 downto 0)) return signed is begin if v > to_signed(2147483647, 64) then return to_signed( 2147483647, 32); elsif v < to_signed(-2147483648, 64) then return to_signed(-2147483648, 32); else return v(31 downto 0); end if; end function; ```[file:41] ### Fixed-point scale reference ``` Q16.16 (FXP<+/-,32,16>): real = bits x 2^-16 Multiply two Q16.16: 64-bit product, shift right 16. Q8.24 (FXP<+/-,32,8>): real = bits x 2^-24 Gain x Q16.16: 64-bit product, shift right 24. Q2.30 (FXP<+/-,32,2>): real = bits x 2^-30 Multiply by Q16.16: 64-bit product, shift right 30. ``` Every scale transition must be commented in the VHDL.[file:41] ### Shift-right comment — mandatory on every multiply line Format: `-- Q<SI>.<SFW> x Q<GI>.<GFW>, shift right <GFW>` Examples: ``` -- Q16.16 x Q8.24, shift right 24 -- Q16.16 x Q2.30, shift right 30 -- Q16.16 x Q16.16, shift right 16 ``` Shift amount = FWL of the GAIN operand = WordLength − IWL of the gain port.[file:41]

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

`Name` must use only allowed characters — no parentheses, no `%`.
Use `pct` for percent, remove parentheses from units.

```xml
<Signal Name="Data In 0 to 100 pct">
  <HDLName>DataIn</HDLName>
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

`Name` must not contain parentheses. Replace `(Kp)` → `Kp`.

```xml
<Signal Name="Proportional Gain Kp">
  <HDLName>ProportionalGainKp</HDLName>
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

`Name` must not contain parentheses or slashes. Use plain words only.

```xml
<Signal Name="Filter Alpha">
  <HDLName>FilterAlpha</HDLName>
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

### Signal Name attribute — character restrictions (v4.6 critical rule)

**THE MOST COMMON IMPORT ERROR.** The NI CLIP parser enforces strict
character rules on every `Name` attribute throughout the XML file.
This applies to `<CLIPDeclaration Name="">`, `<Interface Name="">`,
`<Signal Name="">`, and `<Path Name="">`.

**Allowed characters in any Name attribute:**

- English letters (A–Z, a–z)
- Digits (0–9)
- Space (` `)
- Underscore (`_`)
- Dash (`-`)
- Period (`.`)

**FORBIDDEN characters — cause "unsupported characters" import error:**

- Parentheses: `(` `)` — even for units like `(Kp)` or `(0-100%)`
- Percent sign: `%`
- Slash: `/`
- Angle brackets: `<` `>`
- Plus or minus in combined notation: `+/-`
- Ampersand: `&`
- Any other special character not in the allowed list

**Signal Name sanitization procedure:**

Before writing any `Name` attribute, apply these transformations:

| Original label fragment | Safe replacement             |
| ----------------------- | ---------------------------- |
| `(Kp)`                  | `Kp` or `_Kp`                |
| `(0-100%)`              | `0 to 100 pct`               |
| `(%)`                   | `pct`                        |
| `+/-`                   | `Signed`                     |
| `(Ti)`                  | `Ti`                         |
| `(Td)`                  | `Td`                         |
| `1/N`                   | `1 over N` or `Reciprocal N` |
| `dt_s`                  | `dt s` or `dt sec`           |

**Name vs HDLName — two separate fields with different rules:**

`Name` attribute = sanitized human-readable label.

- Must pass the character rule above.
- Used as the terminal label in the LabVIEW block diagram.
- Spaces and dashes and underscores allowed; parentheses and `%` forbidden.

`HDLName` child element = the VHDL port name **exactly**.

- PascalCase. No spaces. No special characters at all.
- Must match the entity port name character-for-character.

Example — engineering label "Proportional Gain (Kp)":

```
Name="Proportional Gain Kp"        ← parentheses removed
HDLName="ProportionalGainKp"       ← PascalCase, no spaces
```

Example — engineering label "Data In (0-100%)":

```
Name="Data In 0 to 100 pct"        ← parens and % removed
HDLName="DataIn"                   ← PascalCase
```

Example — engineering label "Avg Gain (1/N)":

```
Name="Avg Gain 1 over N"           ← parens and slash removed
HDLName="AvgGain"
```

**Preflight check:** Before writing the XML file, scan every `Name`
attribute value with this regex. It must return no matches (zero hits = pass):

```python
import re
forbidden = re.compile(r'[()%/<>&+]')
# Test: forbidden.search(name_value) must be None for every Name attribute
```

### HDLType exact-match rule (v4.5)

The `HDLType` value MUST be the exact VHDL type declaration string,
including the underscore and the parentheses with lowercase `downto`.

| VHDL port declaration                     | HDLType value                   |
| ----------------------------------------- | ------------------------------- |
| `Clk : in std_logic`                      | `std_logic`                     |
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

| Forbidden                                                           | Import error                             |
| ------------------------------------------------------------------- | ---------------------------------------- |
| Missing `FormatVersion` tag                                         | Required tag missing                     |
| `InterfaceType` outside `Interface` element                         | Required tag missing                     |
| `SignalType = reset` on LabVIEW interface                           | Import failure                           |
| `xmlns` attribute on `CLIPDeclaration`                              | Import failure                           |
| Text content inside `<DataType>` (`<DataType>Boolean</DataType>`)   | Required tag choices missing             |
| `<DataType><FXP>` missing `<Signed>` child                          | Terminal defaults to Unsigned FXP        |
| `Direction = Input` or `Direction = Output`                         | Use `ToCLIP` and `FromCLIP`              |
| `TopLevel` as attribute on `<Path>`                                 | Top-level file count: 0                  |
| `<Implementation>` element instead of `<Path>`                      | Required tag Path missing                |
| Absolute path or dot-slash in `Path Name`                           | File not found                           |
| Missing `UseInLabVIEWSingleCycleTimedLoop` on data signals          | Terminal unavailable in SCTL             |
| XML comment inside an opening tag                                   | XML parser error                         |
| Nested `Implementation/SynthesisFileList` form                      | Wrong schema                             |
| `HDLType` with uppercase `DOWNTO`                                   | Whitespace expected / import failure     |
| **v4.6** `Signal Name` contains `()`, `%`, `/`, `<>`, `+/-`         | Unsupported characters in name attribute |
| **v4.6** `CLIPDeclaration Name` contains special chars              | Unsupported characters in name attribute |
| `HDLType` missing underscore or parentheses                         | Whitespace expected / import failure     |
| `FormatVersion` value other than `4.2` for LV FPGA 2021 and earlier | Required tag FormatVersion               |
| Missing `<DataType>` on clock signal                                | Required tag missing                     |

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
- [ ] **v4.7** Zero occurrences of `sra` or `srl` in VHDL — use `resize(product(63 downto SHIFT), 64)` inside `sat32` instead
- [ ] Every multiply line has a shift-math comment
- [ ] **v4.8** No integer literal has absolute value greater than 2147483647 (VRFC 10-985)
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
- [ ] **v4.6** Every `Name` attribute (CLIPDeclaration, Interface, Signal, Path) contains only letters, digits, spaces, underscores, dashes, periods — no `()`, `%`, `/`, `<>`, `+/-`
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

| Error                                                      | Rule                              | Fix                                                                                                                                                                                      |
| ---------------------------------------------------------- | --------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Required tag FormatVersion missing                         | P4 root skeleton                  | Add `<FormatVersion>4.2</FormatVersion>` as first child                                                                                                                                  |
| Required tag InterfaceType missing                         | P4 root skeleton                  | Move `InterfaceType` inside `Interface` element                                                                                                                                          |
| Required tag DataType missing                              | P4 DataType rule                  | Add `<DataType>` with child element to every `Signal`                                                                                                                                    |
| Required tag choices: Boolean, FXP, U8...                  | P4 v4.5 DataType                  | Change text content inside `<DataType>` to child element (`<Boolean/>`)                                                                                                                  |
| Terminals show as Unsigned FXP                             | P4 v4.5 FXP Signed                | Add `<Signed>true</Signed>` inside every `<FXP>` block                                                                                                                                   |
| Current top-level file count: 0                            | P4 v4.5 ImplementationList        | Use `<Path>` with `<TopLevel>true</TopLevel>` child element                                                                                                                              |
| Required tag Path missing                                  | P4 v4.5 ImplementationList        | Change `<Implementation>` to `<Path>` element                                                                                                                                            |
| Synth 8-5809 encrypted envelope                            | P3 v4.4                           | Check for process `declare` blocks, scientific notation, runtime division                                                                                                                |
| RTL Elaboration failed                                     | P3 structure                      | Run `ghdl -a --std=08`; check sensitivity list and pre-declared signals                                                                                                                  |
| Declaration Names shows X in CLIP dialog                   | P4 ImplementationList             | Bare filename in Path Name; vhd and xml in same directory                                                                                                                                |
| Terminals do not appear in block diagram                   | P4 Signal                         | Use `HDLName`; check `SignalList` structure                                                                                                                                              |
| Constants created as 32,32 in LabVIEW                      | P4 FXP tags                       | Verify `IntegerWordLength`; set in IP Terminals page                                                                                                                                     |
| Synth 8-5809 on division line                              | P3 division rule                  | Move divide to RT; send coefficient as port                                                                                                                                              |
| Synth 8-5809 on declare line                               | P3 v4.4 declare                   | Move variables to architecture declarative region                                                                                                                                        |
| Terminals not usable in SCTL                               | P4 SCTL                           | Add `<UseInLabVIEWSingleCycleTimedLoop>Allowed</UseInLabVIEWSingleCycleTimedLoop>`                                                                                                       |
| aReset has no effect                                       | P3 process template               | Confirm `aReset` inside `rising_edge`, not in sensitivity list                                                                                                                           |
| Whitespace expected / import failure                       | P4 v4.5 HDLType                   | Verify `std_logic_vector(31 downto 0)` — exact case and underscores                                                                                                                      |
| **VRFC 10-724: found 0 definitions of operator "sra"**     | **P3 v4.7 Shift operator**        | Replace every `x sra N` with `resize(x(63 downto N), 64)` inside sat32 call                                                                                                              |
| **Unsupported characters in name attribute**               | **P4 v4.6 Signal Name**           | Remove `()`, `%`, `/`, `<>`, `+/-` from every `Name` attribute; replace `(Kp)` → `Kp`, `(0-100%)` → `0 to 100 pct`, `1/N` → `1 over N`                                                   |
| **VRFC 10-985: literal ... exceeds maximum integer value** | **P3 v4.8 Integer literal range** | Replace large decimal literal with a shift-based expression such as `shift_left(to_signed(2147483647, 64), 24)`, or revert to using `sat32` with 32-bit bounds; never emit literals with |

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

# Name attribute character check (v4.6)
import re as _re
_name_forbidden = _re.compile(r'[()%/<>&]|\+/-')

def name_attr_ok(attrib_val):
    return _name_forbidden.search(attrib_val) is None

# Root element
check("Root element is CLIPDeclaration with no xmlns",
      root.tag == "CLIPDeclaration" and "xmlns" not in root.attrib)

# FormatVersion must be first child and value 4.2
first_child = list(root)[0] if len(root) else None
# v4.6: validate Name attributes on CLIPDeclaration, Interface, Signal, Path
def all_names_valid(root_el):
    bad = []
    # CLIPDeclaration Name
    n = root_el.attrib.get("Name", "")
    if n and not name_attr_ok(n):
        bad.append(f"CLIPDeclaration Name: {n!r}")
    # Interface Name
    for iface in root_el.findall(".//Interface"):
        n = iface.attrib.get("Name", "")
        if n and not name_attr_ok(n):
            bad.append(f"Interface Name: {n!r}")
    # Signal Name
    for sig in root_el.findall(".//Signal"):
        n = sig.attrib.get("Name", "")
        if n and not name_attr_ok(n):
            bad.append(f"Signal Name: {n!r}")
    # Path Name
    for p in root_el.findall(".//Path"):
        n = p.attrib.get("Name", "")
        if n and not name_attr_ok(n):
            bad.append(f"Path Name: {n!r}")
    if bad:
        print("  Name violations:", bad)
    return len(bad) == 0

check("Every Name attribute has only allowed characters (no ()%/<>&+/-)",
      all_names_valid(root))

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

## PHASE 11 — MANDATORY PREFLIGHT SELF-RUN AND CHECKLIST DISPLAY

This phase is mandatory on every build. After generating all files and
before delivering them to the user, the AI must:

### Step 1 — Run clip_preflight.py

Execute the preflight Python script against the generated `.vhd` and
`.xml` files. This is not optional and cannot be skipped.

```
python clip_preflight.py EntityName.vhd EntityName.xml
```

If running in a sandboxed environment (e.g., Perplexity AI, ChatGPT code
interpreter, Claude artifacts), use the `execute_code` or equivalent tool
to run the script and capture its output.

### Step 2 — Display the checklist output

Present the complete preflight output table to the user in your response,
formatted exactly as the script produces it:

```
CLIP Preflight v4.7 — EntityName
==================================================

── VHDL ──
── XML ──

Check                                                  Status
--------------------------------------------------------------
ieee libs present                                      ✅
Entity name found                                      ✅
...
Every Name attribute has only allowed characters ...   ✅
...
No sra or srl operators in VHDL                        ✅

32/32 checks passed.
```

### Step 3 — Fix before delivering

If any check shows ❌:

1. Identify the failing rule from Phase 3, Phase 4, or Phase 8.
2. Fix the affected file.
3. Re-run clip_preflight.py.
4. Repeat until 32/32 ✅.
5. Only then deliver the files to the user.

**Do not deliver files with a failing preflight.**

### Step 4 — Confirm in your response

After delivering files, include one line in your response:

> Phase 11 Preflight: **32/32 ✅** — all files passed before delivery.

If the environment cannot run Python, perform the Phase 11 checks
mentally by tracing through every check in the script against the
generated code, and state:

> Phase 11 Preflight: **mental trace complete, 32/32 ✅**.

---

## FINAL RULE

If this file is attached, the user wants **working files** — not
explanations, not pseudocode, not slides.

Ask five questions.
Apply defaults for anything unanswered.
Run Phase 8 preflight on every file before delivering.
**v4.6: Before writing any XML, sanitize every Name attribute.**
Remove `()`, `%`, `/`, `<>`, `+/-` from every Signal Name.
**v4.7: Never use `sra` or `srl` in VHDL.**
Use `resize(product(63 downto SHIFT), 64)` inside `sat32` for every shift.
**v4.7: Run Phase 11 — execute clip_preflight.py and show the checklist**
before delivering. Fix every ❌ before delivering.
Deliver all files including `clip_preflight.py`.

That is the entire job.
