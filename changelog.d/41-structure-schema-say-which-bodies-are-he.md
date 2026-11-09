### Added

- A structure file can say that a rigid body is held in the world, in an optional `bodies.fixed` column, and that a point rides a tube, in an optional `points.tube` column. The validator refuses a tube name that is no row of `tubes`, and a point that rides a tube while on a body or held in the world.
