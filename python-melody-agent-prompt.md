# AI Coding-Agent Prompt: LabVIEW Melody Python Module

## Purpose

Use the following prompt with any AI coding agent to create or recreate the Python module used by a LabVIEW VI for melody generation.

The generated module must be compatible with the LabVIEW Python Node and must return a 10-second mono audio waveform plus its sample rate. The LabVIEW VI will use the waveform for PC sound-card playback and for a complete-waveform STFT/spectrogram analysis.

---

## Copy-and-Paste Prompt

```text
You are an expert Python developer familiar with LabVIEW Python Node integration, digital audio waveform generation, and strict positional function interfaces.

Create a complete standalone Python module named:

    play_melody.py

The module will be called from LabVIEW through the LabVIEW Python Node.

==================================================
1. REQUIRED PUBLIC FUNCTION
==================================================

Implement exactly this public function:

    play_melody(melody)

Do not rename the function.
Do not add required parameters.
Do not reorder parameters.
Do not use default argument values.
LabVIEW will call the function positionally with exactly one input.

The function input is:

    melody

The function must accept the LabVIEW Melody Style Enum after it has been converted to its underlying I32 value.

For standalone Python testing, the function may also accept the style name as a string.

==================================================
2. LABVIEW ENUM MAPPING
==================================================

The LabVIEW Enum is named:

    Melody Style.ctl

The Enum items must map exactly as follows:

    0 = Classical
    1 = Jazz
    2 = Blues
    3 = Electronic
    4 = Folk

The Python function must use the numeric values as the primary interface.

If the input is an integer:

    0 selects Classical
    1 selects Jazz
    2 selects Blues
    3 selects Electronic
    4 selects Folk

If the input is a string, accept these case-insensitive names:

    Classical
    Jazz
    Blues
    Electronic
    Folk

If the input is invalid or outside the range 0 through 4, select Classical as a safe fallback. Do not return an empty waveform for an invalid selection.

==================================================
3. REQUIRED OUTPUTS
==================================================

Return exactly two values in this order:

    return waveform, sample_rate

Output 1:

    waveform

Requirements:

- Must be a plain Python list.
- Every element must be a native Python float.
- Do not return a NumPy array.
- Do not return a tuple containing the waveform as the only output.
- Do not return a generator, iterator, dictionary, or custom object.
- The waveform must be mono.
- The waveform must contain exactly 441,000 samples.

Output 2:

    sample_rate

Requirements:

- Must be a native Python int.
- Must equal 44100.

The output represents exactly 10 seconds:

    duration = len(waveform) / sample_rate

The expected duration must be 10.0 seconds.

==================================================
4. AUDIO GENERATION REQUIREMENTS
==================================================

Generate five different recognizable melody patterns, one for each style:

- Classical
- Jazz
- Blues
- Electronic
- Folk

Use note frequencies in Hz. A frequency of 0.0 may be used for a rest.

Use these fixed audio settings:

    sample_rate = 44100
    duration_seconds = 10.0
    note_duration_seconds = 0.5
    amplitude = 0.8

Each style should contain twenty 0.5-second notes so that the complete melody is exactly 10 seconds long.

Generate a sine-wave tone for each note unless a different synthesis method is explicitly needed for a style. Keep the implementation simple, deterministic, and dependency-light.

Apply a short attack and release envelope to each note to reduce clicks at note transitions. The envelope must not change the final array length.

Keep the output amplitude within approximately -0.8 to +0.8. Avoid clipping.

Do not use random numbers unless a fixed deterministic seed is used. Prefer deterministic output so that the waveform is reproducible between calls.

==================================================
5. LABVIEW COMPATIBILITY REQUIREMENTS
==================================================

The module must be suitable for the LabVIEW Python Node.

Use only native Python types at the public function boundary:

- int
- float
- str
- list
- tuple

Do not expose these types in the function return value:

- numpy.ndarray
- numpy.float64
- numpy.int64
- dict
- generator
- custom class instance

NumPy is not required. Prefer the Python standard library, especially math, unless NumPy materially simplifies the implementation. If NumPy is used internally, convert every output to native Python types before returning it.

All imports must be at the top of the module.

Do not use module-level mutable state.
Do not use global waveform buffers.
Do not write files from the public function.
Do not open an audio device from Python.
Do not play audio from Python.

LabVIEW, not Python, will play the returned waveform through the PC sound card.

==================================================
6. FUNCTION DOCSTRING
==================================================

Add a clear docstring to play_melody that documents:

- The function name.
- The input type and accepted Enum values.
- The output types.
- The sample rate.
- The waveform length.
- The 10-second duration.
- The LabVIEW Enum mapping.
- The fallback behavior for invalid input.

==================================================
7. ERROR HANDLING
==================================================

The function should not fail for normal invalid melody selections.

For invalid integer values, nonnumeric values, or unrecognized strings, use Classical as the fallback.

Do not silently return None.
Do not return an empty list.
Do not raise an exception solely because the melody selection is outside the valid range.

If an unexpected programming error occurs, allow it to raise normally so that LabVIEW can report the Python error rather than hiding it.

==================================================
8. STANDALONE SMOKE TEST
==================================================

Include a main guard:

    if __name__ == "__main__":

The smoke test must call the function for all five Enum values:

    0, 1, 2, 3, 4

For each call, verify:

1. The result is a tuple with two elements.
2. The waveform is a list.
3. The sample rate is an int.
4. The sample rate equals 44100.
5. The waveform length equals 441000.
6. The first 1000 waveform values are native Python floats.
7. The waveform contains finite values only.
8. The absolute peak amplitude is no greater than 0.8 plus a small numerical tolerance.
9. The waveform is not all zeros for the five valid styles.

Also test:

- The string input "Classical".
- The string input "jazz".
- An invalid string.
- An invalid integer such as 99.

Print one PASS or FAIL line for each test and finish with exactly one of:

    OVERALL PASS

or:

    OVERALL FAIL

The module is not ready for LabVIEW until the standalone test prints OVERALL PASS.

==================================================
9. CODE QUALITY REQUIREMENTS
==================================================

Write readable, maintainable Python.

Use meaningful names such as:

- sample_rate
- duration_seconds
- note_seconds
- samples_per_note
- envelope_samples
- waveform
- frequency
- style_index

Avoid unnecessary abstractions.
Avoid external packages unless required.
Avoid asynchronous code.
Avoid threading.
Avoid audio playback libraries.
Avoid sound-card access.

Make the function deterministic and safe to call repeatedly from LabVIEW.

==================================================
10. REQUIRED RESPONSE FORMAT
==================================================

When you finish, provide:

1. The complete contents of play_melody.py in one Python code block.
2. A short explanation of the LabVIEW input and output types.
3. The exact Enum mapping.
4. The LabVIEW Python Node return-type configuration.
5. The standalone command used to test the file.
6. The expected smoke-test output.
7. Any assumptions or compatibility warnings.

Do not provide pseudocode.
Do not omit the smoke test.
Do not provide multiple competing implementations.
Produce one complete implementation that can be saved directly as play_melody.py.
```

