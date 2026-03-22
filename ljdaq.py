# LPC LABJACK T7 PYTHON CONFIG SCRIPT
# Author: Thomas Tedeschi
# Last Update Date: 3/22/2026

from labjack import ljm
from colorama import Fore, Style, init
import time
import numpy as np

# Open LabJack
mb = ljm.openS("T7", "ANY", "ANY")

# GLOBAL CONSTANTS
killed = False
timestamp = 0
celsius = 1
farenheit = 2
pastt = np.zeros(hist)
pastp = np.zeros(hist)
pastl = np.zeros(hist)
hist = 10
last_mc = 0
# pwm_freq = 
# kill_pin_num = 
# tpin_pos_num =
# tpin_neg_num =
# trng =
# trind =
# tset =
# ppin_num =
# prng =
# prind =
# lpin_num =
# lrng =
# lrind =
# pmax =
# pmin =
# kload =
# v_kload =
# res_val =
# arm_pin =
# fire_pin =
# ignite_out_pin =
# servo1_pwm_pin =
# servo2_pwm_pin =
# curpos =
# startval =
# openval =
# movact_pin_num
# closedval =
# lastfire =
# v_off
# fire_time

# ================================
# EXCEPTIONS
# ================================

class SystemFault(Exception):
    pass

# ================================
# CONFIG FUNCTIONS
# ================================

# --------------------------------------------------------
# Configures a thermocoupler to read differential voltage between
# ppin and npin. Rng is the max voltage this can read, rind is 
# the resolution of the measurement, sett is settling time
# and temp is the unit (e.g. celsius or farenheit)
# --------------------------------------------------------

def configure_thermocouple(ppin, npin, rng, rind, sett, temp):
    pos_name = f"AIN{ppin}"
    neg_name = f"AIN{ppin}_NEGATIVE_CH"

    ljm.eWriteName(mb, neg_name, npin)
    ljm.eWriteName(mb, f"{pos_name}_RANGE", rng)
    ljm.eWriteName(mb, f"{pos_name}_RESOLUTION_INDEX", rind)
    ljm.eWriteName(mb, f"{pos_name}_SETTLING_US", sett)
    ljm.eWriteName(mb, f"{pos_name}_EF_INDEX", 22)
    ljm.eWriteName(mb, f"{pos_name}_EF_CONFIG_A", temp)

# --------------------------------------------------------
# Configures either a transducer or a loadcell since they
# are done the same. Connects to AIN apin with range rng 
# and resolution rind. The voltage is compared to GND.
#---------------------------------------------------------
def configure_transducer_loadcell(apin, rng, rind):
    ain_name = f"AIN{apin}"
    ljm.eWriteName(mb, f"{ain_name}_NEGATIVE_CH", 199)
    ljm.eWriteName(mb, f"{ain_name}_RANGE", rng)
    ljm.eWriteName(mb, f"{ain_name}_RESOLUTION_INDEX", rind)
    ljm.eWriteName(mb, f"{ain_name}_SETTLING_US", 0)

# --------------------------------------------------------
# Configures a pin as digital I/O, with the function func.
# func MUST BE either 'input' or 'ouput'.
# --------------------------------------------------------
def configure_digital_io(diopin_num, func):
    if func == "input":
        ljm.eWriteName(mb, f"DIO{diopin_num}_DIRECTION", 0)
    else:
        ljm.eWriteName(mb, f"DIO{diopin_num}_DIRECTION", 1)
        ljm.eWriteName(mb, f"DIO{diopin_num}_STATE", 0)


def configure_clock(freq):
    ljm.eWriteName(mb, "DIO_EF_CLOCK0_ENABLE", 0)
    ljm.eWriteName(mb, "DIO_EF_CLOCK0_DIVISOR", 1)
    ljm.eWriteName(mb, "DIO_EF_CLOCK0_ROLL_VALUE", 80000000/freq)
    ljm.eWriteName(mb, "DIO_EF_CLOCK0_ENABLE", 1)

# --------------------------------------------------------
# Configures a DIO pin to output pwm at 50 HZ and start
# value startval
# --------------------------------------------------------
def configure_pwm(diopin_num, startval):
    ljm.eWriteName(mb, f"DIO{diopin_num}_EF_ENABLE", 0)
    ljm.eWriteName(mb, f"DIO{diopin_num}_EF_INDEX", 0)
    ljm.eWriteName(mb, f"DIO{diopin_num}_EF_OPTIONS", 0)
    ljm.eWriteName(mb, f"DIO{diopin_num}_EF_CONFIG_A", startval)
    ljm.eWriteName(mb, f"DIO{diopin_num}_EF_ENABLE", 1)

