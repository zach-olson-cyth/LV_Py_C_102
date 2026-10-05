"""LabVIEW Python Node-compatible melody waveform generator.

Public interface (do not change positional parameter order):
    play_melody(melody)

Input:
    melody: LabVIEW Melody Type enum underlying I32 value
        0 = Classical
        1 = Jazz
        2 = Blues
        3 = Electronic
        4 = Folk

Return:
    (waveform, sample_rate)
        waveform: plain Python list[float]
        sample_rate: plain Python float in samples/second
"""

import math


_SAMPLE_RATE = 44100.0
_AMPLITUDE = 0.65
_ATTACK_SECONDS = 0.008
_RELEASE_SECONDS = 0.025


def _midi_to_hz(midi_note):
    """Return the frequency in Hz for an integer MIDI note."""
    return 440.0 * (2.0 ** ((float(midi_note) - 69.0) / 12.0))


def _make_note(midi_note, duration_seconds, waveform_type, amplitude):
    """Create one monophonic note as a plain Python list of floats."""
    sample_count = max(1, int(round(float(duration_seconds) * _SAMPLE_RATE)))
    frequency = _midi_to_hz(midi_note)
    attack_count = max(1, int(round(_ATTACK_SECONDS * _SAMPLE_RATE)))
    release_count = max(1, int(round(_RELEASE_SECONDS * _SAMPLE_RATE)))
    output = []

    for index in range(sample_count):
        time_seconds = float(index) / _SAMPLE_RATE
        phase = 2.0 * math.pi * frequency * time_seconds

        if waveform_type == "sine":
            sample = math.sin(phase)
        elif waveform_type == "jazz":
            sample = (
                0.74 * math.sin(phase)
                + 0.19 * math.sin(2.0 * phase)
                + 0.07 * math.sin(3.0 * phase)
            )
        elif waveform_type == "blues":
            sample = (
                0.76 * math.sin(phase)
                + 0.18 * math.sin(2.0 * phase)
                + 0.06 * math.sin(4.0 * phase)
            )
        elif waveform_type == "electronic":
            fundamental = math.sin(phase)
            harmonic_3 = math.sin(3.0 * phase)
            harmonic_5 = math.sin(5.0 * phase)
            sample = 0.72 * fundamental + 0.20 * harmonic_3 + 0.08 * harmonic_5
        elif waveform_type == "folk":
            sample = (
                0.82 * math.sin(phase)
                + 0.13 * math.sin(2.0 * phase)
                + 0.05 * math.sin(3.0 * phase)
            )
        else:
            sample = math.sin(phase)

        envelope = 1.0
        if index < attack_count:
            envelope *= float(index) / float(attack_count)
        if index >= sample_count - release_count:
            envelope *= float(sample_count - 1 - index) / float(release_count)

        output.append(float(amplitude * envelope * sample))

    return output


def _make_silence(duration_seconds):
    """Create a silent gap as a plain Python list of floats."""
    sample_count = max(0, int(round(float(duration_seconds) * _SAMPLE_RATE)))
    return [0.0] * sample_count


def _render_phrase(notes, waveform_type, amplitude, gap_seconds):
    """Render (MIDI note, seconds) pairs into one monophonic waveform."""
    output = []
    for midi_note, duration_seconds in notes:
        output.extend(_make_note(midi_note, duration_seconds, waveform_type, amplitude))
        if gap_seconds > 0.0:
            output.extend(_make_silence(gap_seconds))
    return output


def play_melody(melody):
    """Generate a style-selected audio waveform for the LabVIEW Python Node.

    The sole positional argument is coerced to an integer and clamped to the
    LabVIEW enum range 0 through 4. The return value is a two-field tuple for
    a LabVIEW cluster: (1D DBL waveform array, DBL sample rate).
    """
    try:
        style_index = int(melody)
    except (TypeError, ValueError, OverflowError):
        style_index = 0

    if style_index < 0:
        style_index = 0
    elif style_index > 4:
        style_index = 4

    if style_index == 0:
        notes = [
            (60, 0.24), (62, 0.24), (64, 0.24), (65, 0.24),
            (67, 0.36), (65, 0.12), (64, 0.24), (62, 0.24),
            (60, 0.48),
        ]
        waveform = _render_phrase(notes, "sine", _AMPLITUDE, 0.008)
    elif style_index == 1:
        notes = [
            (60, 0.18), (63, 0.18), (67, 0.30), (70, 0.18),
            (69, 0.18), (67, 0.30), (65, 0.18), (63, 0.18),
            (60, 0.42),
        ]
        waveform = _render_phrase(notes, "jazz", _AMPLITUDE, 0.014)
    elif style_index == 2:
        notes = [
            (57, 0.26), (60, 0.26), (62, 0.18), (63, 0.18),
            (64, 0.34), (62, 0.18), (60, 0.18), (57, 0.46),
        ]
        waveform = _render_phrase(notes, "blues", _AMPLITUDE, 0.016)
    elif style_index == 3:
        notes = [
            (48, 0.14), (55, 0.14), (60, 0.14), (67, 0.14),
            (72, 0.14), (67, 0.14), (60, 0.14), (55, 0.14),
            (48, 0.28),
        ]
        waveform = _render_phrase(notes, "electronic", _AMPLITUDE, 0.004)
    else:
        notes = [
            (62, 0.24), (65, 0.24), (67, 0.24), (69, 0.24),
            (67, 0.24), (65, 0.24), (62, 0.24), (60, 0.48),
        ]
        waveform = _render_phrase(notes, "folk", _AMPLITUDE, 0.012)

    return (waveform, float(_SAMPLE_RATE))


if __name__ == "__main__":
    expected_names = ["Classical", "Jazz", "Blues", "Electronic", "Folk"]
    passed = True

    for style_index, style_name in enumerate(expected_names):
        result = play_melody(style_index)
        waveform, sample_rate = result
        is_valid = (
            isinstance(result, tuple)
            and len(result) == 2
            and isinstance(waveform, list)
            and len(waveform) > 0
            and all(isinstance(value, float) for value in waveform)
            and isinstance(sample_rate, float)
            and sample_rate == _SAMPLE_RATE
            and max(abs(value) for value in waveform) <= _AMPLITUDE
        )
        print("{0}: {1} ({2} samples at {3:.0f} Hz)".format(
            style_name,
            "PASS" if is_valid else "FAIL",
            len(waveform),
            sample_rate,
        ))
        passed = passed and is_valid

    invalid_waveform, invalid_rate = play_melody(999)
    invalid_is_valid = (
        isinstance(invalid_waveform, list)
        and len(invalid_waveform) > 0
        and all(isinstance(value, float) for value in invalid_waveform)
        and isinstance(invalid_rate, float)
    )
    print("Out-of-range clamp: {0}".format("PASS" if invalid_is_valid else "FAIL"))
    passed = passed and invalid_is_valid

    print("OVERALL: {0}".format("PASS" if passed else "FAIL"))
