### Added

- A structure file's optional `kites` block gives each kite's own KA frame in the world: its origin `pos_ENU` and its orientation `Q_KA2ENU`. Points and bodies may name their kite in an optional `kite` column, which a file with several kites needs. The conventions page defines the conversion `p_KA = Rᵀ (p_ENU − o)` with a worked example, and both V3 examples carry a kite row (awesIO 1.1.0).