---

## LabVIEW Integration Contract

The Python agent must preserve this interface:

| Direction | Name | LabVIEW type | Python type |
|---|---|---|---|
| Input | `melody` | Enum, underlying I32 | `int` |
| Output 1 | `waveform` | 1D DBL Array | `list[float]` |
| Output 2 | `sample_rate` | I32 | `int` |

The Python function returns a two-element tuple:

```python
(waveform, sample_rate)
```

Configure the LabVIEW Python Node return type as a cluster containing:

1. A 1D DBL Array.
2. An I32.

If the LabVIEW Python Node does not accept the Enum directly, convert the Enum to an I32 using a To Long Integer function before calling Python.

## Required Enum Order

Create `Melody Style.ctl` with these items in this exact order:

```text
Classical
Jazz
Blues
Electronic
Folk
```

The order must not change after the VI is wired because the Python code uses the numeric values 0 through 4.

## Standalone Test Commands

From Command Prompt, change to the directory containing the file:

```cmd
cd C:\path\to\the\folder\containing\the\file
```

Run the smoke test:

```cmd
python play_melody.py
```

Check the Python executable used for testing:

```cmd
python -c "import sys; print(sys.executable); print(sys.version)"
```

The Python executable used for standalone testing should be the same executable configured for the LabVIEW Python session.

## Acceptance Criteria

Do not connect the module to LabVIEW until all of the following are true:

- `python -m py_compile play_melody.py` completes without an error.
- `python play_melody.py` prints `OVERALL PASS`.
- All five numeric Enum values generate different valid waveforms.
- Each waveform is a native Python list.
- Each sample is a native Python float.
- The sample rate is a native Python int equal to 44100.
- Each waveform contains exactly 441000 samples.
- No Python audio playback or sound-card access is used.
- The return order is exactly `(waveform, sample_rate)`.
- The function signature remains exactly `play_melody(melody)`.

## Relationship to the LabVIEW VI

The LabVIEW VI is responsible for:

1. Providing the `Melody Style.ctl` Enum.
2. Converting the Enum to I32 if required.
3. Calling the Python Node.
4. Receiving the waveform and sample rate.
5. Playing the waveform through the non-Express LabVIEW sound-output VIs.
6. Waiting for playback completion before clearing the sound-output reference.
7. Computing the STFT over the complete waveform.
8. Displaying the time-scaled and frequency-scaled spectrogram.

The Python module is responsible only for deterministic waveform generation and returning LabVIEW-compatible data.
