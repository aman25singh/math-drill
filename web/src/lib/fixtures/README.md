# Verified metric fixtures

`metrics.json` contains synthetic cases and expected results captured from the
Python implementation at commit `3dcf5fb`, after live parity verification.
It covers all 29 W04 scenarios. No user practice data is included.

The Python app is frozen as historical reference. Normal web tests consume these
fixed expected results without executing Python. Do not regenerate expected
results from the TypeScript implementation: that would hide regressions.
Any intentional web metric change needs a reviewed expectation and explanation.
