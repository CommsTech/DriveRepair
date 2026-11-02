//! Read-only vendor capability classification, NOT a firmware repair engine.
//!
//! Brand hints are not enough to identify a service-area layout, firmware
//! generation, ATA passthrough command sequence, or USB bridge compatibility.
//! No vendor-specific command or firmware write may be synthesized from these
//! heuristics. Future devices require exact-model and firmware-revision proof.

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum VendorHint {
    Seagate, WesternDigital, Toshiba, Other,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum FirmwarePrivilege {
    ReadOnlyMetadata,
}

pub struct FirmwareIdentity<'a> {
    pub model: &'a str,
    pub revision: &'a str,
    pub transport: &'a str,
}

pub trait ReadOnlyFirmwareInspector {
    fn vendor_hint(&self) -> VendorHint;
    fn required_privilege(&self) -> FirmwarePrivilege {
        FirmwarePrivilege::ReadOnlyMetadata
    }
    fn supports_firmware_write(&self) -> bool { false }
    fn notes(&self) -> &'static str {
        "Read-only inventory. Manufacturer recovery modes and service-area changes are unsupported."
    }
}

pub struct GenericInspector { vendor: VendorHint }

impl GenericInspector {
    pub fn for_identity(identity: &FirmwareIdentity<'_>) -> Self {
        let model = identity.model.trim().to_ascii_uppercase();
        let vendor = if model.starts_with("ST") || model.starts_with("SEAGATE") {
            VendorHint::Seagate
        } else if model.starts_with("WDC") || model.starts_with("WD ") || model.starts_with("WESTERN DIGITAL") {
            VendorHint::WesternDigital
        } else if model.starts_with("TOSHIBA") {
            VendorHint::Toshiba
        } else {
            VendorHint::Other
        };
        Self { vendor }
    }
}

impl ReadOnlyFirmwareInspector for GenericInspector {
    fn vendor_hint(&self) -> VendorHint { self.vendor }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn vendor_is_a_hint_never_write_permission() {
        for (name, expected) in [
            ("ST1000LM048", VendorHint::Seagate),
            ("WDC WD10", VendorHint::WesternDigital),
            ("TOSHIBA HD", VendorHint::Toshiba),
            ("Unidentified USB bridge", VendorHint::Other),
        ] {
            let info = FirmwareIdentity {model: name, revision: "X1", transport: "USB"};
            let inspector = GenericInspector::for_identity(&info);
            assert_eq!(inspector.vendor_hint(), expected);
            assert_eq!(inspector.required_privilege(), FirmwarePrivilege::ReadOnlyMetadata);
            assert!(!inspector.supports_firmware_write());
        }
    }
}
