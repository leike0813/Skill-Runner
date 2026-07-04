# Design

No standalone design decision is required for this change. The implementation is a narrow prompt-construction cleanup: schema repair reruns already reuse the existing engine session, so the repair prompt must not duplicate the previous candidate preview.
