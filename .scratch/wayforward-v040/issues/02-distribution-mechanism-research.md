# Distribution mechanism research

Type: research
Status: open
Blocked by: —

## Question

What is the most secure, adoption-friendly way to let a new user run DriveRepair with one command on Windows, macOS, and Linux? Compare, with evidence (precedent OSS disk tools, packaging docs, risk notes): (a) per-OS bootstrap script that verifies Python ≥3.10, builds a venv, installs, launches; (b) published console-script package on PyPI used via pipx/uv; (c) PyInstaller/zipapp bundled binaries (AV false-positive and review-opacity risks); (d) hybrid. Recommend one primary path plus what ships alongside it, and list what the repo must gain (entry points, scripts, version metadata) to support it. Cite sources.
