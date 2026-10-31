// Error recovery strategies
// Implements various retry and recovery mechanisms for disk operations
// Gate 0: never claim verified from nonzero CRC alone; max_attempts==0 is fail-closed

use core::clone::Clone;
use core::default::Default;
use core::ops::FnMut;
use core::result::Result;

/// Retry strategy for disk operations
#[derive(Debug, Clone, Copy, PartialEq)]
pub enum RetryStrategy {
    /// No retry
    None,
    /// Fixed delay between retries
    FixedDelay(u32), // milliseconds
    /// Exponential backoff
    ExponentialBackoff {
        initial_delay_ms: u32,
        max_delay_ms: u32,
        multiplier: f32,
    },
    /// Linear backoff
    LinearBackoff {
        initial_delay_ms: u32,
        increment_ms: u32,
        max_delay_ms: u32,
    },
}

impl RetryStrategy {
    /// Calculate delay for retry attempt
    pub fn delay_for_attempt(&self, attempt: u32) -> u32 {
        match self {
            RetryStrategy::None => 0,
            RetryStrategy::FixedDelay(delay) => *delay,
            RetryStrategy::ExponentialBackoff {
                initial_delay_ms,
                max_delay_ms,
                multiplier,
            } => {
                let delay = (*initial_delay_ms as f32) * multiplier.powi(attempt as i32);
                delay.min(*max_delay_ms as f32) as u32
            }
            RetryStrategy::LinearBackoff {
                initial_delay_ms,
                increment_ms,
                max_delay_ms,
            } => {
                let delay = initial_delay_ms + (increment_ms * attempt);
                delay.min(*max_delay_ms)
            }
        }
    }
}

impl Default for RetryStrategy {
    fn default() -> Self {
        RetryStrategy::ExponentialBackoff {
            initial_delay_ms: 100,
            max_delay_ms: 5000,
            multiplier: 2.0,
        }
    }
}

/// Error recovery helper
pub struct ErrorRecovery {
    strategy: RetryStrategy,
    max_attempts: u32,
}

impl ErrorRecovery {
    /// Create new error recovery instance
    pub fn new(strategy: RetryStrategy, max_attempts: u32) -> Self {
        Self {
            strategy,
            max_attempts,
        }
    }

    /// Execute operation with retry logic.
    /// If `max_attempts == 0`, returns `Err(E::default())` without panicking
    /// and without treating the operation as successful.
    pub fn retry<F, T, E>(&self, mut operation: F) -> Result<T, E>
    where
        F: FnMut() -> Result<T, E>,
        E: Clone + Default,
    {
        if self.max_attempts == 0 {
            // Fail-closed: zero attempts configured — do not call operation, do not unwrap
            return Err(E::default());
        }

        let mut last_error: Option<E> = None;

        for attempt in 0..self.max_attempts {
            match operation() {
                Ok(result) => return Ok(result),
                Err(e) => {
                    last_error = Some(e.clone());

                    if attempt + 1 < self.max_attempts {
                        let delay = self.strategy.delay_for_attempt(attempt);
                        if delay > 0 {
                            // EXPERIMENTAL/UNSUPPORTED: platform-specific delay not wired yet
                            let _ = delay;
                        }
                    }
                }
            }
        }

        match last_error {
            Some(e) => Err(e),
            None => Err(E::default()),
        }
    }
}

/// Sector verification methods
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum VerificationMethod {
    /// No verification
    None,
    /// Simple checksum (XOR)
    Checksum,
    /// CRC32
    Crc32,
    /// ECC (Error Correcting Code) if available
    Ecc,
}

/// Honest verification outcome — never claim Verified without an expected value
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum VerificationResult {
    /// Data matched the expected CRC / checksum
    Verified,
    /// No expected value was provided; integrity unknown
    Unverified,
    /// Expected value was provided and did not match
    Mismatch,
}

/// Verify sector data against an optional expected CRC32.
/// Passing `None` always yields `Unverified` — nonzero CRC alone is never "verified".
pub fn verify_against_expected(data: &[u8], expected_crc: Option<u32>) -> VerificationResult {
    match expected_crc {
        None => {
            let _ = data;
            VerificationResult::Unverified
        }
        Some(expected) => {
            use crate::repair::crc32::crc32;
            let calculated = crc32(data);
            if calculated == expected {
                VerificationResult::Verified
            } else {
                VerificationResult::Mismatch
            }
        }
    }
}

/// Legacy helper retained for callers that still pass a method.
/// Without an expected CRC this never returns true for Crc32/Ecc/Checksum "verified".
pub fn verify_sector(data: &[u8], method: VerificationMethod) -> bool {
    match method {
        VerificationMethod::None => false,
        VerificationMethod::Checksum | VerificationMethod::Crc32 | VerificationMethod::Ecc => {
            // Gate 0: never claim verified from content heuristics alone
            let _ = data;
            false
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::disk::DiskError;

    #[test]
    fn test_retry_strategy_fixed_delay() {
        let strategy = RetryStrategy::FixedDelay(100);
        assert_eq!(strategy.delay_for_attempt(0), 100);
        assert_eq!(strategy.delay_for_attempt(5), 100);
    }

    #[test]
    fn test_retry_strategy_exponential() {
        let strategy = RetryStrategy::ExponentialBackoff {
            initial_delay_ms: 100,
            max_delay_ms: 1000,
            multiplier: 2.0,
        };
        assert_eq!(strategy.delay_for_attempt(0), 100);
        assert_eq!(strategy.delay_for_attempt(1), 200);
        assert_eq!(strategy.delay_for_attempt(2), 400);
        assert_eq!(strategy.delay_for_attempt(3), 800);
        assert_eq!(strategy.delay_for_attempt(4), 1000);
    }

    #[test]
    fn test_verify_against_expected_none_is_unverified() {
        let data = [0x01, 0x02, 0x03, 0x04];
        assert_eq!(
            verify_against_expected(&data, None),
            VerificationResult::Unverified
        );
    }

    #[test]
    fn test_verify_against_expected_match_and_mismatch() {
        use crate::repair::crc32::crc32;
        let data = [0x01, 0x02, 0x03, 0x04];
        let crc = crc32(&data);
        assert_eq!(
            verify_against_expected(&data, Some(crc)),
            VerificationResult::Verified
        );
        assert_eq!(
            verify_against_expected(&data, Some(crc ^ 0xFFFF)),
            VerificationResult::Mismatch
        );
    }

    #[test]
    fn test_max_attempts_zero_no_panic() {
        let recovery = ErrorRecovery::new(RetryStrategy::None, 0);
        let result: Result<(), DiskError> = recovery.retry(|| Ok(()));
        assert_eq!(result, Err(DiskError::Unsupported));
    }
}
