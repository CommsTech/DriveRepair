# Distribution mechanism research

Type: research
Status: open
Blocked by: —

## Question

What is the most secure, adoption-friendly way to let a new user run DriveRepair with one command on Windows, macOS, and Linux? Facts already in-repo (verify, don't assume): `scripts/setup_host_environment.py` (consent-gated host setup helper, landed 0.3.3b37), `scripts/check_release_readiness.py`, `scripts/check_release_hygiene.py`. Compare, with evidence (precedent OSS disk tools, packaging docs, risk notes): (a) per-OS bootstrap script that verifies Python ≥3.10, builds a venv, installs, launches; (b) published console-script package on PyPI used via pipx/uv; (c) PyInstaller/zipapp bundled binaries (AV false-positive and review-opacity risks); (d) hybrid building on `setup_host_environment.py`. Recommend one primary path plus what ships alongside it, whether the existing helper satisfies the one-command goal or needs extension, and list what the repo still lacks. Cite sources.
