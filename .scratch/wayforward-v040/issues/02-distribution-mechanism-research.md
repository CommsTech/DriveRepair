# Distribution mechanism research

Type: research
Status: resolved
Blocked by: —

## Question

What is the most secure, adoption-friendly way to let a new user run DriveRepair with one command on Windows, macOS, and Linux? Facts already in-repo (verify, don't assume): `scripts/setup_host_environment.py` (consent-gated host setup helper, landed 0.3.3b37), `scripts/check_release_readiness.py`, `scripts/check_release_hygiene.py`. Compare, with evidence (precedent OSS disk tools, packaging docs, risk notes): (a) per-OS bootstrap script that verifies Python ≥3.10, builds a venv, installs, launches; (b) published console-script package on PyPI used via pipx/uv; (c) PyInstaller/zipapp bundled binaries (AV false-positive and review-opacity risks); (d) hybrid building on `setup_host_environment.py`. Recommend one primary path plus what ships alongside it, whether the existing helper satisfies the one-command goal or needs extension, and list what the repo still lacks. Cite sources.

## Answer

**Recommendation (primary path): (b)+(d) hybrid — publish `driverepair-desktop` as a console-script package on PyPI, installed via `pipx install driverepair-desktop` (or `uv tool install`), with per-OS optional smartctl install driven by the existing consent-gated helper.** This matches how comparable OSS tools distribute: smartmontools ships native installers per OS (.dmg, win32-setup.exe, distro packages) for the low-level tool, while pure-Python apps standardize on pipx/uv with declared entry points (pipx works with "any package that declares console script entry points", incl. git/local sources — https://pipx.pypa.io/, https://pipx.pypa.io/latest/how-to/install-pipx.html). A PyInstaller one-file binary is the fallback-of-last-resort: PyInstaller onefile exes are routinely flagged by Windows Defender/heuristics (Trojan:Win32/Wacatac etc.) and code signing only reduces, not removes, false positives; unsigned free-tier OSS like this repo would face SmartScreen "unknown publisher" and opaque binary review (https://www.pythonguis.com/faq/problems-with-antivirus-software-and-pyinstaller/, https://stackoverflow.com/questions/64788656/, https://journal.code4lib.org/articles/18136).

**What ships alongside:** documented quickstart (`uv tool run`/`pipx run` for zero-install try-out); a small bootstrap script per OS (pure-text, reviewable — following the pipx bootstrap precedent of `python pipx.py` from docs) that verifies Python ≥3.10, installs pipx/uv if missing, then `pipx install driverepair-desktop`; keep `setup_host_environment.py` as the consent-gated post-install step for smartctl (winget on Windows already wired; Linux/macOS need apt/brew branches).

**Does `setup_host_environment.py` satisfy one-command? Verified: no.** Its default mode is report-only; installs require `--approve-install`. `--install-desktop-qt` runs `pip install -e desktop[qt]`, an *editable install of the source tree* — it only works from a git checkout, not for a new user. There is no macOS/Linux smartctl branch (Windows winget only). It also checks module availability but does not create a venv or fetch Python. It is an excellent consent-gated prerequisite checker, not a bootstrap.

**What the repo lacks:** no PyPI publication (package name/version 0.3.3b37 declared only locally in `desktop/pyproject.toml`); entry points exist (`driverepair-desktop`, `driverepair-gui` etc. — good, pipx-compatible); no root-level `pyproject.toml` (only `desktop/` and Cargo) so `pipx install git+...` needs pointing at the subpackage; no code-signing cert or CI signing; no published wheels. Also missing: pinned PyPI release workflow and a one-line README install command.

**Risks:** (1) AV false positives if PyInstaller fallback is ever shipped — avoid, or sign; (2) PyPI supply-chain trust — publish from tagged CI builds, not laptops; (3) elevated smartctl installs are consent-gated already, which is a differentiator worth keeping; (4) pipx GUI entry point on Windows is not on PATH-start-menu — document or add a tiny shortcut script.

Citations: https://pipx.pypa.io/ · https://pipx.pypa.io/latest/how-to/install-pipx.html · https://www.pythonguis.com/faq/problems-with-antivirus-software-and-pyinstaller/ · https://stackoverflow.com/questions/64788656/ · https://journal.code4lib.org/articles/18136 · https://sourceforge.net/projects/smartmontools/ · https://github.com/smartmontools/smartmontools/releases · https://community.chocolatey.org/packages/smartmontools
