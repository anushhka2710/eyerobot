# Mechanical eye - natural behaviour: saccades, fixations, scanning, lid-follow, blinks.
# Pins are GPIO names. Angles use the same scale as calibrate.py (544-2400 us).
from machine import Pin, PWM
import time
import random

# ---- Calibrated angles (found with calibrate.py) ----
LR_PIN,  LR_RIGHT, LR_CENTRE, LR_LEFT = 2, 68, 110, 145    # left-right (eye's left = viewer's right; 62 clashed with the horn behind, 68 ok)
UD_PIN,  UD_DOWN,  UD_CENTRE, UD_UP   = 3, 50, 100, 125    # up-down
LID_PIN, LID_OPEN, LID_CLOSED         = 4, 93, 134         # eyelids

# ---- Eye movement ----
REST_DOWN         = 5            # resting gaze sits this many degrees below level
CENTRE_BIAS       = 0.4          # most looks stay within 40% of the range around the rest point
FAR_LOOK_CHANCE   = 0.25         # ...but sometimes look anywhere in the full range
SACCADE_BASE      = 0.06         # seconds for a tiny hop
SACCADE_PER_DEG   = 0.0025       # extra seconds per degree of travel (40 deg -> 0.16 s)
FIX_SHORT         = (0.3, 1.0)   # usual fixation (hold) time
FIX_LONG          = (2.5, 6.0)   # occasional long stare
LONG_STARE_CHANCE = 0.3
SCAN_CHANCE       = 0.4          # chance a look is followed by 1-2 small nearby hops
SCAN_RADIUS       = 8            # degrees
SCAN_FIX          = (0.2, 0.5)   # fixation between scan hops
MICRO_DEG         = 1.5          # tiny drift during long stares
MICRO_GAP         = (0.4, 0.9)

# ---- Eyelids ----
LID_DROOP_DOWN    = 8            # top lid lowers up to this much when looking fully down
LID_LIFT_UP       = 2            # lid opens a touch when looking up (open stop is close)
BLINK_GAP         = (1.5, 8.0)   # blink spacing (skewed toward the short end)
DOUBLE_BLINK      = 0.15
HALF_BLINK        = 0.10         # slow partial blink
CLOSE_TIME, HOLD_TIME, OPEN_TIME = 0.12, 0.10, 0.22
BIG_LOOK          = 20           # a look this big (degrees)...
BLINK_ON_BIG_LOOK = 0.6          # ...has this chance of happening under a blink

# ---- Light sensor (photoresistor on GP26 with a 10k divider; bright light RAISES the reading) ----
LIGHT_ENABLED     = True         # photoresistor wired and tested
LIGHT_PIN         = 26
LIGHT_BRIGHT_IS_LOW = False      # torch RAISES the reading (ambient ~54000, torch ~65000)
LIGHT_MARGIN      = 6000         # how far from room level counts as "bright light" (torch measured +10000, noise +-500)
LIGHT_RELEASE     = 0.6          # reopen once light falls below this fraction of the margin (hysteresis)
LIGHT_REOPEN_WAIT = 0.4          # seconds after the light goes before opening again
LIGHT_TRACK       = 0.002        # how fast the "room level" follows slow changes while the eye is open (~30 s)
LIGHT_PRINT_EVERY = 1.0          # seconds between readings printed to the console (0 = never)

# ---- Sleep (room goes dark for a long time) ----
SLEEP_ENABLED     = True
DARK_FRACTION     = 0.85         # dark = reading below this fraction of the lit-room level (lit ~40500, dimmed ~32500)
DARK_HYST         = 1500         # hysteresis around the dark threshold
LIGHTS_ON_TIME    = 1.5          # a rise from dark that lasts this long = lights on (not a torch)
WAKE_RISE         = 4000         # while asleep, a rise this far above the dark level = light, wake up
DARK_TIME         = 5            # seconds of continuous dark (e.g. sensor covered) before getting drowsy
DROWSY_TIME       = 6            # seconds spent getting drowsy before dropping off
SLEEP_TWITCH_GAP  = (5, 15)      # seconds between little twitches while asleep
SLEEP_STIR_CHANCE = 0.2          # chance a twitch is a sleepy stir (lids crack open and close)
WAKE_LIGHT_TIME   = 2.0          # seconds of light before waking gently (only used if WAKE_SOUND_ONLY is False)
START_ASLEEP      = True         # boot straight into sleep; a clap or a light held on it for a moment wakes it
WAKE_STRUGGLES    = (1, 1)       # groggy wake: this many failed tries to get the lids up before it manages (whole wake ~5 s)
WAKE_STRUGGLE_OPEN = (0.35, 0.6) # each try drags the lids about this far open (0 = shut, 1 = open), a bit further each time...
WAKE_SAG_PAUSE    = (0.2, 0.4)   # ...then they sag shut again and it dozes this long before the next try
WAKE_SOUND_FLARE  = 0.5          # a clap jerks the lids this far open first, before they sag back down
WAKE_SOUND_ONLY   = True         # asleep (at boot, or after the dark): only a spike in sound from either mic wakes it; light is ignored

