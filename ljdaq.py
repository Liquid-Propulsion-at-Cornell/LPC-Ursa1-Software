# LPC LABJACK T7 PYTHON CONFIG SCRIPT
# Author: Thomas Tedeschi
# Last Update Date: 3/21/2026

from labjack import ljm
from colorama import Fore, Style, init
import time

# Open LabJack
handle = ljm.openS("T7", "ANY", "ANY")

# GLOBAL CONSTANTS
killed = False
timestamp = 0
celsius = 1
farenheit = 2
pastt = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
pastp = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
pastl = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
hist = 10
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
# closedval =
# lastfire =

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

    ljm.eWriteName(handle, neg_name, npin)
    ljm.eWriteName(handle, f"{pos_name}_RANGE", rng)
    ljm.eWriteName(handle, f"{pos_name}_RESOLUTION_INDEX", rind)
    ljm.eWriteName(handle, f"{pos_name}_SETTLING_US", sett)
    ljm.eWriteName(handle, f"{pos_name}_EF_INDEX", 22)
    ljm.eWriteName(handle, f"{pos_name}_EF_CONFIG_A", temp)

# --------------------------------------------------------
# Configures either a transducer or a loadcell since they
# are done the same. Connects to AIN apin with range rng 
# and resolution rind. The voltage is compared to GND.
#---------------------------------------------------------
def configure_transducer_loadcell(apin, rng, rind):
    ain_name = f"AIN{apin}"
    ljm.eWriteName(handle, f"{ain_name}_NEGATIVE_CH", 199)
    ljm.eWriteName(handle, f"{ain_name}_RANGE", rng)
    ljm.eWriteName(handle, f"{ain_name}_RESOLUTION_INDEX", rind)
    ljm.eWriteName(handle, f"{ain_name}_SETTLING_US", 0)

# --------------------------------------------------------
# Configures a pin as digital I/O, with the function func.
# func MUST BE either 'input' or 'ouput'.
# --------------------------------------------------------
def configure_digital_io(diopin_num, func):
    if func == "input":
        ljm.eWriteName(handle, f"DIO{diopin_num}_DIRECTION", 0)
    else:
        ljm.eWriteName(handle, f"DIO{diopin_num}_DIRECTION", 1)
        ljm.eWriteName(handle, f"DIO{diopin_num}_STATE", 0)

# --------------------------------------------------------
# Configures a DIO pin to output pwm at 50 HZ and start
# value startval
# --------------------------------------------------------
def configure_pwm(diopin_num, startval):
    ljm.eWriteName(handle, "DIO_EF_CLOCK0_ENABLE", 0)
    ljm.eWriteName(handle, "DIO_EF_CLOCK0_DIVISOR", 1)
    ljm.eWriteName(handle, "DIO_EF_CLOCK0_ROLL_VALUE", 1600000)
    ljm.eWriteName(handle, "DIO_EF_CLOCK0_ENABLE", 1)

    ljm.eWriteName(handle, f"DIO{diopin_num}_EF_ENABLE", 0)
    ljm.eWriteName(handle, f"DIO{diopin_num}_EF_INDEX", 0)
    ljm.eWriteName(handle, f"DIO{diopin_num}_EF_OPTIONS", 0)
    ljm.eWriteName(handle, f"DIO{diopin_num}_EF_CONFIG_A", startval)
    ljm.eWriteName(handle, f"DIO{diopin_num}_EF_ENABLE", 1)

# ================================
# MEASUREMENT FUNCTIONS
# ================================

# --------------------------------------------------------
# Measures and returns transducer current by diving measured 
# voltage by known resistance (Ohm's Law).
# --------------------------------------------------------
def measure_transducer_current(apin, resistance):
    voltage = ljm.eReadName(handle, f"AIN{apin}")
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
    return ljm.eReadName(handle, f"AIN{tpin}_EF_READ_A")

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
    pin_v = ljm.eReadName(handle, f"AIN{ldpin}")
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
    if nextpos == curpos:
        print(Fore.RED + "MOVE COMMAND FAILED: ALREADY " + upper(curpos))
        return False
    if nextpos == "open":
        ljm.eWriteName(handle, f"DIO{diopin_num}_EF_CONFIG_A", openval)
        curpos = nextpos
        return True
    elif nextpos == "closed":
        ljm.eWriteName(handle, f"DIO{diopin_num}_EF_CONFIG_A", closedval)
        curpos = nextpos
        return True
    else:
        print(Fore.RED + "MOVE COMMAND FAILED: " + str(upper(nextpos)) + " INVALID MOVEMENT COMMAND")
        return False