# ================================
# MEASUREMENT FUNCTIONS
# ================================

# --------------------------------------------------------
# Measures and returns transducer current by diving measured 
# voltage by known resistance (Ohm's Law).
# --------------------------------------------------------
def measure_transducer_current(apin, resistance):
    voltage = ljm.eReadName(mb, f"AIN{apin}")
    return voltage / resistance

# --------------------------------------------------------
# Converts transducer current to pressure and returns
# --------------------------------------------------------
def current_to_pressure(current, pmin, pmax):
    return ((current - 0.004) / 0.016) * (pmax - pmin) + pmin

# --------------------------------------------------------
# Measures the temperature by reading TC pin. Returns temp.
# --------------------------------------------------------
def read_temperature(tpin):
    return ljm.eReadName(mb, f"AIN{tpin}_EF_READ_A")

# --------------------------------------------------------
# Calculates and returns the pressure using the current 
# and conversion functions.
# --------------------------------------------------------
def read_pressure(prpin, resis, p_min, p_max):
    c = measure_transducer_current(prpin, resis)
    return current_to_pressure(c, p_min, p_max)

# --------------------------------------------------------
# Reads the load cell load using by calculating a scaling
# factor with a known load and its voltage as well as the 
# offset (0 load) voltage and using a formula with the 
# measured pin voltage.
# --------------------------------------------------------
def read_load(ldpin, v_off, kload, v_kload):
    factor = kload / (v_kload - v_off)
    pin_v = ljm.eReadName(mb, f"AIN{ldpin}")
    return (pin_v - v_off) * factor

# ================================
# DIGITAL / SERVO FUNCTIONS
# ================================

# --------------------------------------------------------
# Moves the servo motors between two positons. nextpos 
# MUST BE either 'open' or 'closed'. Returns whether motor
# moved, prints error if there is one.
# --------------------------------------------------------
def move(diopin_num, nextpos):
    global curpos
    if nextpos == curpos:
        print(Fore.RED + "MOVE COMMAND FAILED: ALREADY " + curpos.upper())
        return False
    if nextpos == "open":
        ljm.eWriteName(mb, f"DIO{diopin_num}_EF_CONFIG_A", openval)
        curpos = nextpos
        return True
    elif nextpos == "closed":
        ljm.eWriteName(mb, f"DIO{diopin_num}_EF_CONFIG_A", closedval)
        curpos = nextpos
        return True
    else:
        print(Fore.RED + "MOVE COMMAND FAILED: " + str(nextpos.upper()) + " INVALID MOVEMENT COMMAND")
        return False
    
def detect_move(pin):
    if dread(pin) == 1 and last_mc == 0:
        return True
    return False

def moveseq1(pin1):
    # TBD
    pass

def moveseq2(pin2):
    # TBD
    pass

# --------------------------------------------------------
# Reads from DIO Pin.
# --------------------------------------------------------
def dread(diopin_num):
    return ljm.eReadName(mb, f"DIO{diopin_num}")

# --------------------------------------------------------
# Writes to DIO Pin, 0 for input, 1 for output.
# --------------------------------------------------------
def dwrite(diopin_num, state):
    ljm.eWriteName(mb, f"DIO{diopin_num}_STATE", state)

# ================================
# IGNITION FUNCTIONS
# ================================

# --------------------------------------------------------
# Checks if armed, and measurements are within range before
# firing.
# --------------------------------------------------------
def is_ignition_safe(a, p, t, l, mp, mt, ml, mip, mit, mil):
    if not a:
        print(Fore.RED + "IGNITION FAILURE: SYSTEM NOT ARMED")
        return False
    if p > mp or p < mip:
        print(Fore.RED + "IGNITION FAILURE: PRESSURE TOO LARGE")
        return False
    if t > mt or t < mit:
        print(Fore.RED + "IGNITION FAILURE: TEMPERATURE TOO HIGH")
        return False
    if l > ml or l < mil:
        print(Fore.RED + "IGNITION FAILURE: LOAD TOO HIGH")
        return False
    return True

# --------------------------------------------------------
# Control function for firing, checking safety before
# firing and handling the result.
# --------------------------------------------------------
def fire_control(ipin, ftime, a, p, t, l, mp, mt, ml, mip, mit, mil):
    if is_ignition_safe(a, p, t, l, mp, mt, ml, mip, mit, mil):
        if lastfire == 0:
            print(Fore.YELLOW + "IGNITION ACTIVE")
            fire(ipin, ftime)
            print(Fore.YELLOW + "IGNITION COMPLETE")
            return True
        else:
            print(Fore.RED + "IGNITION FAILED: NO CONSECUTIVE IGNITES")
            return False
    else:
        return False