# ---- Dazzle performance (what the eye does while a bright light is on it) ----
DAZZLE_HOLD       = (0.6, 1.0)   # beat held fully shut after the snap
SQUINT_START      = 0.3          # each try starts about this far open (0 = shut, 1 = normal open)
SQUINT_REACH      = (0.5, 0.7)   # ...and pushes open to somewhere in this range before it's too bright
SQUINT_FLINCH     = 0.15         # then flinches back down to this
SQUINT_TREMOR     = 3            # degrees of muscle-tension tremor while pushing open
SQUINT_PUSHES     = 1            # push-open-and-flinch cycles per peek (keep it low: more looks like fluttering)
SQUINT_ATTEMPTS   = (1, 2)       # peeks before giving up and staying shut until the light goes
GIVEUP_WAIT       = (1.5, 3.0)   # shut time between peeks
AVERT_DOWN        = 15           # eye turns down this much while squinting...
AVERT_SIDE        = 10           # ...and this much to one side
RECOVER_BLINKS    = (2, 3)       # quick flutter-blinks after the one full blink on recovery

# ---- Sound sensors (KY-038 type: DO pins change state when loud; AO on GP27/GP28 for which-side) ----
SOUND_ENABLED     = True         # DO pins tested: both rest LOW, pulse HIGH on a clap
MIC1_DO, MIC1_AO  = 16, 27       # mic 1 = LEFT side of the eye
MIC2_DO, MIC2_AO  = 17, 28       # mic 2 = RIGHT side
STARTLE_BURST_MS  = 150          # ignore the clap's own burst of pulses for this long after a startle
MOVE_DEAF_MS      = 400          # ignore mic pulses this soon after the servos last moved: the eye's own noise trips the mics
STARTLE_LOOK      = 1.0          # how far toward the sound side (fraction of the L/R range)
STARTLE_FREEZE    = (0.8, 1.5)   # wide-eyed freeze after the dart
STARTLE_WIDE      = 4            # lids open this much wider than normal during the freeze
STARTLE_HOLD      = (0.6, 1.2)   # after the freeze and blinks, keep looking that way this long, then move on

MIN_PULSE_US, MAX_PULSE_US = 544, 2400
FRAME = 0.01                       # 10 ms per update: quicker to abort a move when a clap arrives


def pulse_ns(angle):
    return int((MIN_PULSE_US + (MAX_PULSE_US - MIN_PULSE_US) * angle / 180) * 1000)


last_motion = 0                    # ticks_us of the last servo command, so the eye's own noise can be told from a clap


class Servo:
    def __init__(self, pin, angle, lo, hi):
        self.lo, self.hi = min(lo, hi), max(lo, hi)
        self.angle = angle
        self.pwm = PWM(Pin(pin), freq=50, duty_ns=pulse_ns(angle))

    def set(self, angle):
        global last_motion
        angle = max(self.lo, min(self.hi, angle))     # never outside the calibrated range
        self.angle = angle
        self.pwm.duty_ns(pulse_ns(angle))
        last_motion = time.ticks_us()


BOOT_ASLEEP = START_ASLEEP and LIGHT_ENABLED and SLEEP_ENABLED
lr  = Servo(LR_PIN,  LR_CENTRE, LR_RIGHT, LR_LEFT)
ud  = Servo(UD_PIN,  max(UD_DOWN, UD_CENTRE - 20) if BOOT_ASLEEP else UD_CENTRE, UD_DOWN, UD_UP)
lid = Servo(LID_PIN, LID_CLOSED - 2 if BOOT_ASLEEP else LID_OPEN, LID_OPEN - LID_LIFT_UP, LID_CLOSED)


def ease(t):
    return t * t * (3 - 2 * t)


class Interrupted(Exception):
    """Raised inside a move when a loud sound arrives, so the startle can start at once."""
    pass


