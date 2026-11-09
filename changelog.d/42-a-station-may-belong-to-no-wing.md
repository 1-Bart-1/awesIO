### Changed

- A `spanwise_stations` row of a structure file may have a null `wing`, a station no wing owns, and empty `points`; the `wing` column stays required.
- BREAKING: `validate` refuses a structure whose station names a wing that is no row of `wings`.
