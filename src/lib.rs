// Main library module
// Core functionality for drive repair tool

#![cfg_attr(not(feature = "std"), no_std)]

#[cfg(feature = "alloc")]
extern crate alloc;

#[cfg(feature = "std")]
extern crate std;

// Prelude for no_std compatibility
#[cfg(not(feature = "std"))]
pub mod prelude {
    pub use core::clone::Clone;
    pub use core::convert::From;
    pub use core::default::Default;
    pub use core::iter::Iterator;
    pub use core::marker::{Send, Sync};
    pub use core::ops::{Fn, FnMut};
    pub use core::option::Option::{self, None, Some};
    pub use core::result::Result::{self, Err, Ok};
}

pub mod disk;
pub mod platform;
pub mod repair;
#[cfg(feature = "alloc")]
pub mod rescue;
pub mod smart;
pub mod ui;

// Re-export commonly used types
pub use disk::{AccessMode, DeviceIdentity, Disk, DiskError, DiskInfo, DiskInterface};
pub use repair::{RepairConfig, RepairEngine, RepairResult, RepairStats, SectorOutcome};
pub use smart::{SmartHealthStatus, SmartInterface};
