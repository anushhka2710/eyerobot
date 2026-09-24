# SAFE 3-servo calibration (no automatic movement, servos start OFF)
#
# Angle scale matches the reference Arduino code (0° = 544 µs, 180° = 2400 µs),
# so the reference values are usable starting points:
#   left-right: lower 60, upper 115, centre 90
#   up-down:    lower 45, upper 120, centre 85
#   eyelids:    open 75, closed 145
#
# Commands (type in the serial console, then Enter):
#   l / u / e   select servo: l = left-right (GP2), u = up-down (GP3), e = eyelids (GP4)
#   on 85       start sending a signal to the selected servo, at 85° (it will snap there)
#   off         stop the signal to the selected servo (it goes limp)
#   off all     stop every servo
#   +  -        move selected servo 1°
#   +5  -5      move selected servo 5°  (any +N / -N works)
#   g 85        go to angle 85 (gradually)
#   p           print all servo angles
from machine import Pin, PWM
import time

STEP_DELAY = 0.04     # seconds per 1° step - every move is gradual, never a snap

# Reference-code pulse scale
MIN_PULSE_US = 544
MAX_PULSE_US = 2400


def pulse_ns(angle):
    return int((MIN_PULSE_US + (MAX_PULSE_US - MIN_PULSE_US) * angle / 180) * 1000)


# Each servo: pin, safe limits, last known angle. "pwm" is None while the servo is off.
# Pin numbers are GPIO names (GP2 = physical pin 4, GP3 = pin 5, GP4 = pin 6).
# Confirmed with ONE servo plugged in at a time: GP2 = left-right, GP3 = up-down, GP4 = eyelids.
SERVOS = {
    "l": {"name": "left-right (GP2)", "pin": 2, "lo": 66, "hi": 145, "angle": 110, "pwm": None},  # right 68, forward 110, left 145
    "u": {"name": "up-down    (GP3)", "pin": 3, "lo": 40, "hi": 125, "angle": 85,  "pwm": None},
    "e": {"name": "eyelids    (GP4)", "pin": 4, "lo": 90, "hi": 140, "angle": 97,  "pwm": None},  # open ~97, closed ~134 (higher = closed)
}

# ---- Startup: NO signals. Every servo stays limp until you turn it on. ----
for s in SERVOS.values():
    Pin(s["pin"], Pin.IN)


def servo_on(s, angle):
    """Start driving the servo at this angle. It WILL snap to it, so pick the angle its arm is near."""
    angle = max(s["lo"], min(s["hi"], angle))
    s["angle"] = angle
    s["pwm"] = PWM(Pin(s["pin"]), freq=50, duty_ns=pulse_ns(angle))


def servo_off(s):
    """Stop the signal; the servo goes limp."""
    if s["pwm"]:
        s["pwm"].duty_ns(0)     # zero pulse = no signal (GP2/GP3 share a PWM slice, so don't deinit)
        s["pwm"] = None
    Pin(s["pin"], Pin.IN)


def move_to(s, target):
    """Walk the servo 1° at a time to target, clamped to its safe range."""
    if not s["pwm"]:
        print("that servo is OFF - use: on <angle>")
        return
    target = max(s["lo"], min(s["hi"], target))
    while s["angle"] != target:
        s["angle"] += 1 if target > s["angle"] else -1
        s["pwm"].duty_ns(pulse_ns(s["angle"]))
        time.sleep(STEP_DELAY)


def print_all():
    for key in ("l", "u", "e"):
        s = SERVOS[key]
        state = "%d" % s["angle"] if s["pwm"] else "OFF (last %d)" % s["angle"]
        limit = "  (at limit)" if s["pwm"] and s["angle"] in (s["lo"], s["hi"]) else ""
        print("  %s %s: %s%s" % (key, s["name"], state, limit))


print("All servos OFF (no signal). Use l/u/e then 'on <angle>' to enable one.")
print("Commands: l/u/e, on <angle>, off, off all, +, -, +5, -5, g <angle>, p")
print_all()

selected = "e"

while True:
    cmd = input("[%s] > " % selected).strip().lower()
    s = SERVOS[selected]

    try:
        if cmd in SERVOS:
            selected = cmd
        elif cmd == "p":
            pass
        elif cmd == "off all":
            for x in SERVOS.values():
                servo_off(x)
        elif cmd == "off":
            servo_off(s)
        elif cmd.startswith("on "):
            servo_on(s, int(cmd[3:]))
        elif cmd.startswith("g "):
            move_to(s, int(cmd[2:]))
        elif cmd[:1] in ("+", "-"):
            delta = 1 if cmd == "+" else -1 if cmd == "-" else int(cmd)
            move_to(s, s["angle"] + delta)
        else:
            print("unknown command:", cmd)
            continue
    except ValueError:
        print("bad number in command:", cmd)
        continue

    print_all()
