# ADR-005: Structured blocks, not arbitrary HTML

## Decision

Store validated, versioned page blocks and restricted rich-text JSON. Never arbitrary HTML/JS.

## Reason

Security, accessibility, responsive consistency, maintainability, future block migration.
Unknown block types fail safely on render instead of crashing the page.
