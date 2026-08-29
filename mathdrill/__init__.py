"""Math Drill: timed mental-arithmetic drills with per-question timing analysis.

The interesting part of this project is not the drill, it is the record it
keeps. Every answered question is stored with its operands held separately
from the rendered question string, which is what makes digit-level feature
extraction possible ("operands containing a 9 cost you 4.98s vs 3.44s for a 1").

Layout:
    core      pure-stdlib drill logic (config, question generation, sessions)
    features  pandas feature extraction and metrics; no plotting
    storage   reading and writing the session JSON file
    app       Tkinter frontend
    insights  matplotlib/seaborn charts

`core` and `features` import neither tkinter nor matplotlib, so they can be
reused by a CLI, a web port, or a test suite.
"""

__version__ = "0.2.0"

__all__ = ["__version__"]