# --------------------------------------------------------
# Reads from DIO Pin.
# --------------------------------------------------------
def dread(diopin_num):
    return ljm.eReadName(handle, f"DIO{diopin_num}")

# --------------------------------------------------------
# Writes to DIO Pin, 0 for input, 1 for output.
# --------------------------------------------------------
def dwrite(diopin_num, state):
    ljm.eWriteName(handle, f"DIO{diopin_num}_STATE", state)

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
    if is_ignition_safe(a, p, t, l, mp, mt, ml):
        if lastfire == 0:
            print(Fore.ORANGE + "IGNITION ACTIVE")
            fire(ipin, ftime)
            print(Fore.ORANGE + "IGNITION COMPLETE")
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
    if sum < max_temp or sum > min_temp:
        return False
    return True

def check_pressure(history, pressure):
    sum = 0
    for i in history:
        sum += i
    sum = (sum+pressure)/(hist+1)
    if sum < max_pres or sum > min_pres:
        return False
    return True

def check_load(history, load):
    sum = 0
    for i in history:
        sum += i
    sum = (sum+load)/(hist+1)
    if sum < max_load or sum > min_load:
        return False
    return True

def kill(safet, safep, safel, kill_pin):
    dwrite(kill_pin, 0)
    if not safet:
        print(Fore.RED + "ABORTING: TEMPERATURE UNSAFE")
    if not safep:
        print(Fore.RED + "ABORTING: PRESSURE UNSAFE")
    if not safel:
        print(Fore.RED + "ABORTING: LOAD UNSAFE")
    print(Fore.RED + "PLEASE RESET SYSTEM ONCE MANUALLY CONFIRMED SAFE")

# ================================
# CONFIGURATION
# ================================

# Configure Temperature Sensing
configure_thermocouple(tpin_pos_num, tpin_neg_num, trng, trind, tset, celsius)
# Configure Pressure Sensing
configure_transducer_loadcell(ppin_num, prng, prind)
# Configure Load Sensing
configure_transducer_loadcell(lpin_num, lrng, lind)
# Configure the Servo Pins
configure_digital_io(servo1_pwm_pin, "output")
configure_pwm(servo1_pwm_pin, startval)
configure_digital_io(servo2_pwm_pin, "output")
configure_pwm(servo2_pwm_pin, startval)
# Configure ignition pins
configure_digital_io(ignite_in_pin, "input")
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
    if temp > max_temp or temp < min_temp:
        warn = 1
        safet = check_temperature(past, temp)
    if pres > max_pres or pres < min_pres:
        warn = 1
        safep = check_pressure(pastp, pres)
    if load > max_load or load < min_load:
        warn = 1
        safel = check_load(pastl, load)  
    if warn:
        if not (safet and safep and safel):
            kill(safet, safep, safel, kill_pin_num)  
            killed = True
        else:
            print(Fore.ORANGE + "WARNING: POTENTIALLY UNSAFE CONDITIONS")

    # ================================
    # MOVEMENT HANDLING HERE
    # ================================
    if not killed:
        armed = (dread(arm_pin) == 1)
        firing = (dread(fire_pin) == 1)

        if firing:
            if timestamp < hist:
                did_fire = fire_control(ignite_out_pin, fire_time, pres, temp, load, max_pres, max_temp, max_load, min_pres, min_temp, min_load)
                lastfire = int(did_fire)
            else:
                print(Fore.RED + "IGNITION FAILED: SYSTEM NOT READY")
                lastfire = 0

        print(Fore.GREEN + "Temperature (C):", temp)
        print(Fore.GREEN + "Pressure (psi):", pres)
        print(Fore.GREEN + "Force:", load)

        time.sleep(0.1)