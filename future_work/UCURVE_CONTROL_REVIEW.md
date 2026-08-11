# Capstone U-Curve and Geometry-Adaptive Control Review

## Conclusion

The capstone U-curve is not a global voltage-current control law. It is an
open-loop sweep for one nominal 13.65 nN thrust target, one Ø10 mm
can/gap/aperture geometry, one plasma condition, and an electrostatic model
with no magnetic field.

A more portable control principle is:

> Maximize safe, useful escaped axial current—not emitted current—and apply
> the minimum acceleration voltage needed for the thrust target, while
> continuing to increase current only while total power decreases.

This structure can adapt to a Spindt or another field-emitter array, but it is
not completely geometry-independent: escape, beam direction, collection,
floating potential, and actuator limits remain properties of the installed
hardware and environment.

## What the capstone curve measured

The lower-voltage currents were calculated by the optimistic H1 model and then
prescribed in the PIC runs. The nominal demand remained 13.65 nN, but delivered
thrust did not remain fixed.

| Supply voltage | Emitted current | Escape | Escaped current | Delivered thrust | Specific power |
|---:|---:|---:|---:|---:|---:|
| 200 V | 0.342 mA | 98.4% | 0.337 mA | 13.65 nN | 5.01 mW/nN |
| 125 V | 0.464 mA | 93.8% | 0.435 mA | 13.09 nN | 4.43 mW/nN |
| 92.4 V | 0.601 mA | 79.9% | 0.480 mA | 11.59 nN | 4.79 mW/nN |
| 78 V | 0.840 mA | 57.4% | 0.482 mA | 10.38 nN | 6.31 mW/nN |

The decisive observation is the change from 92.4 V to 78 V: emitted current
increased by almost 40%, while escaped current remained approximately 0.48 mA.
The additional emission was lost through self-scrape inside the can instead of
becoming useful exhaust.

The experiment therefore supports controlling on escaped or return-balanced
current rather than commanded emission. It does not constitute a globally
optimized, constant-delivered-thrust surface. See the
[pre-registered U-curve plan and results](../pic_sims/ladder/capstone/UCURVE_PLAN.md).

The same 92.4 V command transmitted 99.99% in the clean isolated-gun geometry.
The strong left-arm loss is consequently attributable to the capstone can,
gap, lid, and collection fields rather than to a universal electron-gun limit.

## The correct current balance

At equilibrium, net collected ambient current equals escaped beam current:

$$
I_{\mathrm{col,net}} = I_{\mathrm{esc}}.
$$

It does not generally equal emitted current. During a transient, the body
capacitance gives

$$
C\dot{\phi} = I_{\mathrm{esc}} - I_{\mathrm{col,net}},
$$

or

$$
I_{\mathrm{esc}} = I_{\mathrm{col,net}} + C\dot{\phi}.
$$