# --------------------------------------------------------
# Fires for time ftime.
# --------------------------------------------------------
def fire(ipin, ftime):
    dwrite(ipin, 1)
    time.sleep(ftime)
    dwrite(ipin, 0)

# ================================
# SAFETY FUNCTIONS
# ================================

def check_temperature(history, temperature):
    sum = 0
    for i in history:
        sum += i
    sum = (sum+temperature)/(hist+1)
    if sum > max_temp or sum < min_temp:
        return False
    return True

def check_pressure(history, pressure):
    sum = 0
    for i in history:
        sum += i
    sum = (sum+pressure)/(hist+1)
    if sum > max_pres or sum < min_pres:
        return False
    return True

def check_load(history, load):
    sum = 0
    for i in history:
        sum += i
    sum = (sum+load)/(hist+1)
    if sum > max_load or sum < min_load:
        return False
    return True

def kill(safet, safep, safel, kill_pin):
    dwrite(kill_pin, 0)
    if not safet:
        return Fore.RED + "ABORTING: TEMPERATURE UNSAFE. PLEASE RESET SYSTEM ONCE MANUALLY CONFIRMED SAFE"
    if not safep:
        return Fore.RED + "ABORTING: PRESSURE UNSAFE. PLEASE RESET SYSTEM ONCE MANUALLY CONFIRMED SAFE"
    if not safel:
        return Fore.RED + "ABORTING: LOAD UNSAFE. PLEASE RESET SYSTEM ONCE MANUALLY CONFIRMED SAFE"
    
# ================================
# CONFIGURATION
# ================================

# Configure Temperature Sensing
configure_thermocouple(tpin_pos_num, tpin_neg_num, trng, trind, tset, celsius)
# Configure Pressure Sensing
configure_transducer_loadcell(ppin_num, prng, prind)
# Configure Load Sensing
configure_transducer_loadcell(lpin_num, lrng, lrind)
# Configure the Servo Pins
configure_clock(pwm_freq)
configure_digital_io(servo1_pwm_pin, "output")
configure_pwm(servo1_pwm_pin, startval)
configure_digital_io(servo2_pwm_pin, "output")
configure_pwm(servo2_pwm_pin, startval)
configure_digital_io(movact_pin_num, "input")
# Configure ignition pins
configure_digital_io(fire_pin, "input")
configure_digital_io(ignite_out_pin, "output")
configure_digital_io(fire_pin, "input")

# ================================
# MAIN LOOP 
# ================================

while not killed:
    temp = read_temperature(tpin_pos_num)
    pres = read_pressure(ppin_num, res_val, pmin, pmax)
    load = read_load(lpin_num, v_off, kload, v_kload)

    warn = 0
    safet = True
    safep = True
    safel = True
    if temp > max_temp or temp < min_temp:
        warn = 1
        safet = check_temperature(pastt, temp)
    if pres > max_pres or pres < min_pres:
        warn = 1
        safep = check_pressure(pastp, pres)
    if load > max_load or load < min_load:
        warn = 1
        safel = check_load(pastl, load)  
    if warn:
        if not (safet and safep and safel):
            kill_message = kill(safet, safep, safel, kill_pin_num)  
            killed = True
            raise SystemFault(kill_message)
        else:
            print(Fore.YELLOW + "WARNING: POTENTIALLY UNSAFE CONDITIONS")

    if not killed:
        idx = timestamp%hist
        pastt[idx] = temp
        pastp[idx] = pres
        pastl[idx] = load
        armed = (dread(arm_pin) == 1)
        firing = (dread(fire_pin) == 1)

        if firing:
            if timestamp < hist:
                did_fire = fire_control(ignite_out_pin, fire_time, armed, pres, temp, load, max_pres, max_temp, max_load, min_pres, min_temp, min_load)
                lastfire = int(did_fire)
            else:
                print(Fore.RED + "IGNITION FAILED: SYSTEM NOT READY")
                lastfire = 0
        
        movcom = detect_move(movact_pin_num)
        if movcom:
            movseq1(servo1_pwm_pin)
            movseq2(servo2_pwm_pin)

        print(Fore.GREEN + "Temperature (C):", temp)
        print(Fore.GREEN + "Pressure (psi):", pres)
        print(Fore.GREEN + "Force:", load)

        timestamp += 1
        time.sleep(0.1)