interruptible = True      # set False during sequences that must not be cut short (dazzle, startle)


def sound_spike():
    """True if a mic caught a sound that was NOT the eye's own movement. A pulse that arrives within
    MOVE_DEAF_MS of a servo command is the eye's own clatter: discard it and keep listening."""
    if not SOUND_ENABLED or not (snd_t[0] or snd_t[1]):
        return False
    t1, t2 = snd_t[0], snd_t[1]
    t = t1 if not t2 else t2 if not t1 else (t1 if time.ticks_diff(t1, t2) < 0 else t2)   # the earlier edge
    if time.ticks_diff(t, last_motion) < MOVE_DEAF_MS * 1000:
        snd_t[0] = snd_t[1] = 0
        return False
    return True


def sound_pending():
    return interruptible and due(startle_ok_at) and sound_spike()


def move(targets, duration):
    """Move several servos together, all finishing at the same time. targets = [(servo, angle), ...]
    Aborts (raises Interrupted) if a loud sound arrives mid-move."""
    plan = [(s, s.angle, a) for s, a in targets]
    steps = max(1, int(duration / FRAME))
    for i in range(1, steps + 1):
        t = ease(i / steps)
        for s, a0, a1 in plan:
            s.set(a0 + (a1 - a0) * t)
        if sound_pending():
            raise Interrupted()
        time.sleep(FRAME)


def lid_for(ud_angle):
    """Where the top lid should rest for a given vertical gaze (lid follows the eye)."""
    if ud_angle < UD_CENTRE:                      # looking down -> lid droops
        frac = (UD_CENTRE - ud_angle) / (UD_CENTRE - UD_DOWN)
        return LID_OPEN + LID_DROOP_DOWN * frac
    frac = (ud_angle - UD_CENTRE) / (UD_UP - UD_CENTRE)   # looking up -> lid lifts a little
    return LID_OPEN - LID_LIFT_UP * frac


def biased(lo, centre, hi):
    if random.random() < FAR_LOOK_CHANCE:
        return random.uniform(lo, hi)
    return random.uniform(centre - (centre - lo) * CENTRE_BIAS,
                          centre + (hi - centre) * CENTRE_BIAS)


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def saccade(lr_t, ud_t):
    """Quick eye jump. Big jumps often happen under a blink, like a real eye."""
    global next_blink
    dist = max(abs(lr_t - lr.angle), abs(ud_t - ud.angle))
    dur = SACCADE_BASE + SACCADE_PER_DEG * dist
    lid_t = lid_for(ud_t)
    if dist >= BIG_LOOK and random.random() < BLINK_ON_BIG_LOOK:
        move([(lid, LID_CLOSED)], CLOSE_TIME)
        move([(lr, lr_t), (ud, ud_t)], dur)       # eye moves while the lids are shut
        move([(lid, lid_t)], OPEN_TIME)
        next_blink = later(BLINK_GAP)
    else:
        move([(lr, lr_t), (ud, ud_t), (lid, lid_t)], dur)


def blink():
    r = random.random()
    if r < HALF_BLINK:                            # slow partial blink
        mid = (lid_for(ud.angle) + LID_CLOSED) / 2
        move([(lid, mid)], 0.25)
        time.sleep(0.1)
        move([(lid, lid_for(ud.angle))], 0.3)
        return
    move([(lid, LID_CLOSED)], CLOSE_TIME)
    time.sleep(HOLD_TIME)
    move([(lid, lid_for(ud.angle))], OPEN_TIME)
    if r < HALF_BLINK + DOUBLE_BLINK:
        time.sleep(0.12)
        move([(lid, LID_CLOSED)], CLOSE_TIME)
        time.sleep(HOLD_TIME)
        move([(lid, lid_for(ud.angle))], OPEN_TIME)


def later(lo_hi, skew=False):
    secs = random.uniform(*lo_hi)
    if skew:                                      # favour the short end
        secs = min(secs, random.uniform(*lo_hi))
    return time.ticks_add(time.ticks_ms(), int(secs * 1000))


def due(t):
    return time.ticks_diff(time.ticks_ms(), t) >= 0


# ---- Light sensor ----
if LIGHT_ENABLED:
    from machine import ADC
    ldr = ADC(LIGHT_PIN)
    room = sum(ldr.read_u16() for _ in range(50)) / 50      # room light level at startup
    lit_room = room                                          # assume we start with the lights on
    dark_room = room * DARK_FRACTION                         # updated when it actually gets dark
    print("light sensor on: room level %d, closes when brighter by %d, dark below %d" % (room, LIGHT_MARGIN, room * DARK_FRACTION))
