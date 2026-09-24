# eyerobot

A mechanical eye running on a Raspberry Pi Pico 2 W (MicroPython). Three hobby servos drive left-right gaze, up-down gaze, and the eyelids. The firmware produces natural-looking behaviour: saccades, fixations, scanning, micro-drift during long stares, lid-follow, and blinks.

## Files

- `main.py` – the eye behaviour loop; runs automatically on boot.
- `calibrate.py` – interactive helper for finding each servo's usable angle range.
- `blink.py` – a minimal eyelid blink test.

## Wiring

| Servo | Pin |
|-------|-----|
| Left-right | GP2 |
| Up-down | GP3 |
| Eyelids | GP4 |

Calibrated angles live at the top of `main.py`; re-run `calibrate.py` if you change the mechanism.
