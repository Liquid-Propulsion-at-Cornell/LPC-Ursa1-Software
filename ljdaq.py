# LPC LABJACK T7 PYTHON CONFIG SCRIPT
# Author: Thomas Tedeschi
# Last Update Date: 4/25/2026

import threading
import copy
import time
import numpy as np
from dataclasses import dataclass
from labjack import ljm
from colorama import Fore, Style, init

mb = ljm.openS("T7", "ANY", "ANY")

# ================================
# FSM STATES
# ================================
STATE_ABORT           = 0
STATE_COLD_OPS        = 1
STATE_PRE_FIRE_PURGE  = 2
STATE_FILL            = 3
STATE_STATE_CHECK     = 4
STATE_HOT_FIRE        = 5
STATE_POST_FIRE_PURGE = 6
STATE_VENT_SAFING     = 7

# ================================
# UNIT CONSTANTS
# ================================
CELSIUS    = 1
FAHRENHEIT = 2

# ================================
# HARDWARE PIN ASSIGNMENTS
# ================================
# pwm_freq =
# tc1_pin_pos =
# tc1_pin_neg =
# tc2_pin_pos =
# tc2_pin_neg =
# tc_rng =
# tc_rind =
# tc_sett =
# pt1_pin =        # Fuel tank PT
# pt2_pin =        # Ox tank PT
# pt3_pin =        # Chamber PT
# pt4_pin =        # Supply PT
# pt_rng =
# pt_rind =
# pt_res_val =     # shunt resistor (ohms)
# lc_pin =
# lc_rng =
# lc_rind =
# v_off =          # load cell zero voltage
# kload =          # known calibration load (units)
# v_kload =        # voltage at kload
# v1_pin =         # Main Fuel valve     (two-way, powered=OPEN)
# v2_pin =         # Main Ox valve       (two-way, powered=OPEN)
# v3_pin =         # Fill valve          (two-way, powered=OPEN)
# v4_pin =         # Purge A             (two-way, powered=OPEN)
# v5_pin =         # Purge B             (two-way, powered=OPEN)
# v6_pin =         # Vent                (auto-return, unpowered=OPEN, powered=CLOSED)
# v1_open_pwm =
# v1_close_pwm =
# v2_open_pwm =
# v2_close_pwm =
# v3_open_pwm =
# v3_close_pwm =
# v4_open_pwm =
# v4_close_pwm =
# v5_open_pwm =
# v5_close_pwm =
# v6_close_pwm =   # V6 has no open_pwm — dropping EF enable is how it opens
# ignite_pin =
# kill_pin =       # digital output: normally HIGH; write LOW on abort to cut main 12V bus
# start_pin =      # digital input: rising edge starts sequence (STATE 1 → 2)
# arm_pin =        # digital input: rising edge in STATE 4 authorizes fire

# startval =       # initial PWM value written to all servo pins on boot

# ================================
# SEQUENCE TIMING
# ================================
# Purge_Time =              # seconds — pre/post fire purge duration
# Delay_1 =                 # seconds — igniter ON → V1 open
# Delay_2 =                 # seconds — V1 open → V2 open
# Burn_Duration =           # seconds — V2 open → close all + igniter off
# Ignition_Confirm_Time =   # seconds — window after V2 open to confirm ignition

# ================================
# PRESSURE PARAMETERS
# ================================
# pt1_pmin =   pt1_pmax =   # Fuel tank PT range (psi)
# pt2_pmin =   pt2_pmax =   # Ox tank PT range (psi)
# pt3_pmin =   pt3_pmax =   # Chamber PT range (psi)
# pt4_pmin =   pt4_pmax =   # Supply PT range (psi)
# MEOP =                    # Ox tank fill cutoff pressure (psi)
# Max_Chamber_Pressure =    # Hard start abort limit (psi)
# Min_Ignition_Pressure =   # Min chamber pressure after V2 open to confirm ignition

# ================================
# SAFETY THRESHOLDS
# ================================
# warn_temp_max =    warn_temp_min =
# fault_temp_max =   fault_temp_min =
# warn_pres_max =    warn_pres_min =
# fault_pres_max =   fault_pres_min =
# warn_load_max =    warn_load_min =
# fault_load_max =   fault_load_min =
# max_temp_rate =    # max per-sample delta before fault
# max_pres_rate =
# max_load_rate =
# amb =              # expected ambient temperature (C) for cold ops / vent safing checks
# tdiff =            # allowable TC deviation from ambient (C)
# pdiff =            # allowable PT deviation from 0 psig

