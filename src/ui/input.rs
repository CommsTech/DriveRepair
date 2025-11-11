// Input handling for bootable environment
// Provides keyboard input for disk selection and menu navigation

#![allow(dead_code)]

/// Input handler for bootable environment
pub struct InputHandler;

impl InputHandler {
    /// Wait for key press and return key code
    /// Returns None if no key available
    pub fn get_key() -> Option<KeyCode> {
        // TODO: Implement keyboard input
        // For BIOS: Use INT 16h, AH=0x00 (Read Key)
        // For UEFI: Use Simple Text Input protocol
        // For std: Use stdin
        None
    }

    /// Wait for key press (blocking)
    pub fn wait_for_key() -> KeyCode {
        loop {
            if let Some(key) = Self::get_key() {
                return key;
            }
        }
    }

    /// Read number from input
    pub fn read_number(max: usize) -> Option<usize> {
        let mut digits = Vec::new();

        loop {
            match Self::wait_for_key() {
                KeyCode::Digit(d) => {
                    digits.push(d);
                    // TODO: Display digit
                }
                KeyCode::Enter => {
                    if !digits.is_empty() {
                        let mut num = 0;
                        for &digit in &digits {
                            num = num * 10 + digit as usize;
                        }
                        if num <= max {
                            return Some(num);
                        }
                    }
                    return None;
                }
                KeyCode::Escape => {
                    return None;
                }
                KeyCode::Backspace => {
                    if !digits.is_empty() {
                        digits.pop();
                        // TODO: Erase last digit from display
                    }
                }
                _ => {}
            }
        }
    }

    /// Prompt for yes/no
    pub fn prompt_yes_no() -> bool {
        loop {
            match Self::wait_for_key() {
                KeyCode::Char('y') | KeyCode::Char('Y') => return true,
                KeyCode::Char('n') | KeyCode::Char('N') => return false,
                _ => {}
            }
        }
    }
}

/// Key codes for keyboard input
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum KeyCode {
    /// Digit key (0-9)
    Digit(u8),
    /// Character key
    Char(char),
    /// Enter/Return key
    Enter,
    /// Escape key
    Escape,
    /// Backspace key
    Backspace,
    /// Arrow keys
    Up,
    Down,
    Left,
    Right,
    /// Function keys
    F1,
    F2,
    F3,
    F4,
    F5,
    F6,
    F7,
    F8,
    F9,
    F10,
    F11,
    F12,
    /// Other keys
    Tab,
    Space,
    Unknown,
}

#[cfg(feature = "std")]
impl InputHandler {
    /// Read input from stdin (for std environment)
    pub fn read_from_stdin() -> Option<String> {
        use std::io;
        let mut buffer = String::new();
        io::stdin().read_line(&mut buffer).ok()?;
        Some(buffer.trim().to_string())
    }
}
