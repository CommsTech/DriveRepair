# Test-validity and dead-code audit design

Type: research
Status: open
Blocked by: —

## Question

Design the bounded audit that proves the suite validates behavior and the codebase is clean: (1) method to detect tests that assert line/interface existence rather than behavior (e.g., assertion-density scan, mutation testing via mutmut/cosmic-ray feasibility on a 600-test suite, targeted manual sampling plan); (2) dead-code and TODO inventory (vulture, ruff F401/unreachable, grep TODO audit) with expected false-positive handling for Windows ctypes type-ignores and defensive fail-closed branches; (3) effort estimate and pass/fail criteria so a later session can execute without re-deciding. Cite tool docs; recommend a default.