next_light_print = time.ticks_ms()


def light_excess():
    v = ldr.read_u16()
    return v, ((room - v) if LIGHT_BRIGHT_IS_LOW else (v - room))


def light_gone(state):
    """True once the light has been below the release level for LIGHT_REOPEN_WAIT. state = [gone_at]."""
    v, excess = light_excess()
    if excess > LIGHT_MARGIN * LIGHT_RELEASE:
        state[0] = None
        return False
    if state[0] is None:
        state[0] = time.ticks_ms()
    return time.ticks_diff(time.ticks_ms(), state[0]) > LIGHT_REOPEN_WAIT * 1000


def wait_shut(secs, state):
    """Stay still for secs; return True early if the light goes away."""
    end = time.ticks_add(time.ticks_ms(), int(secs * 1000))
    while time.ticks_diff(time.ticks_ms(), end) < 0:
        if light_gone(state):
            return True
        time.sleep(0.03)
    return False


def squint_peek(state):
    """Tug-of-war squint: the lid pushes open a little further each try, the brightness bites,
    it flinches back down, quivers, and tries again. True if the light goes during it."""
    lid_open = lid_for(ud.angle)

    def at(f):                                   # lid angle for a fraction open (0 = shut, 1 = open)
        return LID_CLOSED - (LID_CLOSED - lid_open) * f

    side = random.choice((-AVERT_SIDE, AVERT_SIDE))
    move([(lid, at(SQUINT_START)),
          (ud, clamp(ud.angle - AVERT_DOWN, UD_DOWN, UD_UP)),
          (lr, clamp(lr.angle + side, LR_RIGHT, LR_LEFT))], 0.2)
    for _ in range(SQUINT_PUSHES):                # one slow push open, one flinch, then give up
        reach = random.uniform(*SQUINT_REACH)
        steps = random.randint(4, 8)
        for i in range(1, steps + 1):             # push open, trembling
            if light_gone(state):
                return True
            f = SQUINT_START + (reach - SQUINT_START) * i / steps
            move([(lid, at(f) + random.uniform(-SQUINT_TREMOR, SQUINT_TREMOR))], random.uniform(0.06, 0.12))
        move([(lid, at(SQUINT_FLINCH))], 0.05)    # too bright: flinch back down
        hold_end = time.ticks_add(time.ticks_ms(), int(random.uniform(0.15, 0.4) * 1000))
        while time.ticks_diff(time.ticks_ms(), hold_end) < 0:   # quivering hold
            if light_gone(state):
                return True
            move([(lid, at(SQUINT_FLINCH) + random.uniform(-SQUINT_TREMOR / 2, SQUINT_TREMOR / 2))], 0.06)
    return False


def recover():
    """Light has gone: open a little, one full blink, a few quick flutter-blinks, then settle."""
    global next_blink, fixation_end, scan_hops, long_stare
    time.sleep(0.2)
    lid_open = lid_for(ud.angle)
    move([(lid, (lid_open + LID_CLOSED) / 2)], 0.3)      # half open, cautiously
    time.sleep(0.15)
    move([(lid, LID_CLOSED)], CLOSE_TIME)                 # one full blink
    time.sleep(HOLD_TIME)
    move([(lid, lid_open)], OPEN_TIME)
    time.sleep(0.2)
    for _ in range(random.randint(*RECOVER_BLINKS)):      # quick flutter-blinks
        move([(lid, (lid_open + LID_CLOSED) * 0.5)], 0.06)
        move([(lid, lid_open)], 0.08)
        time.sleep(0.05)
    time.sleep(0.3)
    saccade(LR_CENTRE, REST_UD)                           # settle back to a resting gaze
    next_blink   = later(BLINK_GAP, skew=True)
    fixation_end = later(FIX_SHORT)
    scan_hops    = 0
    long_stare   = False


def dazzle():
    """The whole performance. Blocks until the light goes away and the eye has recovered."""
    global room, interruptible
    interruptible = False
    try:
        _dazzle()
    finally:
        interruptible = True


def _dazzle():
    state = [None]
    lid.set(LID_CLOSED)                                   # instant snap shut
    print("DAZZLED")
    if not wait_shut(random.uniform(*DAZZLE_HOLD), state):
        for attempt in range(random.randint(*SQUINT_ATTEMPTS)):
            if squint_peek(state):
                break
            move([(lid, LID_CLOSED)], 0.15)               # give up this peek
            if wait_shut(random.uniform(*GIVEUP_WAIT), state):
                break
        else:
            while not light_gone(state):                  # gave up: stay shut until it's gone
                time.sleep(0.03)
    print("light gone - recovering")
    recover()


