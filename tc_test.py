from labjack import ljm
from colorama import Fore, init
import time

init(autoreset=True)

mb = ljm.openS("T7", "ANY", "ANY")

ljm.eWriteName(mb, "AIN1_NEGATIVE_CH",      0)
ljm.eWriteName(mb, "AIN1_RANGE",            0.1)
ljm.eWriteName(mb, "AIN1_RESOLUTION_INDEX", 0)
ljm.eWriteName(mb, "AIN1_SETTLING_US",      0)
ljm.eWriteName(mb, "AIN1_EF_INDEX",         22)
ljm.eWriteName(mb, "AIN1_EF_CONFIG_A",      2)    # 2 = Fahrenheit
# ljm.eWriteName(mb, "AIN1_EF_CONFIG_D",      -1)   # CJC offset (°C) — tune to match a known reference

print("TC test running — Ctrl+C to stop\n")

try:
    while True:
        temp = ljm.eReadName(mb, "AIN1_EF_READ_A")
        print(Fore.GREEN + f"Temp: {temp:.1f} F")
        time.sleep(0.5)
except KeyboardInterrupt:
    pass
finally:
    ljm.close(mb)