HIST           = 10
REQUIRED_SAFE  = 5
SAMPLE_PERIOD  = 0.001   # 1 kHz
CONTROL_PERIOD = 0.001   # 1 kHz


# ================================
# SENSOR SNAPSHOT
# Scalar-only; history arrays live inside sampling_loop.
# ================================
@dataclass
class SensorSnapshot:
    tc1:       float = 0.0
    tc2:       float = 0.0
    pt1:       float = 0.0
    pt2:       float = 0.0
    pt3:       float = 0.0
    pt4:       float = 0.0
    load:      float = 0.0
    timestamp: int   = 0


# ================================
# RUNTIME FSM STATE
# Owned exclusively by control_loop; sampling_loop reads system_state under state_lock.
# ================================
system_state    = STATE_COLD_OPS
state_timer     = -1.0
hot_fire_step   = 0
ignite          = False
fire_authorized = False


# ================================
# THREAD SYNCHRONIZATION
# ================================
sensor_lock  = threading.Lock()   # guards latest_sensors reads/writes
state_lock   = threading.Lock()   # guards system_state reads/writes
abort_event  = threading.Event()  # set by either thread on fault or interrupt
abort_reason = ""                 # written under state_lock before setting event

latest_sensors = SensorSnapshot()


# ================================
# CONFIG FUNCTIONS
# ================================

def configure_thermocouple(ppin, npin, rng, rind, sett, temp_unit):
    pos_name = f"AIN{ppin}"
    ljm.eWriteName(mb, f"AIN{ppin}_NEGATIVE_CH", npin)
    ljm.eWriteName(mb, f"{pos_name}_RANGE", rng)
    ljm.eWriteName(mb, f"{pos_name}_RESOLUTION_INDEX", rind)
    ljm.eWriteName(mb, f"{pos_name}_SETTLING_US", sett)
    ljm.eWriteName(mb, f"{pos_name}_EF_INDEX", 22)
    ljm.eWriteName(mb, f"{pos_name}_EF_CONFIG_A", temp_unit)

def configure_transducer_loadcell(apin, rng, rind):
    ain_name = f"AIN{apin}"
    ljm.eWriteName(mb, f"{ain_name}_NEGATIVE_CH", 199)
    ljm.eWriteName(mb, f"{ain_name}_RANGE", rng)
    ljm.eWriteName(mb, f"{ain_name}_RESOLUTION_INDEX", rind)
    ljm.eWriteName(mb, f"{ain_name}_SETTLING_US", 0)

def configure_digital_io(diopin_num, func):
    if func == "input":
        ljm.eWriteName(mb, f"DIO{diopin_num}_DIRECTION", 0)
    else:
        ljm.eWriteName(mb, f"DIO{diopin_num}_DIRECTION", 1)
        ljm.eWriteName(mb, f"DIO{diopin_num}_STATE", 0)

def configure_clock(freq):
    ljm.eWriteName(mb, "DIO_EF_CLOCK0_ENABLE", 0)
    ljm.eWriteName(mb, "DIO_EF_CLOCK0_DIVISOR", 1)
    ljm.eWriteName(mb, "DIO_EF_CLOCK0_ROLL_VALUE", 80000000 / freq)
    ljm.eWriteName(mb, "DIO_EF_CLOCK0_ENABLE", 1)

def configure_pwm(diopin_num, val):
    ljm.eWriteName(mb, f"DIO{diopin_num}_EF_ENABLE", 0)
    ljm.eWriteName(mb, f"DIO{diopin_num}_EF_INDEX", 0)
    ljm.eWriteName(mb, f"DIO{diopin_num}_EF_OPTIONS", 0)
    ljm.eWriteName(mb, f"DIO{diopin_num}_EF_CONFIG_A", val)
    ljm.eWriteName(mb, f"DIO{diopin_num}_EF_ENABLE", 1)


# ================================
# MEASUREMENT FUNCTIONS
# ================================

def measure_transducer_current(apin, resistance):
    return ljm.eReadName(mb, f"AIN{apin}") / resistance

def current_to_pressure(current, pmin, pmax):
    return ((current - 0.004) / 0.016) * (pmax - pmin) + pmin