def check_light():
    """Watch the sensor; run the dazzle performance if a bright light appears."""
    global room, lit_room, next_light_print
    v, excess = light_excess()
    if dark_since is not None and excess > LIGHT_MARGIN:   # we're in the dark and it just got brighter:
        end = time.ticks_add(time.ticks_ms(), int(LIGHTS_ON_TIME * 1000))   # lights on, or a torch?
        while time.ticks_diff(time.ticks_ms(), end) < 0:
            v, excess = light_excess()
            if excess <= LIGHT_MARGIN:
                break                                     # it went away: a flash, fall through to dazzle
            time.sleep_ms(50)
        else:
            room = lit_room = v                           # sustained: the lights are on, this is the room now
            print("lights on: room level now %d" % room)
            return False
    if LIGHT_PRINT_EVERY and due(next_light_print):
        print("light %d (room %d, brighter by %d)" % (v, room, excess))
        next_light_print = later((LIGHT_PRINT_EVERY, LIGHT_PRINT_EVERY))
    if excess > LIGHT_MARGIN:
        dazzle()
        return True
    if SLEEP_ENABLED and check_sleep(v):
        return True
    if abs(v - room) < LIGHT_MARGIN:
        room += (v - room) * LIGHT_TRACK                  # slowly follow small room changes only
    return False


# ---- Sound sensors ----
if SOUND_ENABLED:
    from machine import ADC
    mic1_do, mic2_do = Pin(MIC1_DO, Pin.IN), Pin(MIC2_DO, Pin.IN)
    mic1_ao, mic2_ao = ADC(MIC1_AO), ADC(MIC2_AO)
    # learn each DO pin's resting level (modules differ: some rest HIGH, some LOW); "loud" = the opposite
    _c1 = sum(mic1_do.value() for _ in range(200)); _c2 = sum(mic2_do.value() for _ in range(200))
    mic1_rest, mic2_rest = (1 if _c1 > 100 else 0), (1 if _c2 > 100 else 0)
    # interrupts latch the first edge on each mic (DO pulses are too short to poll between moves)
    snd_t = [0, 0]                                   # ticks_us of first edge since last clear, 0 = none

    def _mic1_irq(pin):
        if snd_t[0] == 0:
            snd_t[0] = time.ticks_us() or 1

    def _mic2_irq(pin):
        if snd_t[1] == 0:
            snd_t[1] = time.ticks_us() or 1

    mic1_do.irq(trigger=Pin.IRQ_RISING if mic1_rest == 0 else Pin.IRQ_FALLING, handler=_mic1_irq)
    mic2_do.irq(trigger=Pin.IRQ_RISING if mic2_rest == 0 else Pin.IRQ_FALLING, handler=_mic2_irq)
    print("sound sensors on: mic1 rests %d, mic2 rests %d (interrupt driven)" % (mic1_rest, mic2_rest))
startle_ok_at = time.ticks_ms()


def mic_swing(adc, ms=15):
    lo, hi = 65535, 0
    t0 = time.ticks_us()
    while time.ticks_diff(time.ticks_us(), t0) < ms * 1000:
        v = adc.read_u16(); lo = min(lo, v); hi = max(hi, v)
    return hi - lo


