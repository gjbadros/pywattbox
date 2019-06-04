"""
Wattbox control module for turning on and off outlets on a SnapAV wattbox
power strip.

Author: Greg J. Badros

$ cd .../path/to/home-assistant/
$ pip3 install --upgrade .../path/to/pywattbox

Then the component/wattbox.py and its require line will work.

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

class WattBoxXmlParser(object):
    """The parser for WattBox XML status output."""

    # pylint: disable=too-few-public-methods, too-many-instance-attributes
    def __init__(self, wattbox, xml_str):
        """Initializes the XML parser."""
        self.wattbox = wattbox
        self._xml_str = xml_str
        self.switches = []
        self.hostname = None
        self.hardware_version = None
        self.serial_number = None
        self.has_ups = False

    def parse(self):
        """Main entrypoint into the parser. It gets the state of the strip."""

        import xml.etree.ElementTree as ET

        root = ET.fromstring(self._xml_str)
        self.hostname = root.find('host_name').text
        self.hardware_version = root.find('hardware_version').text
        self.serial_number = root.find('serial_number').text
        self.has_ups = root.find('hasUPS').text == '1'
        outlet_names = root.find('outlet_name').text.split(',')
        outlet_status = root.find('outlet_status').text.split(',')
        for (i, (name, state)) in enumerate(zip(outlet_names, outlet_status)):
            self.switches.append(Switch(self.wattbox, i, name, state == '1'))
        return True


class WattBox(object):
    """Main WattBox class.

    This object owns the connection to the wattbox power strip, handles
    reading status, and issuing state changes.
    """

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
        self.__last_updated = None
        self._switches = None

    def load_xml(self):
        """Load the WattBox status from the device."""
        url = 'http://{h}/wattbox_info.xml'.format(h=self._host)
        response = requests.get(url, auth=(self._username, self._password),
                                verify=False)
        xml_str = response.text
        _LOGGER.debug("Loaded xml status = %s", xml_str)
        parser = WattBoxXmlParser(self, xml_str)
        try:
            parser.parse()
        except Exception as e:
            _LOGGER.warning("Could not parse WattBox %s response", self._hostname)
            raise

        _LOGGER.debug('Found wattbox with %d outlets', len(parser.switches))
        self._switches = parser.switches
        self._hostname = parser.hostname
        self._hardware_version = parser.hardware_version
        self._serial_number = parser.serial_number
        self._has_ups = parser.has_ups
        self.__last_updated = mktime(localtime())
        return True

    @property
    def switches(self):
        """Return the full list of outputs in the controller."""
        return self._switches

    @property
    def host(self):
        """Return the full list of outputs in the controller."""
        return self._host

    def _update(self, xml_str=None):
        now = mktime(localtime())

        if xml_str is None:
            if now - self.__last_updated < 3:
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
        self.__last_updated = now


class Switch(object):
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
            response = requests.get(url, auth=(self._wattbox._username,
                                               self._wattbox._password),
                                    verify=False)
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
