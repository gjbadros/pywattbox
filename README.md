pywattbox 0.0.5
===============
A simple Python library for controlling a WattBox IP-controlled outlet.

Note that on PyPi, this is pysnapavwattbox


Authors
-------
Greg Badros (gjbadros on github)


Installation
------------

Get the source from github.


Example
-------
    import pywattbox

    wb = pywattbox.WattBox("192.168.0.x", "host", user", "password")
    wb.load_xml_db()


License
-------
This code is released under the MIT license.
