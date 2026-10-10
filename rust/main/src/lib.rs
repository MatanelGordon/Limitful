//! Limitful — distributed rate-limiting primitives.
//!
//! This crate is a Rust implementation of the Limitful specification. It is
//! currently under active development; no public API is stable until v1.0.0.
//!
//! ## Design overview
//!
//! The crate will eventually provide building blocks for coordinated rate
//! limiting, leader election, and distributed mutual exclusion across
//! heterogeneous clients (Rust, Python, TypeScript, Go, C#).  Each sub-system
//! will live in its own workspace crate so optional integrations (OpenTelemetry,
//! Redis sync, etc.) can be added as siblings rather than nested inside `main`.
//!
//! ## Current status
//!
//! **Scaffold only.** No algorithms or network code are implemented yet.

#[cfg(test)]
mod tests {
    #[test]
    fn works() {
        assert_eq!(2 + 2, 4);
    }
}
