"""
Wattbox control module for turning on and off outlets on a SnapAV wattbox
power strip.

Author: Greg J. Badros

$ cd .../path/to/home-assistant/
$ pip3 install --upgrade .../path/to/pywattbox

Then the component/wattbox.py and its require line will work.

TODO: Parse voltage_value (1200 = 120V; it's in tenths of volts)
      Parse current_value (105 = 10.5A; it's in tengths of amps)
      Parse power_value (600 = 600W; it's in watts)

And create a sensor for the watts (and maybe the others)

"""

__Author__ = "Greg J. Badros <badros@gmail.com>"
__copyright__ = "Copyright 2019, Greg J. Badros"

from time import (localtime, mktime)
import logging
import threading
import re
import json
import requests

# urllib.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
_LOGGER = logging.getLogger(__name__)


def xml_escape(s):
    """Return s but after XML escaping of < and & characters."""
    # pylint: disable=invalid-name
    answer = s.replace("<", "&lt;")
    answer = answer.replace("&", "&amp;")
    return answer

def _t(root, name):
    """Return the element named NAME's text or None."""
    e = root.find(name)
    if e is None:
        return None
    return e.text

def _i(root, name):
    """Return the element named NAME's text as an int/10 or None."""
    e = root.find(name)
    if e is None:
        return None
    return int(e.text)/10

class WattBox:
    """Main WattBox class.

    This object owns the connection to the wattbox power strip, handles
    reading status, and issuing state changes.
    """



    def parse(self, xml_str):
        """Main entrypoint into the parser. It gets the state of the strip."""

        import xml.etree.ElementTree as ET
        _LOGGER.debug("wattbox %s parse: %s", self, xml_str)

        root = ET.fromstring(xml_str)
        self._hostname = _t(root, 'host_name')
        self._hardware_version = _t(root, 'hardware_version')
        self._serial_number = _t(root, 'serial_number')
        self._has_ups = _t(root, 'hasUPS')
        self._voltage = _i(root, 'voltage_value')
        self._current = _i(root, 'current_value')
        self._power = _i(root, 'power_value')
        self._cloud_status = _t(root, 'cloud_status') == '1'
        outlet_names = _t(root, 'outlet_name').split(',')
        outlet_status = _t(root, 'outlet_status').split(',')
        for (i, (name, state)) in enumerate(zip(outlet_names, outlet_status)):
            self._switches.append(Switch(self, i, name, state == '1'))
        return True

    # pylint: disable=too-many-instance-attributes, too-many-arguments
    def __init__(self, host, username, password, area='',
                 noop_set_state=False):
        """Initializes the WattBox object. No connection is made to the device."""
        self._host = host
        self._username = username
        self._password = password
        self._area = area
        self._noop_set_state = noop_set_state
        self._hostname = None
        self._hardware_version = None
        self._serial_number = None
        self._has_ups = None
        self._last_updated = None
        self._switches = []
        self._has_ups = False
        self._voltage = None
        self._current = None
        self._power = None
        self._cloud_status = None

    def load_xml(self):
        """Load the WattBox status from the device."""
        url = 'http://{h}/wattbox_info.xml'.format(h=self._host)
        try:
            response = requests.get(url, auth=(self._username, self._password),
                                    verify=False)
        except requests.exceptions.ConnectionError as e:
            _LOGGER.warning("Could not load_xml from wattbox at %s - error %s", url, e)
            raise
        xml_str = response.text
        _LOGGER.debug("Loaded xml status = %s", xml_str)
        try:
            self.parse(xml_str)
        except Exception as e:
            _LOGGER.warning("Could not parse WattBox %s response", self._hostname)
            raise

        _LOGGER.debug('Found wattbox with %d outlets', len(self._switches))
        self._last_updated = mktime(localtime())
        return True

    @property
    def switches(self):
        """Return the full list of outputs in the controller."""
        return self._switches

    @property
    def voltage(self):
        """Return the reported voltage in Volts."""
        return self._voltage

    @property
    def current(self):
        """Return the reported current in Amps."""
        return self._current

    @property
    def power(self):
        """Return the reported power in Watts."""
        return self._power

    @property
    def host(self):
        """Return the full list of outputs in the controller."""
        return self._host

    def _update(self, xml_str=None):
        now = mktime(localtime())

        if xml_str is None:
            if now - self._last_updated < 3:
                return
            url = 'http://{h}/control.cgi'.format(h=self._host)
            _LOGGER.debug("update Sending wattbox %s url %s", self._hostname, url)
            if not self._noop_set_state:
                response = requests.get(url,
                                        auth=(self._username, self._password),
                                        verify=False)
                xml_str = response.text
            else:
                _LOGGER.info("Not actually making request to wattbox host (noop_set_state)")
        import xml.etree.ElementTree as ET
        root = ET.fromstring(xml_str)
        vals = root.find('outlet_status').text.split(',')
        if len(vals) != len(self._switches):
            raise Exception("Bad outlet_status length not equal to switches length: " + xml_str)
        for (i, val) in enumerate(vals):
            # pylint: disable=protected-access
            self._switches[i]._on = (val == '1')
        self._last_updated = now


class Switch:
    """Wattbox Switch represents a single IP-controlled outlet
    that can be turned on or off."""
    def __init__(self, wattbox, offset, name, on):
        self._wattbox = wattbox
        self._outlet_num = offset + 1
        self._name = '{n} [{num}]'.format(n=name, num=offset+1)
        self._on = on

    @property
    def name(self):
        """Return the name of this switch."""
        return self._name

    @name.setter
    def name(self, value):
        """Set the name."""
        self._name = value

    @property
    def outlet_num(self):
        """Return the 1-based outlet number of this switch."""
        return self._outlet_num

    @property
    def is_on(self):
        """Return True if the switch is on, else False."""
        return self._on

    def __str__(self):
        """Returns a pretty-printed string for this object."""
        return "WattBox outlet {n} ({on})".format(
            n=self._name,
            on="on" if self._on else "off")

    def __repr__(self):
        """Returns a stringified representation of this object."""
        return str({'name': self._name, 'on': self._on})

    # pylint: disable=protected-access
    def set_state(self, turn_on):
        """Set the state of the switch to on iff turn_on is True."""
        cmd = "1" if turn_on else "0"
        current_time = '%d999' % (mktime(localtime()))
        url = 'http://{h}/control.cgi?outlet={o}&command={c}&time={t}'.format(
            h=self._wattbox._host, o=self._outlet_num, c=cmd, t=current_time)
        _LOGGER.debug("Sending wattbox %s url %s",
                      self._wattbox._hostname, url)
        if not self._wattbox._noop_set_state:
            try:
                response = requests.get(url, auth=(self._wattbox._username,
                                                   self._wattbox._password),
                                        verify=False)
            except requests.exceptions.ConnectionError as e:
                _LOGGER.warning("Could not reach wattbox at %s - error %s", url, e)
                return
            self._update(response.text)
        else:
            _LOGGER.info("Not actually making request to wattbox host (noop_set_state)")
        self._on = turn_on
        _LOGGER.debug("Wattbox responded '%s'", response.text)

    def _update(self, response_text=None):
        old_on = self._on
        self._wattbox._update(response_text)
        if old_on != self._on:
            _LOGGER.info("Updated wattbox %s", self)
        return old_on != self._on
