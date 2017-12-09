""" Addresses issues with importing across nested modules.

See http://docs.python-guide.org/en/latest/writing/structure/ for
background on why this file exists and what it does. In short, it avoids
some import issues when the tests package is in the same folder as
(and not nested within) the source package.
"""

import os
import sys
# Insert at the front of the path (rather than append) to ensure that
# `forecaster` refers to the top-level package, not one of the various
# nested `forecaster.py` modules.
sys.path.insert(
    0,
    # Go up one level from this dir to add the (non-package) root
    # dir to the python import path:
    os.path.dirname(
        os.path.dirname(
            os.path.abspath(__file__)
        )
    )
)
