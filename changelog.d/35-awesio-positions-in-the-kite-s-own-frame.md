### Added

- A structure file's `wings` rows may give the wing's own KA frame in the world, the frame its aerodynamic mesh is drawn in: its origin `pos_ENU` and its orientation `Q_KA2ENU`, as optional columns. The conventions page defines the conversion `p_KA = Rᵀ (p_ENU − o)` with a worked example, and places a structure file's kite at 90° elevation and 0° heading by convention. Both V3 examples are placed so and give their wing's frame (awesIO 1.1.0).
