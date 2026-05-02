from labjack import ljm
from colorama import Fore, init
import time

init(autoreset=True)

mb = ljm.openS("T7", "ANY", "ANY")

# LJTick-InAmp 51x, channel B output on AIN1 (single-ended vs GND)
# VOUT = 51 * (INB+ - INB-) + 2.5 — tare cancels the offset automatically
ljm.eWriteName(mb, "AIN1_NEGATIVE_CH",      199)   # single-ended
ljm.eWriteName(mb, "AIN1_RANGE",            10.0)  # ±10V to cover 2.5V offset
ljm.eWriteName(mb, "AIN1_RESOLUTION_INDEX", 0)
ljm.eWriteName(mb, "AIN1_SETTLING_US",      0)

# ================================
# CALIBRATION
# ================================
# v_off   = zero voltage (tare)
# kload   = known calibration load (your units)
# v_kload = voltage reading at kload

def tare():
    readings = [ljm.eReadName(mb, "AIN1") for _ in range(50)]
    return sum(readings) / len(readings)

def calibrate():
    input(Fore.YELLOW + "Apply known calibration load, then press Enter...")
    readings = [ljm.eReadName(mb, "AIN1") for _ in range(50)]
    v_kload = sum(readings) / len(readings)
    kload = float(input(Fore.YELLOW + "Enter the calibration load value: "))
    return kload, v_kload

def read_load(v_off, kload, v_kload):
    v = ljm.eReadName(mb, "AIN1")
    factor = kload / (v_kload - v_off)
    return (v - v_off) * factor

# ================================
# RUN
# ================================
print(Fore.YELLOW + "DIAGNOSTIC — apply and remove load to verify signal is changing (10 s)...")
for _ in range(100):
    raw = ljm.eReadName(mb, "AIN1")
    print(Fore.CYAN + f"  AIN1: {raw:.6f} V")
    time.sleep(0.1)

input(Fore.YELLOW + "\nRemove all load, then press Enter to tare...")
v_off = tare()
print(Fore.GREEN + f"Zero voltage: {v_off:.6f} V")

kload, v_kload = calibrate()
print(Fore.GREEN + f"v_off:   {v_off:.6f} V")
print(Fore.GREEN + f"v_kload: {v_kload:.6f} V")
print(Fore.GREEN + f"delta:   {v_kload - v_off:.6f} V")
print(Fore.GREEN + f"kload:   {kload}")

print("\nStreaming — Ctrl+C to stop\n")
try:
    while True:
        load = read_load(v_off, kload, v_kload)
        raw  = ljm.eReadName(mb, "AIN1")
        print(Fore.GREEN + f"Load: {load:.3f}    Raw: {raw:.6f} V")
        time.sleep(0.1)
except KeyboardInterrupt:
    pass
finally:
    ljm.close(mb)
