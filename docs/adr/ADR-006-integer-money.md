# ADR-006: Integer money

## Decision
Store money as integer minor units (paise) with an explicit currency code.

## Reason
Avoid floating-point rounding errors. ₹899.00 is stored as 89900 INR paise. Percentages use
basis points. Historical orders snapshot prices and never change with the catalogue.
