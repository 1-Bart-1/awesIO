### Changed

- A tether's `start_point` and `end_point` may be null, meaning the tether starts at its first segment's first point or ends at its last segment's second point. Both stay required columns in place, so every existing structure file is still valid.