def read_temperature(tpin):
    return ljm.eReadName(mb, f"AIN{tpin}_EF_READ_A")

def read_pressure(prpin, resis, p_min, p_max):
    return current_to_pressure(measure_transducer_current(prpin, resis), p_min, p_max)

def read_load(ldpin, v_off, kload, v_kload):
    factor = kload / (v_kload - v_off)
    return (ljm.eReadName(mb, f"AIN{ldpin}") - v_off) * factor


# ================================
# VALVE / SERVO FUNCTIONS
# ================================

def move(pin, target, open_pwm, close_pwm):
    if target == "open":
        ljm.eWriteName(mb, f"DIO{pin}_EF_CONFIG_A", open_pwm)
    elif target == "closed":
        ljm.eWriteName(mb, f"DIO{pin}_EF_CONFIG_A", close_pwm)
    else:
        print(Fore.RED + f"MOVE FAILED: INVALID TARGET '{target}'")

def v6_power_closed():
    ljm.eWriteName(mb, f"DIO{v6_pin}_EF_CONFIG_A", v6_close_pwm)

def v6_release():
    ljm.eWriteName(mb, f"DIO{v6_pin}_EF_ENABLE", 0)

def dread(diopin_num):
    return ljm.eReadName(mb, f"DIO{diopin_num}")

def dwrite(diopin_num, state):
    ljm.eWriteName(mb, f"DIO{diopin_num}_STATE", state)


# ================================
# IGNITION FUNCTIONS
# ================================

def fire_on():
    global ignite
    dwrite(ignite_pin, 1)
    ignite = True
    print(Fore.YELLOW + "IGNITION ACTIVE")

def fire_off():
    global ignite
    dwrite(ignite_pin, 0)
    ignite = False
    print(Fore.YELLOW + "IGNITION OFF")


# ================================
# SAFETY FUNCTIONS
# History arrays are local to sampling_loop and passed in explicitly.
# ================================

def check_rate_of_change(history, current, max_delta, ts):
    if ts == 0:
        return True
    last = history[(ts - 1) % HIST]
    return abs(current - last) <= max_delta

def check_sensor_avg(history, current, lo, hi, ts):
    count = min(ts, HIST)
    avg = (np.sum(history[:count]) + current) / (count + 1)
    return lo <= avg <= hi

def run_safety_checks(snap, pastt1, pastt2, pastp1, pastp2, pastp3, pastp4, pastl, cur_state):
    ts = snap.timestamp

    if cur_state != STATE_HOT_FIRE:
        for t, h in zip([snap.tc1, snap.tc2], [pastt1, pastt2]):
            if not check_rate_of_change(h, t, max_temp_rate, ts):
                return False, "TEMPERATURE RATE OF CHANGE EXCEEDED"
            if not check_sensor_avg(h, t, fault_temp_min, fault_temp_max, ts):
                return False, "TEMPERATURE OUT OF FAULT BOUNDS"
            if not (warn_temp_min <= t <= warn_temp_max):
                print(Fore.YELLOW + "WARNING: TEMPERATURE APPROACHING LIMITS")

        for p, h in zip([snap.pt1, snap.pt2, snap.pt3, snap.pt4],
                        [pastp1,   pastp2,   pastp3,   pastp4]):
            if not check_rate_of_change(h, p, max_pres_rate, ts):
                return False, "PRESSURE RATE OF CHANGE EXCEEDED"
            if not check_sensor_avg(h, p, fault_pres_min, fault_pres_max, ts):
                return False, "PRESSURE OUT OF FAULT BOUNDS"
            if not (warn_pres_min <= p <= warn_pres_max):
                print(Fore.YELLOW + "WARNING: PRESSURE APPROACHING LIMITS")

    if not check_rate_of_change(pastl, snap.load, max_load_rate, ts):
        return False, "LOAD RATE OF CHANGE EXCEEDED"
    if not check_sensor_avg(pastl, snap.load, fault_load_min, fault_load_max, ts):
        return False, "LOAD OUT OF FAULT BOUNDS"
    if not (warn_load_min <= snap.load <= warn_load_max):
        print(Fore.YELLOW + "WARNING: LOAD APPROACHING LIMITS")

    return True, ""

