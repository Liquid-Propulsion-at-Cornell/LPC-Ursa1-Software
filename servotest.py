# SERVO MOTOR CONTROL TEST
# Author: Thomas Tedeschi
# Last Update Date: 5/2/2026

from labjack import ljm
from colorama import Fore, init
import time

init(autoreset=True)

mb = ljm.openS("T7", "ANY", "ANY")

PWM_FREQ  = 50
ROLL      = int(80_000_000 / PWM_FREQ)
DEG_90_MS = 0.6   # ms of travel per 90° — tune if sweep angle is wrong

ljm.eWriteName(mb, "DIO_EF_CLOCK0_ENABLE",     0)
ljm.eWriteName(mb, "DIO_EF_CLOCK0_DIVISOR",    1)
ljm.eWriteName(mb, "DIO_EF_CLOCK0_ROLL_VALUE", ROLL)
ljm.eWriteName(mb, "DIO_EF_CLOCK0_ENABLE",     1)

ljm.eWriteName(mb, "DIO0_EF_ENABLE",   0)
ljm.eWriteName(mb, "DIO0_EF_INDEX",    0)
ljm.eWriteName(mb, "DIO0_EF_OPTIONS",  0)
ljm.eWriteName(mb, "DIO0_EF_CONFIG_A", int(80_000_000 * 1.5 / 1000))
ljm.eWriteName(mb, "DIO0_EF_ENABLE",   1)

def set_ms(ms):
    ljm.eWriteName(mb, "DIO0_EF_CONFIG_A", int(80_000_000 * ms / 1000))

# ================================
# JOG TO HOME
# ================================
print(Fore.CYAN + "JOG MODE — type a pulse width in ms (e.g. 1.5) to move servo")
print(Fore.CYAN + "Valid range is roughly 0.5 to 2.5 ms")
print(Fore.CYAN + "Press Enter with no input when servo is at your desired home\n")

home_ms = 1.5
set_ms(home_ms)

while True:
    val = input(Fore.YELLOW + f"  Current: {home_ms:.2f} ms  →  new value (or Enter to confirm): ").strip()
    if val == "":
        break
    try:
        home_ms = float(val)
        set_ms(home_ms)
    except ValueError:
        print(Fore.RED + "  Enter a number like 1.2 or 1.8")

target_ms = home_ms + DEG_90_MS
print(Fore.GREEN + f"\nHome: {home_ms:.2f} ms    90° target: {target_ms:.2f} ms")
print(Fore.GREEN + "Running sweep — Ctrl+C to stop\n")

# ================================
# SWEEP
# ================================
try:
    while True:
        set_ms(home_ms)
        print(Fore.GREEN + "home")
        time.sleep(1)

        set_ms(target_ms)
        print(Fore.GREEN + "90°")
        time.sleep(1)
except KeyboardInterrupt:
    set_ms(home_ms)
finally:
    ljm.eWriteName(mb, "DIO0_EF_ENABLE", 0)
    ljm.close(mb)
