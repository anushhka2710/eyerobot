# Eyelid blinking - eyelid servo on GP4. Left-right (GP2) and up-down (GP3) stay OFF.
from machine import Pin, PWM
import time
import random

# ---- Tune these two ----
OPEN_ANGLE   = 93     # lids open  (lower = more open; 90 jittered against the open stop)
CLOSED_ANGLE = 134    # lids closed (higher = more closed)

# ---- Blink timing (seconds) ----
CLOSE_TIME = 0.15     # time to close
HOLD_TIME  = 0.12     # time held shut
OPEN_TIME  = 0.25     # time to open (a bit slower than closing)
WAIT_MIN   = 2.0      # shortest gap between blinks
WAIT_MAX   = 6.0      # longest gap between blinks
RELAX_AT_REST = False # stop the servo signal between blinks so it can't jitter/hunt

# Same angle scale as calibrate.py and the reference Arduino code
MIN_PULSE_US = 544
MAX_PULSE_US = 2400
FRAME = 0.02          # 20 ms per update (50 Hz)

# Keep the other two servos silent
Pin(2, Pin.IN)
Pin(3, Pin.IN)


def pulse_ns(angle):
    return int((MIN_PULSE_US + (MAX_PULSE_US - MIN_PULSE_US) * angle / 180) * 1000)


lids = PWM(Pin(4), freq=50, duty_ns=pulse_ns(OPEN_ANGLE))   # start open


def move(start, end, duration):
    """Glide from start to end over `duration` seconds (ease in/out)."""
    steps = max(1, int(duration / FRAME))
    for i in range(1, steps + 1):
        t = i / steps
        t = t * t * (3 - 2 * t)             # smoothstep easing
        lids.duty_ns(pulse_ns(start + (end - start) * t))
        time.sleep(FRAME)


def blink():
    lids.duty_ns(pulse_ns(OPEN_ANGLE))          # make sure the signal is on (servo is already at OPEN)
    time.sleep(0.05)
    move(OPEN_ANGLE, CLOSED_ANGLE, CLOSE_TIME)
    time.sleep(HOLD_TIME)
    move(CLOSED_ANGLE, OPEN_ANGLE, OPEN_TIME)
    time.sleep(0.3)                              # let it settle fully open
    if RELAX_AT_REST:
        lids.duty_ns(0)                          # no pulses = servo relaxes, no hunting


print("Eyelids open at", OPEN_ANGLE, "- blinking to", CLOSED_ANGLE)
time.sleep(1)
if RELAX_AT_REST:
    lids.duty_ns(0)

while True:
    time.sleep(random.uniform(WAIT_MIN, WAIT_MAX))
    print("blink")
    blink()
