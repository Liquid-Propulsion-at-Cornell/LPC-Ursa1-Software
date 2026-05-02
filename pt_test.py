# PRESSURE TRANSDUCER READ TEST
# Author: Thomas Tedeschi
# Last Update Date: 5/2/2026

from labjack import ljm
from colorama import Fore
import time

mb = ljm.openS("T7", "ANY", "ANY")

# ================================
# HARDWARE PIN ASSIGNMENTS
# ================================
pt_pin     = 1        # AIN1 — voltage across shunt resistor
pt_rng     = 10.0     # 10 V range (max voltage = 0.02 * 220 = 4.4 V)
pt_rind    = 1        # resolution index
pt_res_val = 220      # shunt resistor (ohms)
pt_pmin    = 0        # pressure at 4 mA (psi)
pt_pmax    = 300      # pressure at 20 mA (psi)
pt_zero    = 0.88     # zero offset (psi) — trim until unpressurized reads 0


# ================================
# CONFIG FUNCTIONS
# ================================

def configure_transducer(apin, rng, rind):
    ain_name = f"AIN{apin}"
    ljm.eWriteName(mb, f"{ain_name}_NEGATIVE_CH", 199)  # single-ended (GND ref)
    ljm.eWriteName(mb, f"{ain_name}_RANGE", rng)
    ljm.eWriteName(mb, f"{ain_name}_RESOLUTION_INDEX", rind)
    ljm.eWriteName(mb, f"{ain_name}_SETTLING_US", 0)


# ================================
# MEASUREMENT FUNCTIONS
# ================================

def measure_current(apin, resistance):
    return ljm.eReadName(mb, f"AIN{apin}") / resistance

def current_to_pressure(current, pmin, pmax):
    return ((current - 0.004) / 0.016) * (pmax - pmin) + pmin

def read_pressure(apin, resistance, pmin, pmax, samples=10):
    avg_current = sum(measure_current(apin, resistance) for _ in range(samples)) / samples
    return current_to_pressure(avg_current, pmin, pmax)


# ================================
# CONFIGURATION
# ================================
configure_transducer(pt_pin, pt_rng, pt_rind)


# ================================
# MAIN LOOP
# ================================
try:
    while True:
        pressure = read_pressure(pt_pin, pt_res_val, pt_pmin, pt_pmax) + pt_zero
        print(Fore.GREEN + f"PT: {pressure:.2f} psi")
        time.sleep(0.5)
finally:
    ljm.close(mb)
