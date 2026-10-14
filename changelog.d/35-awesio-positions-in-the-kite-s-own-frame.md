### Added

- A structure file's optional `placement` block puts the kite in the world: per row a base point at the ground station, its ENU position, and an elevation, azimuth and heading in degrees, applied as the conventions page defines with a worked example. The page defines an azimuth, from east towards north, beside the bearing, and how it converts to a bearing and to KiteUtils.jl's `azimuth_east`. Points and bodies name their row in an optional `placement` column, which may be left out where there is one row.

### Changed

- BREAKING: structure positions are in the kite's KA frame rather than in ENU, with its origin at the point the new required `metadata.origin_point` names, which must sit at `[0, 0, 0]`. Renamed `pos_ENU` to `pos_KA`, `Q_KA2ENU` to `Q_body2KA` and `extra_inertia_KA` to `extra_inertia_body`; a body's own frame is `_body`. The V3 examples are converted to awesIO 2.0.0.
