"""Limitful — distributed rate-limiting primitives (Python).

This package is a Python implementation of the Limitful specification. It is
currently under active development; no public API is stable until v1.0.0.

Design overview
===============
The package will eventually provide building blocks for coordinated rate
limiting, leader election, and distributed mutual exclusion across
heterogeneous clients (Rust, Python, TypeScript, Go, C#). Each subsystem
lives in its own workspace distribution so optional integrations
(OpenTelemetry, Redis sync, etc.) can be added as siblings rather than
nested inside ``main``.

Current status
==============
**Scaffold only.** No algorithms or network code are implemented yet.
"""

__version__ = "0.0.0"