def update_history(snap, pastt1, pastt2, pastp1, pastp2, pastp3, pastp4, pastl):
    idx = snap.timestamp % HIST
    pastt1[idx] = snap.tc1
    pastt2[idx] = snap.tc2
    pastp1[idx] = snap.pt1
    pastp2[idx] = snap.pt2
    pastp3[idx] = snap.pt3
    pastp4[idx] = snap.pt4
    pastl[idx]  = snap.load


# ================================
# ABORT
# Non-blocking: sets reason + event. control_loop runs hardware shutdown on exit.
# ================================

def abort(reason=""):
    global abort_reason
    with state_lock:
        abort_reason = reason
    abort_event.set()
    print(Fore.RED + ("ABORT" + (f": {reason}" if reason else "")))
    print(Fore.RED + "MANUAL RESET REQUIRED")

def _do_abort_hardware():
    global system_state
    move(v1_pin, "closed", v1_open_pwm, v1_close_pwm)
    move(v2_pin, "closed", v2_open_pwm, v2_close_pwm)
    move(v3_pin, "closed", v3_open_pwm, v3_close_pwm)
    move(v4_pin, "closed", v4_open_pwm, v4_close_pwm)
    move(v5_pin, "closed", v5_open_pwm, v5_close_pwm)
    v6_release()
    fire_off()
    dwrite(kill_pin, 0)
    with state_lock:
        system_state = STATE_ABORT

def transition_to(new_state):
    global system_state, state_timer
    with state_lock:
        system_state = new_state
    state_timer = -1.0


# ================================
# FSM STATE HANDLERS
# All read-only on snap. state_timer / hot_fire_step / fire_authorized are
# private to control_loop — no lock needed for those.
# ================================

# STATE 1: COLD OPS
def handle_cold_ops(snap):
    pts_at_zero = all(abs(p) <= pdiff for p in [snap.pt1, snap.pt2, snap.pt3, snap.pt4])
    tcs_at_amb  = all(amb - tdiff <= t <= amb + tdiff for t in [snap.tc1, snap.tc2])
    if pts_at_zero and tcs_at_amb:
        if dread(start_pin) == 1:
            transition_to(STATE_PRE_FIRE_PURGE)
            print(Fore.CYAN + "STATE 2: PRE-FIRE PURGE")
    else:
        if not pts_at_zero:
            print(Fore.YELLOW + "COLD OPS: PTs NOT AT ZERO — WAITING")
        if not tcs_at_amb:
            print(Fore.YELLOW + "COLD OPS: TCs NOT AT AMBIENT — WAITING")

# STATE 2: PRE-FIRE PURGE
def handle_pre_fire_purge(snap):
    global state_timer
    if state_timer < 0:
        move(v4_pin, "open", v4_open_pwm, v4_close_pwm)
        move(v5_pin, "open", v5_open_pwm, v5_close_pwm)
        state_timer = time.time()
        return
    for p in [snap.pt1, snap.pt2, snap.pt3, snap.pt4]:
        if p > warn_pres_max:
            abort("ANOMALOUS BACK-PRESSURE DURING PRE-FIRE PURGE")
            return
    if time.time() - state_timer >= Purge_Time:
        move(v4_pin, "closed", v4_open_pwm, v4_close_pwm)
        move(v5_pin, "closed", v5_open_pwm, v5_close_pwm)
        transition_to(STATE_FILL)
        print(Fore.CYAN + "STATE 3: FILL")

# STATE 3: FILL
def handle_fill(snap):
    global state_timer
    if state_timer < 0:
        v6_power_closed()
        move(v3_pin, "open", v3_open_pwm, v3_close_pwm)
        state_timer = time.time()
        return
    if snap.pt2 >= MEOP:
        move(v3_pin, "closed", v3_open_pwm, v3_close_pwm)
        transition_to(STATE_STATE_CHECK)
        print(Fore.CYAN + "STATE 4: STATE CHECK — OX TANK AT MEOP")

# STATE 4: STATE CHECK
def handle_state_check(snap):
    global fire_authorized
    softsafe = (
        all(fault_temp_min <= t <= fault_temp_max for t in [snap.tc1, snap.tc2]) and
        all(fault_pres_min <= p <= fault_pres_max for p in [snap.pt1, snap.pt2, snap.pt3, snap.pt4])
    )
    if not softsafe:
        print(Fore.RED + "STATE CHECK: SENSORS NOT IN GO RANGE — HOLD")
        return
    if not fire_authorized:
        print(Fore.GREEN + "ALL SENSORS GO — AWAITING FIRE AUTHORIZATION (arm_pin)")
        fire_authorized = (dread(arm_pin) == 1)
    if fire_authorized:
        transition_to(STATE_HOT_FIRE)
        print(Fore.YELLOW + "STATE 5: HOT FIRE SEQUENCE INITIATED")

