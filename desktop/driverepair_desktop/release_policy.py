"""Distribution-time safety policy, embedded into a public zipapp build.

Source checkouts retain engineering commands and must NOT be distributed as a
public image-only beta. The public zipapp builder copies this module with
PUBLIC_BETA_IMAGE_ONLY=True; no user flag or environment variable overrides it.
"""
from __future__ import annotations

PUBLIC_BETA_IMAGE_ONLY = False  # Source checkout / engineering distribution only.

PHYSICAL_WRITE_COMMANDS = frozenset({
    'care-external', 'refresh-external', 'refresh-system',
})
# Image in-place refresh also writes the original source image. Public recovery
# is copy-out-only; work on a separately created clone in engineering builds.
IN_PLACE_WRITE_COMMANDS = PHYSICAL_WRITE_COMMANDS | {'care-image', 'refresh-image'}


def block_public_physical_writes(command: str | None, *, execute_optimization: bool = False) -> None:
    """Deny live patient writes before discovery, device opening or journal access."""
    if PUBLIC_BETA_IMAGE_ONLY and (command in IN_PLACE_WRITE_COMMANDS or
                                   (command == 'optimize-volume' and execute_optimization)):
        raise ValueError(
            'In-place patient writes are unavailable in this public image-first beta. '
            'Choose a read-only scan or rescue to a new image instead. '
            'Hardware repair remains restricted to separately qualified engineering builds.'
        )


def assert_raw_device_writer_available() -> None:
    """Defense in depth when a caller bypasses the CLI dispatcher."""
    if PUBLIC_BETA_IMAGE_ONLY:
        raise PermissionError('Public image-first beta cannot open a physical patient for writing')


def assert_image_patient_writer_available() -> None:
    """No in-place mutation of a source image in the public candidate."""
    if PUBLIC_BETA_IMAGE_ONLY:
        raise PermissionError('Public image-first beta cannot open an original image for in-place rewriting')
