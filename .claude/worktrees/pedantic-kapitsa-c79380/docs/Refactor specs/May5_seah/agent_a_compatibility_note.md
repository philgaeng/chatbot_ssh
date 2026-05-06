# Agent A compatibility note (integration sync gate)

- Ticketing geography contract is present in this worktree via migration `f1a3e9c72b05` and models in `ticketing/models/country.py`.
- Required tables are implemented: `ticketing.countries`, `ticketing.location_level_defs`, `ticketing.locations`, `ticketing.location_translations`.
- Ticketing migration stream currently has a single head: `e8d4b6a0f291`.
- Public migration stream currently has a single head before this tranche: `pub001_seah_reporter_category`.
- Agents B/C/D/E can proceed against this ticketing contract without guessing table shape.