# STATE 5: HOT FIRE
def handle_hot_fire(snap):
    global hot_fire_step, state_timer
    if hot_fire_step == 0:
        fire_on()
        state_timer   = time.time()
        hot_fire_step = 1
    elif hot_fire_step == 1:
        if snap.pt3 > Max_Chamber_Pressure:
            abort("HARD START — CHAMBER PRESSURE EXCEEDED LIMIT")
            hot_fire_step = 0
            return
        if time.time() - state_timer >= Delay_1:
            move(v1_pin, "open", v1_open_pwm, v1_close_pwm)
            state_timer   = time.time()
            hot_fire_step = 2
    elif hot_fire_step == 2:
        if snap.pt3 > Max_Chamber_Pressure:
            abort("HARD START — CHAMBER PRESSURE EXCEEDED LIMIT")
            hot_fire_step = 0
            return
        if time.time() - state_timer >= Delay_2:
            move(v2_pin, "open", v2_open_pwm, v2_close_pwm)
            state_timer   = time.time()
            hot_fire_step = 3
    elif hot_fire_step == 3:
        if snap.pt3 > Max_Chamber_Pressure:
            abort("HARD START — CHAMBER PRESSURE EXCEEDED LIMIT")
            hot_fire_step = 0
            return
        elapsed = time.time() - state_timer
        if elapsed >= Ignition_Confirm_Time and snap.pt3 < Min_Ignition_Pressure:
            abort("IGNITION FAILURE — NO CHAMBER PRESSURE AFTER VALVE OPEN")
            hot_fire_step = 0
            return
        if elapsed >= Burn_Duration:
            move(v1_pin, "closed", v1_open_pwm, v1_close_pwm)
            move(v2_pin, "closed", v2_open_pwm, v2_close_pwm)
            fire_off()
            hot_fire_step = 0
            transition_to(STATE_POST_FIRE_PURGE)
            print(Fore.CYAN + "STATE 6: POST-FIRE PURGE")

# STATE 6: POST-FIRE PURGE
def handle_post_fire_purge(snap):
    global state_timer
    if state_timer < 0:
        move(v4_pin, "open", v4_open_pwm, v4_close_pwm)
        move(v5_pin, "open", v5_open_pwm, v5_close_pwm)
        state_timer = time.time()
        return
    if abs(snap.pt3) <= pdiff:
        move(v4_pin, "closed", v4_open_pwm, v4_close_pwm)
        move(v5_pin, "closed", v5_open_pwm, v5_close_pwm)
        transition_to(STATE_VENT_SAFING)
        print(Fore.CYAN + "STATE 7: VENT & SAFING")

# STATE 7: VENT & SAFING
def handle_vent_safing(snap):
    global state_timer
    if state_timer < 0:
        v6_release()
        state_timer = time.time()
        return
    pts_safe = all(abs(p) <= pdiff for p in [snap.pt1, snap.pt2, snap.pt3, snap.pt4])
    tcs_safe = all(amb - tdiff <= t <= amb + tdiff for t in [snap.tc1, snap.tc2])
    if pts_safe and tcs_safe:
        print(Fore.GREEN + "PAD SAFE")


# ================================
# CONFIGURATION
# ================================
configure_thermocouple(tc1_pin_pos, tc1_pin_neg, tc_rng, tc_rind, tc_sett, CELSIUS)
configure_thermocouple(tc2_pin_pos, tc2_pin_neg, tc_rng, tc_rind, tc_sett, CELSIUS)
configure_transducer_loadcell(pt1_pin, pt_rng, pt_rind)
configure_transducer_loadcell(pt2_pin, pt_rng, pt_rind)
configure_transducer_loadcell(pt3_pin, pt_rng, pt_rind)
configure_transducer_loadcell(pt4_pin, pt_rng, pt_rind)
configure_transducer_loadcell(lc_pin, lc_rng, lc_rind)
configure_clock(pwm_freq)
for pin in [v1_pin, v2_pin, v3_pin, v4_pin, v5_pin, v6_pin]:
    configure_digital_io(pin, "output")
    configure_pwm(pin, startval)
