# LabVIEW Python Node Melody Generator Guide

## Purpose

`play_melody.py` generates one of five named musical styles and returns a 10-second mono waveform for playback through LabVIEW and the computer sound card.

The LabVIEW input should be an **Enum**, not a free-form string. The Enum is converted to its underlying integer value before it is passed to the Python Node.

## Function Interface

```python
waveform, sample_rate = play_melody(melody)
```

| Item | LabVIEW type | Python type | Description |
|---|---|---|---|
| `melody` input | **Enum**, underlying representation `I32` | `int` | Selects the musical style |
| `waveform` output | 1D DBL Array | `list[float]` | 441,000 mono audio samples |
| `sample_rate` output | I32 | `int` | 44,100 samples/second |

## Enum Definition

Create a typedef Enum named:

```text
Melody Style.ctl
```

Populate the Enum items in this exact order:

| Enum item | Numeric value | Musical style |
|---|---:|---|
| `Classical` | 0 | Classical-style melody |
| `Jazz` | 1 | Jazz-style melody |
| `Blues` | 2 | Blues-style melody |
| `Electronic` | 3 | Electronic-style melody |
| `Folk` | 4 | Folk-style melody |

The item order is important because the Python function receives the Enum's numeric value. Do not reorder the items after wiring the VI unless the Python mapping is changed at the same time.

## How to Build the LabVIEW Enum

1. On the Front Panel, open the **Controls** palette.
2. Select **Ring & Enum**.
3. Select **Enum** and place it on the Front Panel.
4. Right-click the Enum and select **Edit Items**.
5. Add these items in order: `Classical`, `Jazz`, `Blues`, `Electronic`, `Folk`.
6. Save the control as a typedef named `Melody Style.ctl`.
7. Use this typedef as the input control connected to the Python Node.

## Python Mapping

```text
0 -> Classical
1 -> Jazz
2 -> Blues
3 -> Electronic
4 -> Folk
```

The function also accepts the style names as strings during direct Python testing, but the recommended LabVIEW interface is the Enum with an I32 underlying value.

## LabVIEW Python Node Wiring

### Input

Wire the `Melody Style.ctl` Enum directly to the Python Node input parameter.

| Python Node item | Setting |
|---|---|
| Module path | Full path to `play_melody.py` |
| Function name | `play_melody` |
| Input parameter | `melody` Enum, underlying I32 |

If the Python Node does not accept the Enum directly in the installed LabVIEW/Python combination, place a **To Long Integer** conversion between the Enum and the Python Node. The resulting value must be 0, 1, 2, 3, or 4.

### Return Type

The function returns:

```python
(waveform, sample_rate)
```

Configure the Python Node return type as a **Cluster** containing:

1. A 1D DBL Array for `waveform`.
2. An I32 for `sample_rate`.

Do not configure the return value as a scalar DBL or as a bare 1D array.

## Waveform Details

- Sample rate: `44,100 Hz`.
- Duration: `10 seconds`.
- Number of samples: `441,000`.
- Channel count: mono.
- Peak amplitude: approximately `0.8` or less.
- Note duration: `0.5 seconds`.
- Notes per style: 20.
- Frequency `0.0`: rest.
- A short attack and release envelope reduces clicks between notes.

## Standalone Python Test

Open Command Prompt in the folder containing `play_melody.py`:

```cmd
cd C:\path\to\the\folder\containing\the\file
```

Run the built-in smoke test:

```cmd
python play_melody.py
```

Expected output:

```text
Classical: PASS
Jazz: PASS
Blues: PASS
Electronic: PASS
Folk: PASS
OVERALL PASS
```

Test one style directly:

```cmd
python -c "from play_melody import play_melody; y, fs = play_melody(3); print(len(y), fs, type(y), type(fs))"
```

Expected values include:

```text
441000 44100 <class 'list'> <class 'int'>
```

## Determine Python Version and Location

### Command Prompt

```cmd
python --version
```

```cmd
py --version
```

```cmd
where python
```

```cmd
where py
```

```cmd
py --list
```

```cmd
py -0p
```

```cmd
python -c "import sys; print(sys.executable)"
```

```cmd
python -c "import sys; print(sys.executable); print(sys.version)"
```

```cmd
py -3.9 -c "import sys; print(sys.executable); print(sys.version)"
```

Replace `3.9` with the version being evaluated.

### PowerShell

```powershell
python --version
```

```powershell
Get-Command python | Format-List Source,Path,Version
```

```powershell
Get-Command py | Format-List Source,Path,Version
```

```powershell
python -c "import sys; print(sys.executable); print(sys.version)"
```

## Check Python Bitness

```cmd
python -c "import struct; print(struct.calcsize('P') * 8)"
```

Expected output is normally either `32` or `64`.

Check LabVIEW bitness under:

```text
Help > About LabVIEW
```

Use a Python bitness compatible with the LabVIEW installation and verify the Python version against the compatibility guidance for the installed LabVIEW release.

## Troubleshooting

### Python function not found

Verify:

```text
Module: play_melody.py
Function: play_melody
```

### Wrong melody selected

Check that the LabVIEW Enum item order exactly matches the table in this guide. The Python mapping is numeric, so changing Enum order changes the selected style.

### Return conversion error

Confirm that the return type is a cluster containing a 1D DBL Array and an I32. The supplied function returns a plain Python list, not a NumPy array.

### Enum input conversion error

Insert a **To Long Integer** function between the Enum and Python Node. The resulting value must be 0, 1, 2, 3, or 4.

## References

- Python `sys` documentation: <https://docs.python.org/3/library/sys.html>
- Python on Windows documentation: <https://docs.python.org/3/using/windows.html>
- NI Python/LabVIEW integration documentation: <https://www.ni.com/en/support/documentation/supplemental/18/installing-python-for-calling-python-code.html>
- NI Python Node reference: <https://www.ni.com/docs/en-US/bundle/labview-api-ref/page/functions/python-node.html>
