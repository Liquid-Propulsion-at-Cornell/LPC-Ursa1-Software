# Liquid Propulsion at Cornell Data Acquisition Software

This repository contains the software for the data acquisition (DAQ) and control systems used by Liquid Propulsion at Cornell (LPC). It contains python scripts for both engine control and DAQ, as well as testing files for different software and hardware. Feel free to use or adapt this software for your own purposes

## Software Log

### Ursa 1

The control and DAQ script for the ursa 1 engine are located in the file ursa1-daq-control.py. This engine's systems are centered around the LabJack T7 board, so the script is configured around it. The script uses a threaded infrastructure, splitting between reading the sensors and running safety checks, and controling the servo motors according to our FSM.  

**This script is still under construction, and is not completely finished. Make sure to edit if you wish to use it.**

## NOTICE

Due to the safety considerations involved in this project, you **must** have explicit permission from the owners to edit this repository. Any person who edits this software without permission will be permanently banned from accessing it, and their edits will be immediately removed. If you wish to edit it, any copying and editing outside of the repository is approved by the owners. Please use this software responsibly.  

All code is written and maintained by Thomas Tedeschi (tmt115). Any questions or suggestions can be sent through github issues, or sent to tmt65@cornell.edu.  