def check_sound():
    """A loud sound -> startle toward that side. Re-listens 150 ms later, so a tap on the other
    side during the freeze or the stare redirects the eye at once. Returns True if it happened."""
    global startle_ok_at, interruptible, next_blink, fixation_end, scan_hops, long_stare
    if not sound_spike():
        return False
    if not due(startle_ok_at):                           # still inside a clap's burst: swallow it
        snd_t[0] = snd_t[1] = 0
        return False
    interruptible = False
    lid.set(clamp(lid_for(ud.angle) - STARTLE_WIDE, lid.lo, lid.hi))   # lids flare the instant a mic fires
    time.sleep_ms(8)                                     # give the other mic a moment to fire too
    t1, t2 = snd_t[0], snd_t[1]
    if t1 and t2:
        dt = time.ticks_diff(t1, t2)                     # negative = mic1 fired first
        if abs(dt) < 2000:                               # within 2 ms: too close to call, use loudness
            left = mic_swing(mic1_ao) >= mic_swing(mic2_ao)
        else:
            left = dt < 0
    else:
        left = bool(t1)
    print("STARTLE", "left" if left else "right")
    lr_t = LR_CENTRE + (LR_LEFT - LR_CENTRE) * STARTLE_LOOK if left else LR_CENTRE - (LR_CENTRE - LR_RIGHT) * STARTLE_LOOK
    ud_t = clamp(UD_CENTRE + 5, UD_DOWN, UD_UP)          # eyes come up a touch, alert
    lr.set(lr_t); ud.set(ud_t)                           # instant dart: servos at full speed
    time.sleep_ms(STARTLE_BURST_MS)                      # let this clap's burst of pulses pass...
    snd_t[0] = snd_t[1] = 0                              # ...then listen again
    startle_ok_at = time.ticks_ms()
    interruptible = True
    # frozen stare, but a new clap cuts it short
    end = later(STARTLE_FREEZE)
    while not due(end):
        if sound_spike():
            return True                                  # main loop calls check_sound() again right away
        time.sleep_ms(5)
    move([(lid, LID_CLOSED)], CLOSE_TIME)                # a blink to break the stare (interruptible)
    time.sleep(HOLD_TIME)
    move([(lid, lid_for(ud_t))], OPEN_TIME)
    time.sleep(0.15)
    move([(lid, LID_CLOSED)], CLOSE_TIME)                # and a second, quicker one
    time.sleep(0.05)
    move([(lid, lid_for(ud_t))], OPEN_TIME)
    next_blink   = later(BLINK_GAP, skew=True)
    fixation_end = later(STARTLE_HOLD)                   # a short "what was that?" then back to normal
    long_stare   = False
    scan_hops    = 0
    return True


# ---- Sleep ----
dark_since = None


def lid_frac(f, lid_open=None):
    """Lid angle for a fraction closed (0 = open, 1 = shut)."""
    if lid_open is None:
        lid_open = lid_for(ud.angle)
    return lid_open + (LID_CLOSED - lid_open) * f


def sleep_wake_reason():
    """While drowsy/asleep: None to keep sleeping, else 'light', 'dazzle' or 'sound'."""
    if sound_spike():
        return "sound"
    if WAKE_SOUND_ONLY:
        return None                                   # wait for a clap, whatever the light does
    v, excess = light_excess()
    if v > lit_room + LIGHT_MARGIN:
        return "light" if pretend_dark else "dazzle"
    if v > dark_room + WAKE_RISE:
        return "light"
    return None


def doze(secs, reason_box):
    """Sleep for secs, polling for a wake reason. True if woken.
    (Mic pulses from the eye's own movement are filtered out by sound_spike, so a clap registers at once.)"""
    end = time.ticks_add(time.ticks_ms(), int(secs * 1000))
    while time.ticks_diff(time.ticks_ms(), end) < 0:
        r = sleep_wake_reason()
        if r:
            reason_box[0] = r
            return True
        time.sleep_ms(10)
    return False


def struggle_awake(reason):
    """Groggy wake-up: the lids drag part-way open, the eye rolls up, the lids quiver and sag shut
    again... a few tries, each getting a little further, until it finally manages to stay open."""
    global interruptible
    interruptible = False
    lid_open = lid_for(REST_UD)
    asleep_ud = ud.angle
    if reason == "sound":                                   # a noise: the lids jerk part-way open...
        lid.set(lid_frac(1 - WAKE_SOUND_FLARE, lid_open))
        time.sleep(0.25)
        move([(lid, LID_CLOSED - 2)], 0.4)                  # ...and sag straight back down
        time.sleep(random.uniform(0.2, 0.3))
    tries = random.randint(*WAKE_STRUGGLES)
    lo, hi = WAKE_STRUGGLE_OPEN
    for i in range(tries):
        f = lo + (hi - lo) * i / max(1, tries - 1) + random.uniform(-0.05, 0.05)   # a little further each try
        f = clamp(f, 0.1, 0.8)
        ud_t = clamp(asleep_ud + (REST_UD - asleep_ud) * f, UD_DOWN, UD_UP)        # eye rolls up as the lids lift
        move([(lid, lid_frac(1 - f, lid_open)), (ud, ud_t)], random.uniform(0.4, 0.5))
        move([(lid, lid_frac(1 - f + random.uniform(0.04, 0.10), lid_open))], random.uniform(0.1, 0.15))   # heavy lids quiver
        move([(lid, lid_frac(1 - f, lid_open))], random.uniform(0.1, 0.15))
        move([(lid, LID_CLOSED - 2), (ud, asleep_ud)], random.uniform(0.35, 0.45))  # gives up: sags shut
        time.sleep(random.uniform(*WAKE_SAG_PAUSE))
    # finally: lids drag most of the way up and the eye comes level
    move([(lid, lid_frac(0.35, lid_open)), (ud, REST_UD), (lr, LR_CENTRE)], 0.5)
    time.sleep(0.2)
    move([(lid, LID_CLOSED)], 0.25); time.sleep(0.1); move([(lid, lid_frac(0.15, lid_open))], 0.35)   # slow heavy blink
    time.sleep(0.15)
    move([(lid, lid_open)], 0.35)                           # awake at last
    time.sleep(0.15)
    blink()
    if SOUND_ENABLED:
        snd_t[0] = snd_t[1] = 0                             # whatever woke it is long gone: don't startle at it now
    interruptible = True


