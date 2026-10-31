// Menu system for bootable environment
// Provides interactive menu navigation and selection

#![allow(dead_code)]

use crate::disk::DiskInfo;
use crate::ui::input::{InputHandler, KeyCode};
use core::option::Option;

#[cfg(feature = "alloc")]
extern crate alloc;

#[cfg(feature = "alloc")]
use alloc::string::{String, ToString};
#[cfg(feature = "alloc")]
use alloc::vec::Vec;

/// Menu item
#[derive(Debug, Clone)]
pub struct MenuItem {
    pub id: usize,
    pub label: String,
    pub description: String,
}

/// Menu system
pub struct Menu {
    title: String,
    items: Vec<MenuItem>,
    selected: usize,
}

impl Menu {
    /// Create new menu
    pub fn new(title: String) -> Self {
        Self {
            title,
            items: Vec::new(),
            selected: 0,
        }
    }

    /// Add menu item
    pub fn add_item(&mut self, id: usize, label: String, description: String) {
        self.items.push(MenuItem {
            id,
            label,
            description,
        });
    }

    /// Display menu
    #[cfg(feature = "std")]
    pub fn display(&self) {
        println!("\n{}", self.title);
        println!("{}", "=".repeat(self.title.len()));
        println!();

        for (index, item) in self.items.iter().enumerate() {
            let marker = if index == self.selected { ">" } else { " " };
            println!("{} [{}] {}", marker, item.id, item.label);
            if !item.description.is_empty() {
                println!("    {}", item.description);
            }
        }
        println!();
    }

    /// Handle keyboard input and return selected item ID
    pub fn handle_input(&mut self) -> Option<usize> {
        loop {
            match InputHandler::wait_for_key() {
                KeyCode::Up | KeyCode::Char('w') | KeyCode::Char('W') => {
                    if self.selected > 0 {
                        self.selected -= 1;
                    } else {
                        self.selected = self.items.len().saturating_sub(1);
                    }
                    #[cfg(feature = "std")]
                    self.display();
                }
                KeyCode::Down | KeyCode::Char('s') | KeyCode::Char('S') => {
                    if self.selected < self.items.len().saturating_sub(1) {
                        self.selected += 1;
                    } else {
                        self.selected = 0;
                    }
                    #[cfg(feature = "std")]
                    self.display();
                }
                KeyCode::Enter if !self.items.is_empty() => {
                    return Some(self.items[self.selected].id);
                }
                KeyCode::Escape => {
                    return None;
                }
                KeyCode::Digit(d) => {
                    // Direct selection by number
                    let index = d as usize;
                    if index < self.items.len() {
                        self.selected = index;
                        return Some(self.items[index].id);
                    }
                }
                _ => {}
            }
        }
    }

    /// Show disk selection menu
    #[cfg(feature = "alloc")]
    pub fn show_disk_selection(disks: &[DiskInfo]) -> Option<usize> {
        let mut menu = Menu::new("Select Drive to Repair".to_string());

        for (index, disk) in disks.iter().enumerate() {
            let interface_str = match disk.interface {
                crate::disk::DiskInterface::ATA => "ATA",
                crate::disk::DiskInterface::SATA => "SATA",
                crate::disk::DiskInterface::NVMe => "NVMe",
                crate::disk::DiskInterface::USB => "USB",
                crate::disk::DiskInterface::Unknown => "Unknown",
            };

            let size_str = crate::disk::detection::format_size(disk.size_bytes);
            let label = format!("{} - {} ({})", interface_str, &disk.model, size_str);
            let description = format!("Serial: {}", &disk.serial);

            menu.add_item(index, label, description);
        }

        menu.add_item(
            disks.len(),
            "Cancel".to_string(),
            "Exit without selecting".to_string(),
        );

        #[cfg(feature = "std")]
        menu.display();

        menu.handle_input()
    }

    /// Show repair options menu
    pub fn show_repair_options() -> Option<RepairOption> {
        let mut menu = Menu::new("Repair Options".to_string());

        menu.add_item(0, "Quick Scan".to_string(), "Fast surface scan".to_string());
        menu.add_item(
            1,
            "Full Scan".to_string(),
            "Complete surface scan".to_string(),
        );
        menu.add_item(
            2,
            "SMART Check".to_string(),
            "Check SMART status only".to_string(),
        );
        menu.add_item(3, "Cancel".to_string(), "Return to main menu".to_string());

        #[cfg(feature = "std")]
        menu.display();

        match menu.handle_input() {
            Some(0) => Some(RepairOption::QuickScan),
            Some(1) => Some(RepairOption::FullScan),
            Some(2) => Some(RepairOption::SmartCheck),
            _ => None,
        }
    }
}

/// Repair option selection
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum RepairOption {
    QuickScan,
    FullScan,
    SmartCheck,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_menu_creation() {
        let menu = Menu::new("Test Menu".to_string());
        assert_eq!(menu.title, "Test Menu");
        assert_eq!(menu.items.len(), 0);
        assert_eq!(menu.selected, 0);
    }

    #[test]
    fn test_menu_add_item() {
        let mut menu = Menu::new("Test Menu".to_string());
        menu.add_item(0, "Item 1".to_string(), "Description".to_string());
        assert_eq!(menu.items.len(), 1);
        assert_eq!(menu.items[0].label, "Item 1");
    }
}
