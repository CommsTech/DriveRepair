// Main library module
// Core functionality for drive repair tool

#![cfg_attr(not(feature = "std"), no_std)]

#[cfg(feature = "alloc")]
extern crate alloc;

#[cfg(feature = "std")]
extern crate std;

pub mod disk;
pub mod platform;
pub mod repair;
pub mod smart;
pub mod ui;

// Re-export commonly used types

// Re-export commonly used types
pub use disk::{Disk, DiskError, DiskInfo, DiskInterface};
pub use repair::{RepairConfig, RepairEngine, RepairResult, RepairStats};
pub use smart::{SmartHealthStatus, SmartInterface};
