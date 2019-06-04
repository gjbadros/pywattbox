from distutils.core import setup

setup(
    name = 'pysnapavwattbox',
    version = '0.0.3',
    license = 'MIT',
    description = 'Python library for WattBox IP-controlled outlets, used for Home Assistant',
    author = 'Greg J. Badros',
    author_email = 'badros@gmail.com',
    url = 'http://github.com/gjbadros/pywattbox',
    packages=['pywattbox'],
    classifiers = [
        'Development Status :: 3 - Alpha',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3.4',
        'Topic :: Home Automation',
        'Topic :: Software Development :: Libraries :: Python Modules',
    ],
)
