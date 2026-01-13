# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog, and this project adheres to
Semantic Versioning.

## [Unreleased]

### Added

### Changed

### Fixed

## [1.3.3] - 2026-01-13

### Added
- Add `--version` flag and lobby `version` command to display the current release.

## [1.3.2] - 2026-01-12

### Fixed
- Reject SAN capture notation when no capture is available (e.g., `Nxe5` without a target).

## [1.3.1] - 2026-01-12

### Added
- Pytest scaffolding plus initial core tests for the CLI game flow.

## [1.3.0] - 2025-12-30

### Added
- Post-game analysis powered by Stockfish, including stats, average CPL, and worst-move reporting.

## [1.2.2] - 2025-12-28

### Changed
- Exclude `book.bin` from built distributions to keep packages smaller.
- Documentation updates.

## [1.2.1] - 2025-12-28

### Fixed
- Turn move numbering in PGN output.