configure_digital_io(ignite_pin, "output")
configure_digital_io(kill_pin,   "output")
ljm.eWriteName(mb, f"DIO{kill_pin}_STATE", 1)  # bus live at startup
configure_digital_io(arm_pin,    "input")
configure_digital_io(start_pin,  "input")


# ================================
# THREADS
# ================================

def sampling_loop():
    pastt1 = np.zeros(HIST)
    pastt2 = np.zeros(HIST)
    pastp1 = np.zeros(HIST)
    pastp2 = np.zeros(HIST)
    pastp3 = np.zeros(HIST)
    pastp4 = np.zeros(HIST)
    pastl  = np.zeros(HIST)
    ts = 0

    while not abort_event.is_set():
        snap = SensorSnapshot(
            tc1       = read_temperature(tc1_pin_pos),
            tc2       = read_temperature(tc2_pin_pos),
            pt1       = read_pressure(pt1_pin, pt_res_val, pt1_pmin, pt1_pmax),
            pt2       = read_pressure(pt2_pin, pt_res_val, pt2_pmin, pt2_pmax),
            pt3       = read_pressure(pt3_pin, pt_res_val, pt3_pmin, pt3_pmax),
            pt4       = read_pressure(pt4_pin, pt_res_val, pt4_pmin, pt4_pmax),
            load      = read_load(lc_pin, v_off, kload, v_kload),
            timestamp = ts,
        )

        with state_lock:
            cur_state = system_state

        if cur_state not in (STATE_ABORT, STATE_VENT_SAFING):
            safe, reason = run_safety_checks(
                snap, pastt1, pastt2, pastp1, pastp2, pastp3, pastp4, pastl, cur_state
            )
            if not safe:
                abort(reason)

        update_history(snap, pastt1, pastt2, pastp1, pastp2, pastp3, pastp4, pastl)

        with sensor_lock:
            latest_sensors.tc1       = snap.tc1
            latest_sensors.tc2       = snap.tc2
            latest_sensors.pt1       = snap.pt1
            latest_sensors.pt2       = snap.pt2
            latest_sensors.pt3       = snap.pt3
            latest_sensors.pt4       = snap.pt4
            latest_sensors.load      = snap.load
            latest_sensors.timestamp = ts

        print(Fore.GREEN + f"TC1: {snap.tc1:.1f}C  TC2: {snap.tc2:.1f}C")
        print(Fore.GREEN + f"PT1: {snap.pt1:.1f}  PT2: {snap.pt2:.1f}  PT3: {snap.pt3:.1f}  PT4: {snap.pt4:.1f} psi")
        print(Fore.GREEN + f"Load: {snap.load:.2f}  State: {cur_state}")

        ts += 1
        time.sleep(SAMPLE_PERIOD)


def control_loop():
    while not abort_event.is_set():
        with sensor_lock:
            snap = copy.copy(latest_sensors)

        with state_lock:
            cur_state = system_state

        if cur_state == STATE_COLD_OPS:
            handle_cold_ops(snap)
        elif cur_state == STATE_PRE_FIRE_PURGE:
            handle_pre_fire_purge(snap)
        elif cur_state == STATE_FILL:
            handle_fill(snap)
        elif cur_state == STATE_STATE_CHECK:
            handle_state_check(snap)
        elif cur_state == STATE_HOT_FIRE:
            handle_hot_fire(snap)
        elif cur_state == STATE_POST_FIRE_PURGE:
            handle_post_fire_purge(snap)
        elif cur_state == STATE_VENT_SAFING:
            handle_vent_safing(snap)

        time.sleep(CONTROL_PERIOD)

    _do_abort_hardware()


# ================================
# ENTRY POINT
# ================================
if __name__ == "__main__":
    sampler    = threading.Thread(target=sampling_loop, daemon=True, name="sampling")
    controller = threading.Thread(target=control_loop,  daemon=True, name="control")
    sampler.start()
    controller.start()
    try:
        while not abort_event.is_set():
            abort_event.wait(timeout=0.1)
    except KeyboardInterrupt:
        abort("KEYBOARD INTERRUPT")
    finally:
        abort_event.set()
        sampler.join(timeout=2.0)
        controller.join(timeout=2.0)
        ljm.close(mb)
