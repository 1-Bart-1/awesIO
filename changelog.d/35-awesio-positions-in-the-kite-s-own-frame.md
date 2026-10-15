### Added

- A structure file places its kite at 90° elevation and 0° heading, so a wing's KA axes are ENU's, and a `wings` row may give the origin of the wing's KA frame, the frame its aerodynamic mesh is drawn in, as an optional `pos_ENU` column. The conventions page defines the conversion `p_KA = p_ENU − o` with a worked example, and both V3 examples are placed so and give their wing's origin (awesIO 1.1.0).
