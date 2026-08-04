# Lab experiments — hardware corroboration

One subfolder per benchtop experiment. This tree sits outside the
`orbit_sims → pic_sims` data flow: nothing here is read by or written from the
other trees.

| experiment | claim demonstrated | counterpart in the ladder |
|---|---|---|
| [`electron_gun/`](electron_gun/README.md) | a net-negative cathode both emits and accelerates electrons onto a grounded collector (≈ 87 mA at −56 V, ≈ 5 Pa) | rung 1, `emitter.negative_cathode` |