Electrons emitted and subsequently intercepted by the cathode, lid, or body
remain internal to the spacecraft. They consume electrical power and deposit
heat or momentum, but they do not constitute exhaust. This separation is
implemented explicitly in the capstone
[charge and momentum ledger](../pic_sims/ladder/capstone/5_ucurve_valley/simulation.py#L180).

The desired-axis thrust is fundamentally

$$
F_{\parallel}[\mathrm{nN}]
= 3.372\,I_{\mathrm{esc}}[\mathrm{mA}]
  \sqrt{\kappa\left(V_a-\phi\right)[\mathrm{eV}]}\,\eta_\theta,
$$

where:

- $V_a$ is the acceleration supply voltage;
- $\phi$ is the positive spacecraft potential relative to the ambient plasma;
- $\kappa$ accounts for acceleration-energy losses;
- $\eta_\theta$ is the momentum-weighted axial factor, approximately
  $\langle\cos\theta\rangle$.

Thrust depends on escaped current, whereas supply power follows emitted source
current:

$$
P_{\mathrm{bus}}
\simeq \frac{V_a I_{\mathrm{emit}}}{\eta_{\mathrm{PPU}}}
      + P_{\mathrm{gate}} + P_{\mathrm{overhead}}.
$$

Consequently, replacing $I_{\mathrm{esc}}$ with $I_{\mathrm{emit}}$ hides
exactly the loss that produced the measured left arm.

## Why maximum current is not always minimum power

Consider the ideal limit in which transmission and collimation are perfect, so
$I=I_{\mathrm{emit}}=I_{\mathrm{esc}}$. On a fixed-thrust contour,

$$
V_a = \phi(I) + \left(\frac{F}{K I}\right)^2,
$$

and therefore

$$
P(I) = I\phi(I) + \frac{F^2}{K^2 I}.
$$

Increasing current reduces the second term: many slower electrons provide more
momentum per unit acceleration power. However, it increases the first term
because collecting a larger replacement current requires the spacecraft to
float more positively.

For the repository's high-$\chi$ collection approximation,
$\phi\propto I^{1/\alpha}$, the interior optimum satisfies

$$
V_a = \frac{2\alpha+1}{\alpha}\phi \approx 3.1\phi.
$$

Thus maximum-current operation is power-optimal only when a current constraint
binds before this interior optimum, or when the collection potential is
negligible. Even a perfectly transmitting Spindt array does not eliminate this
fundamental collection/charging trade.

The capstone can adds a second, geometry-specific tax: high perveance causes
escape to collapse, moving the measured valley from the untaxed prediction near
95 V to approximately 125 V, where $V/\phi\approx5.9$.

## Implications of a Spindt or field-emitter array

A field-emitter array could materially improve the plant by:

- increasing useful emitting area;
- reducing heater power;
- providing fast electronic current control;
- removing or widening the capstone exhaust aperture;
- separating extraction, acceleration, and collimation functions.

However, a Spindt array does not automatically produce a perfectly axial beam.
Single-gate field-emitter arrays can have appreciable initial angular spread. A
double-gate experiment reduced transverse beam energy from approximately
10.3 eV to 0.12 eV, but that result was obtained in a particular 20 keV
laboratory system and is not directly transferable to this 100–300 V regime
([Tsujino et al., Nature Communications](https://pmc.ncbi.nlm.nih.gov/articles/PMC5196429/)).

Downstream space charge also remains important. Charge emitted at excessive
density can be decelerated or reflected, and the limit depends on emitter
geometry and ambient plasma conditions
([Morris, Gilchrist, and Gallimore](https://deepblue.lib.umich.edu/bitstream/handle/2027.42/87359/467_1.pdf%3Bsequence%3D2)).

The preferred hardware architecture would therefore expose independent
actuators and measurements:

- gate/extractor voltage controls $I_{\mathrm{emit}}$;
- accelerator voltage controls exhaust energy;
- a second gate or electrostatic optic controls $\eta_\theta$;
- an isolated or instrumented collector measures net ambient return current;
- emitter, gate-interception, and accelerator currents are measured separately;
- bus-side measurement captures converter and gate losses.

Only alignment with the desired thrust vector matters. In this context,
"axial" is more precise than "horizontal."

## Recommended adaptive controller

### 1. Estimate useful escaping current

Use the measured net collection current and floating-potential derivative:

$$
\widehat I_{\mathrm{esc}}
= I_{\mathrm{col,net}} + C\dot{\phi}.
$$

At a settled operating point, the capacitive term vanishes. Floating potential
alone does not reveal current magnitude without a collection model, so a flight
implementation needs an instrumented collector or another net-current observer.

### 2. Close the thrust loop

Estimate axial thrust as

$$
\widehat F_{\parallel}
= 3.372\,\widehat I_{\mathrm{esc}}
  \sqrt{\kappa(V_a-\phi)}\,\eta_\theta,
$$

and regulate accelerator voltage to meet the requested thrust. A slower
orbit-error or acceleration loop can correct residual error in $\eta_\theta$
and $\kappa$.

### 3. Search for the minimum-power current

While the thrust loop remains closed, slowly perturb the emission-current
reference and compare measured total bus power. Increase useful current only
while power falls. This one-dimensional extremum-seeking loop learns the local
U-valley without a geometry-specific lookup table.

For safe acquisition, begin on the high-voltage/right-hand side and descend
toward the valley. The capstone measurements show that voltage overshoot is
relatively inexpensive, whereas low-voltage undershoot can cause escape
collapse and loss of the operating point.

### 4. Apply hard guards

Stop or retreat when any of the following occurs:

- body potential exceeds its benign limit;
- $dI_{\mathrm{esc}}/dI_{\mathrm{emit}}$ collapses;
- emitted current, current density, or gate interception reaches a limit;
- emitter temperature or converter power reaches a limit;
- voltage reaches the hardware ceiling;
- $\dot\phi$ or current balance has not settled;
- the thrust target remains unreachable.

An unreachable target should produce an explicit infeasible state followed by
duty-cycling or a higher-level mission response, rather than continued current
increase.

## Repository inconsistencies to resolve

The post-U-curve documentation correctly states that the untaxed
$3.12\phi$ result is only a lower bound and calls for an
escape-versus-perveance correction
([MODEL.md](../model/MODEL.md#the-measured-throttle-curve-2026-08-08--the-tax-correction)).

The executable controller nevertheless still:

- commands $V=\texttt{ctrl\_factor}\,\phi$ as its target;
- uses the fixed-perveance frontier escape interpolation;
- excludes the measured U-curve escape tax from mission operating points;
- uses the U-curve equilibria only in the secondary collection-law fit report.

See [`operating_point()`](../model/minimal_model.py#L298). At the anchor plasma
condition and a 13.65 nN demand, the current executable selects approximately
207.9 V and 0.337 mA, not the measured approximately 125 V valley.

The manuscript and presentation also continue to describe the untaxed
$3.1\phi$ rule as the optimal global controller. Those claims should be
reconciled with the measured tax and with the fact that the lower-voltage runs
held nominal target—not delivered thrust—constant:

- [paper throttle section](../paper/main.tex#L290)
- [presentation throttle slide](../paper/slides/slides.tex#L225)

Finally, every committed result remains electrostatic. The geomagnetic-field
and far-field current-closure problem is still open and prevents the present
law from being called globally flight-validated; see
[MAGNETIZED_PLAN.md](../pic_sims/thruster_characterization/MAGNETIZED_PLAN.md).

## Recommended control-law statement

> At each thrust command, estimate escaped axial current from the return-current
> and spacecraft-charge balance, regulate the minimum acceleration voltage that
> closes the thrust error, and increase emission only while measured total bus
> power falls, subject to floating-potential, transport, emitter, thermal, and
> voltage guards.

This preserves the fundamental insight behind the proposed current-first
approach while avoiding attachment to the capstone can's measured U-curve.
