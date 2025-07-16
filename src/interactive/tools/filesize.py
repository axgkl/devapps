"""
name="hurry.filesize",
version="0.9",
description="A simple Python library for human readable file
            sizes (or anything sized in bytes).",
classifiers=[
    "Programming Language :: Python",
    "Topic :: Software Development :: Libraries :: Python Modules",
    ],
keywords='file size bytes',
author='Martijn Faassen, Startifact',
author_email='faassen@startifact.com',
url='',
license='ZPL 2.1',
"""

p, t, g, m, k, b = [1024**i for i in range(5, -1, -1)]
traditional = [
    (p, 'P'),
    (t, 'T'),
    (g, 'G'),
    (m, 'M'),
    (k, 'K'),
    (b, 'B'),
]

alternative = [
    (p, 'PB'),
    (t, 'TB'),
    (g, 'GB'),
    (m, 'MB'),
    (k, 'KB'),
    (b, 'B '),
]


verbose = [
    (p, (' petabyte', ' petabytes')),
    (t, (' terabyte', ' terabytes')),
    (g, (' gigabyte', ' gigabytes')),
    (m, (' megabyte', ' megabytes')),
    (k, (' kilobyte', ' kilobytes')),
    (b, (' byte', ' bytes')),
]

iec = [
    (p, 'Pi'),
    (t, 'Ti'),
    (g, 'Gi'),
    (m, 'Mi'),
    (k, 'Ki'),
    (b, ''),
]

si = [
    (1000**5, 'P'),
    (1000**4, 'T'),
    (1000**3, 'G'),
    (1000**2, 'M'),
    (1000**1, 'K'),
    (1000**0, 'B'),
]

units = [i[1] for i in alternative]
sizes = {u: i for u, i in zip(units, range(len(units)))}


def size(bytes, system=traditional):
    """Human-readable file size.

    Using the traditional system, where a factor of 1024 is used::

    >>> size(10)
    '10B'
    >>> size(100)
    '100B'
    >>> size(1000)
    '1000B'
    >>> size(2000)
    '1K'
    >>> size(10000)
    '9K'
    >>> size(20000)
    '19K'
    >>> size(100000)
    '97K'
    >>> size(200000)
    '195K'
    >>> size(1000000)
    '976K'
    >>> size(2000000)
    '1M'

    Using the SI system, with a factor 1000::

    >>> size(10, system=si)
    '10B'
    >>> size(100, system=si)
    '100B'
    >>> size(1000, system=si)
    '1K'
    >>> size(2000, system=si)
    '2K'
    >>> size(10000, system=si)
    '10K'
    >>> size(20000, system=si)
    '20K'
    >>> size(100000, system=si)
    '100K'
    >>> size(200000, system=si)
    '200K'
    >>> size(1000000, system=si)
    '1M'
    >>> size(2000000, system=si)
    '2M'

    """
    for factor, suffix in system:
        if bytes >= factor:
            break
    amount = int(bytes / factor)
    if isinstance(suffix, tuple):
        singular, multiple = suffix
        if amount == 1:
            suffix = singular
        else:
            suffix = multiple
    return str(amount) + suffix
