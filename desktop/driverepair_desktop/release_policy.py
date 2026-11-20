"""Distribution-time safety policy, embedded into a public zipapp build.

Source checkouts retain engineering commands and must NOT be distributed as a
public image-only beta. The public zipapp builder copies this module with
PUBLIC_BETA_IMAGE_ONLY=True; no user flag or environment variable overrides it.
"""
from __future__ import annotations

PUBLIC_BETA_IMAGE_ONLY = False  # Source checkout / engineering distribution only.
REPAIR_BETA_GUARDED = False  # Only the explicit --repair-beta artifact enables this.

PHYSICAL_WRITE_COMMANDS = frozenset({
    'care-external', 'refresh-external', 'refresh-system', 'validate-usb-capacity',
})
# Image in-place refresh also writes the original source image. Public recovery
# is copy-out-only; work on a separately created clone in engineering builds.
IN_PLACE_WRITE_COMMANDS = PHYSICAL_WRITE_COMMANDS | {'care-image', 'refresh-image', 'validate-image-capacity'}


def block_public_physical_writes(command: str | None, *, execute_optimization: bool = False) -> None:
    """Deny unsafe distribution commands BEFORE inventory or opening patients."""
    direct_write = command in IN_PLACE_WRITE_COMMANDS or (
        command == 'optimize-volume' and execute_optimization) or (
        command == 'repair-windows-filesystem' and execute_optimization)
    if PUBLIC_BETA_IMAGE_ONLY and direct_write:
        raise ValueError(
            'In-place patient writes are unavailable in this public image-first beta. '
            'Choose a read-only scan or rescue to a new image instead. '
            'Hardware repair remains restricted to separately qualified engineering builds.'
        )
    if REPAIR_BETA_GUARDED and direct_write and command not in {'care-external','validate-usb-capacity','repair-windows-filesystem'}:
        raise ValueError(
            'Direct media writes are unavailable in the guarded repair beta. '
            'For physical HDD writes use guided care-external with verified identity, '
            'exclusive lock and a separate durable journal. On-device Windows '
            'filesystem metadata repair is a separately guarded operation.'
        )


def assert_raw_device_writer_available() -> None:
    """Defense in depth when a caller bypasses the CLI dispatcher."""
    if PUBLIC_BETA_IMAGE_ONLY:
        raise PermissionError('Public image-first beta cannot open a physical patient for writing')


def assert_image_patient_writer_available() -> None:
    """No in-place mutation of a source image in the public candidate."""
    if PUBLIC_BETA_IMAGE_ONLY:
        raise PermissionError('Public image-first beta cannot open an original image for in-place rewriting')


def check_guarded_repair_preflight(args, snapshot: dict | None, device) -> dict:
    """The repair-beta may attempt ONLY evidence-qualified guided HDD rewrites.

    Protects against direct CLI invocation that bypasses Qt. All existing
    independent identity/volume/journal checks remain mandatory.
    """
    if not REPAIR_BETA_GUARDED:
        return {'status': 'engineering_build'}
    from .repair_strategy import advise
    from .health import media_from_smart
    if args.command != 'care-external':
        raise PermissionError('Guarded repair beta permits only care-external for hardware writes')
    if args.journal_backend != 'disk' or not args.journal:
        raise PermissionError('Guarded repair requires a durable journal on a separate healthy drive')
    if args.rewrite_neighbors or args.recording != 'auto':
        raise PermissionError('Guarded repair cannot force recording geometry or neighboring writes')
    if args.ack_unknown_health:
        if not (isinstance(snapshot, dict) and
                snapshot.get('source') in {'windows_native_corrob_hdd', 'windows_ata_identify_hdd'} and
                snapshot.get('native_hdd_corrob') is True and
                snapshot.get('status') == 'unknown'):
            raise PermissionError('Unknown-health acknowledgement is reserved for corroborated native Windows HDD identity')
    elif (isinstance(snapshot, dict) and
          snapshot.get('source') in {'windows_native_corrob_hdd', 'windows_ata_identify_hdd'}):
        raise PermissionError('Native HDD identification does not measure health. Explicit --ack-unknown-health is required after data rescue.')
    if args.max_regions > 16 or args.max_regions < 1:
        raise PermissionError('Guarded repair limits each batch to 16 verified regions')
    if not args.auto_lock_volumes and __import__('sys').platform == 'win32':
        raise PermissionError('Guarded repair requires exclusive Windows volume locking')
    profile = advise(model=device.model, bus=device.bus, sector=device.sector_size,
                     snapshot=snapshot)
    if not profile.can_attempt_hdd_refresh:
        raise PermissionError('Physical repair not appropriate: ' + '; '.join(profile.reasons))
    if media_from_smart(snapshot) == 'WARN' and not args.ack_media_warning:
        raise PermissionError('HDD media warning: rescue first and explicitly acknowledge --ack-media-warning')
    return profile.public()
