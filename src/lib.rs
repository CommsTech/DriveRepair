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
    pub use core::result::Result::{self, Ok, Err};
    pub use core::option::Option::{self, Some, None};
    pub use core::marker::{Send, Sync};
    pub use core::default::Default;
    pub use core::clone::Clone;
    pub use core::ops::{Fn, FnMut};
    pub use core::iter::Iterator;
    pub use core::convert::From;
}

pub mod disk;
pub mod platform;
pub mod repair;
pub mod smart;
pub mod ui;

// Re-export commonly used types
pub use disk::{Disk, DiskError, DiskInfo, DiskInterface};
pub use repair::{RepairConfig, RepairEngine, RepairResult, RepairStats};
pub use smart::{SmartHealthStatus, SmartInterface};