def wake_done():
    """Back to normal life: reset the behaviour timers. If we booted asleep in a lit room, whatever
    the light is now counts as 'lights on' so the eye doesn't think it is still dark."""
    global next_blink, fixation_end, scan_hops, long_stare, room, lit_room, pretend_dark
    if pretend_dark:
        room = lit_room = light_excess()[0]
        pretend_dark = False
    next_blink   = later(BLINK_GAP, skew=True)
    fixation_end = later(FIX_SHORT)
    scan_hops    = 0
    long_stare   = False


def go_to_sleep(already_asleep=False):
    """Drowsy -> asleep -> woken. Blocks until something wakes it, then hands back to the main loop.
    already_asleep=True skips the drowsy phase (used at boot)."""
    global interruptible, dark_since, room, lit_room
    interruptible = False
    reason = [None]
    lid_open = lid_for(ud.angle)
    if not already_asleep:
        print("getting drowsy")
    # --- drowsy: lids droop, gaze sinks, slow heavy blinks ---
    t0 = time.ticks_ms(); light_ok_since = None
    while not already_asleep:
        p = min(1.0, time.ticks_diff(time.ticks_ms(), t0) / (DROWSY_TIME * 1000))
        droop = lid_frac(0.6 * p, lid_open)
        move([(lid, droop), (ud, clamp(UD_CENTRE - 5 - 15 * p, UD_DOWN, UD_UP)), (lr, LR_CENTRE)], 0.6)
        if doze(random.uniform(1.5, 3.0), reason):
            break
        move([(lid, LID_CLOSED)], 0.5)                     # slow heavy blink
        if doze(0.4, reason):
            break
        move([(lid, droop)], 0.7)
        if p >= 1.0:
            break
    if reason[0] is None:
        # --- asleep ---
        move([(lid, LID_CLOSED - 2), (ud, clamp(UD_CENTRE - 20, UD_DOWN, UD_UP))], 1.2)
        print("asleep")
        light_since = None
        while True:
            if doze(random.uniform(*SLEEP_TWITCH_GAP), reason):
                break
            if random.random() < SLEEP_STIR_CHANCE:      # sleepy stir: lids crack open and close again
                move([(lid, lid_frac(0.75))], 0.6)
                if doze(0.5, reason):
                    break
                move([(lid, LID_CLOSED - 2)], 0.8)
            else:                                        # small twitch under the lids
                move([(lr, clamp(lr.angle + random.uniform(-3, 3), LR_RIGHT, LR_LEFT)),
                      (ud, clamp(ud.angle + random.uniform(-3, 3), UD_DOWN, UD_UP))], 0.15)
    # --- waking ---
    print("waking:", reason[0])
    dark_since = None
    interruptible = True
    if reason[0] == "light":
        # make sure the light stays on for a moment before committing
        end = time.ticks_add(time.ticks_ms(), int(WAKE_LIGHT_TIME * 1000))
        while time.ticks_diff(time.ticks_ms(), end) < 0:
            v, _ = light_excess()
            if v <= dark_room + WAKE_RISE / 2:
                return go_to_sleep_again()
            time.sleep_ms(50)
        room = lit_room = light_excess()[0]                # the lights are on: this is the room level now
        struggle_awake("light")                            # ...but it takes a while to come round
    elif reason[0] == "sound":
        struggle_awake("sound")                            # jolted, then a hard time surfacing
    # 'dazzle': lids already shut; check_light() will run the dazzle performance and recover
    wake_done()


