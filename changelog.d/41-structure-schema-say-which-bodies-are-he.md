### Added

- A structure file can say that a rigid body is held in the world, in an optional `bodies.fixed` column that defaults to false, and that a point rides a tube, in an optional `points.tube` column. A tether can say how it is placed, in optional `init_stretched_length`, `init_tether_force` and `init_stretch_frac` columns, and a wing which rigid body it moves with, in an optional `wings.body` column.
