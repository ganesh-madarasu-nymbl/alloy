# Real-paper protocol review, October 21, 2026

An independent read-only reviewer checked the three existing reviewed sources and
three additional primary works. **No exact eligible cross-paper pair was found.**
This is a bounded finding about these six works, not proof that no pair exists.
M7 remains open; synthetic campaign tests do not close it.

The implementation fixes degree-2 polynomial features, STLSQ, 20 ensemble models,
training start (-8, 8, 27), default finite differences/smoothing and Gaussian state
noise scaled by each state's standard deviation. Its scalar is aggregate relative
Frobenius coefficient error. Matching only the six exposed condition keys does not
establish agreement on these fixed implementation choices.

| Primary source / location | Reproduction gap |
| --- | --- |
| [Brunton et al. 1509.03580](https://arxiv.org/html/1509.03580), §4.2, Eq. 23, Figs. 4–6, Table 4 | Degree-5 features; derivative-target noise; published coefficients/trajectory errors differ from the adapter scalar. |
| [Fasel et al. 2111.10992](https://arxiv.org/html/2111.10992), Appendix A, Fig. 7 | Start (-8, 7, 27), RMS-normalized noise, 100 ensemble models, 1,000 noise realizations, inclusion thresholds and library bagging rules unsupported by this adapter. |
| [Cortiella et al. 2201.12683v2](https://arxiv.org/pdf/2201.12683), §§5–5.1, PDF pp. 14–16, Table 2 p. 24 | Start (-8, 7, 27), degree 3, absolute Gaussian sigma, retained-sample/boundary rules, l1-trend filtering and WBPDN. Neither method nor metric matches. |
| [de Silva et al. 2004.08424](https://arxiv.org/html/2004.08424), §§4–4.1 | Closest clean-data demonstration, same start and dt=.002 over [0,10), but rounded equations/plots supply no reported matching scalar or second eligible paper; solver and historical defaults need verification. §4.2 uses unsupported SR3/degree 3. |
| [Kaptanoglu et al. 2111.08481v2](https://arxiv.org/html/2111.08481) | Software/method description; no explicit matching Lorenz scalar reproduction protocol found in this review. |
| [Stevens-Haas et al. 2405.03154](https://arxiv.org/html/2405.03154), §III–III-A | MIOSR, Kalman/TV/Savitzky–Golay selection, variance-based noise and coefficient F1/MAE differ from the implemented pipeline. |

The fixed initial condition and per-state noise normalization were additional
blockers identified during this review and added to the existing evidence bundle.
No new executable Claim, scientific improvement or experiment result was invented.
A follow-up should choose one documented protocol and implement its exact dataset,
library, optimizer, noise, aggregation and seeds before claiming reproduction.