def go_to_sleep_again():
    """Light flickered but went dark again: drop straight back to sleep."""
    global interruptible
    interruptible = False
    move([(lid, LID_CLOSED - 2)], 1.0)
    print("back to sleep")
    reason = [None]
    while not doze(random.uniform(*SLEEP_TWITCH_GAP), reason):
        move([(lr, clamp(lr.angle + random.uniform(-3, 3), LR_RIGHT, LR_LEFT))], 0.15)
    interruptible = True
    if reason[0] == "light":
        return go_to_sleep()      # re-enter via the waking path (recurses at most a few times in practice)
    print("waking:", reason[0])
    if reason[0] == "sound":
        struggle_awake("sound")
    wake_done()


def check_sleep(v):
    """Track darkness (relative to the lit level, with hysteresis); sleep after DARK_TIME of it."""
    global dark_since, dark_room
    level = lit_room * DARK_FRACTION
    if dark_since is None:
        if v < level - DARK_HYST:
            dark_since = time.ticks_ms()
            print("dark... (%d < %d)" % (v, level))
    elif v > level + DARK_HYST:
        dark_since = None
        print("light again")
    elif time.ticks_diff(time.ticks_ms(), dark_since) > DARK_TIME * 1000:
        dark_room = v
        go_to_sleep()
        return True
    return False


# ---- Home: eye centred (slightly down), lids open - or asleep, if START_ASLEEP ----
REST_UD = UD_CENTRE - REST_DOWN
pretend_dark = False
if BOOT_ASLEEP:
    print("eye running (asleep: a clap wakes it)" if WAKE_SOUND_ONLY else
          "eye running (asleep: clap, or hold a light on it for a couple of seconds, to wake it)")
    pretend_dark = True
    dark_room = room                     # treat the current light as "dark"...
    lit_room = room / DARK_FRACTION      # ...so a modest rise in light (not only a dazzle) wakes it
    go_to_sleep(already_asleep=True)
else:
    move([(lr, LR_CENTRE), (ud, REST_UD), (lid, lid_for(REST_UD))], 0.5)
    time.sleep(0.5)
    print("eye running")

next_blink   = later(BLINK_GAP, skew=True)
fixation_end = later(FIX_SHORT)
next_micro   = later(MICRO_GAP)
scan_hops    = 0
long_stare   = False

def idle_step():
    """One step of normal behaviour: blink, glance, scan or micro-drift, whichever is due."""
    global next_blink, fixation_end, next_micro, scan_hops, long_stare
    if due(next_blink):
        blink()
        next_blink = later(BLINK_GAP, skew=True)

    elif due(fixation_end):
        if scan_hops > 0:                         # small hop near where we're looking
            scan_hops -= 1
            saccade(clamp(lr.angle + random.uniform(-SCAN_RADIUS, SCAN_RADIUS), LR_RIGHT, LR_LEFT),
                    clamp(ud.angle + random.uniform(-SCAN_RADIUS, SCAN_RADIUS), UD_DOWN, UD_UP))
            fixation_end = later(SCAN_FIX)
            long_stare = False
        else:                                     # a fresh look somewhere
            saccade(biased(LR_RIGHT, LR_CENTRE, LR_LEFT), biased(UD_DOWN, REST_UD, UD_UP))
            if random.random() < SCAN_CHANCE:
                scan_hops = random.randint(1, 2)
                fixation_end = later(SCAN_FIX)
                long_stare = False
            elif random.random() < LONG_STARE_CHANCE:
                fixation_end = later(FIX_LONG)
                long_stare = True
                next_micro = later(MICRO_GAP)
            else:
                fixation_end = later(FIX_SHORT)
                long_stare = False

    elif long_stare and due(next_micro):          # tiny drift so a stare isn't frozen
        move([(lr, clamp(lr.angle + random.uniform(-MICRO_DEG, MICRO_DEG), LR_RIGHT, LR_LEFT)),
              (ud, clamp(ud.angle + random.uniform(-MICRO_DEG, MICRO_DEG), UD_DOWN, UD_UP))], 0.1)
        next_micro = later(MICRO_GAP)

    time.sleep(0.01)


while True:
    if LIGHT_ENABLED and check_light():
        continue                                  # just finished a dazzle performance
    try:
        if SOUND_ENABLED and check_sound():
            continue                              # just startled (or redirected by a new clap)
        idle_step()
    except Interrupted:
        interruptible = True
        pass                                      # a clap cut a move short: loop round to check_sound()
