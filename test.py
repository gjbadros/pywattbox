#!/usr/bin/env python3
"""
Test the pywattbox module for controlling WattBox ip-controlled
power strips.

Before execution, set the following environment variables:

WATTBOX_HOSTNAME - host or ip address of a wattbox device
WATTBOX_USERNAME - login username for that device
WATTBOX_PASSWORD - password for that user

"""

import logging
from os import environ
from pywattbox import WattBox

_LOGGER = logging.getLogger(__name__)

logging.basicConfig(level=logging.DEBUG)

W = WattBox(environ['WATTBOX_HOSTNAME'], environ['WATTBOX_USERNAME'], environ['WATTBOX_PASSWORD'])
W.load_xml()
print(W.switches)
W.switches[0].set_state(True)
v = W.voltage
a = W.current
w = W.power

print("{v} V * {a} A =~ {w} W".format(v=v,a=a,w=w))

if abs(v*a*.8 - w) > (.1 * v *a):
    print("Voltage * Amps should equal Wattage but does not")
