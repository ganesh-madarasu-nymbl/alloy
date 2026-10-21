"""Optical models for the radiative-cooling task.

Approximations, stated so a reviewer can swap in measured data:
  - SiO2: three Lorentz oscillators for its mid-IR phonon bands, roughly fitted to literature
    shapes (strong band near 9 um). Use refractiveindex.info data for real designs.
  - TiO2: lossless, n = 2.4 in the solar band and n = 2.2 in the 8-13 um window.
  - Ag: Drude model (plasma 9.0 eV, damping 0.02 eV, eps_inf 3.7), fair above ~400 nm.
  - Normal incidence, coherent layers, step-function atmosphere (transparent only in 8-13 um),
    surface at ambient temperature (300 K), sun as a 5778 K blackbody scaled to 1000 W/m^2.
"""

import numpy as np

H, C, KB = 6.62607015e-34, 2.99792458e8, 1.380649e-23

SOLAR_UM = np.linspace(0.3, 2.5, 60)
WINDOW_UM = np.linspace(8.0, 13.0, 30)
SOLAR_POWER = 1000.0  # W/m^2
T_AMBIENT = 300.0

# (center cm^-1, oscillator strength, damping cm^-1)
_SIO2_OSC = [(1072.0, 0.58, 60.0), (800.0, 0.10, 60.0), (460.0, 0.90, 25.0)]


def planck(um: np.ndarray, temp: float) -> np.ndarray:
    lam = um * 1e-6
    return 2 * H * C**2 / lam**5 / np.expm1(H * C / (lam * KB * temp))


def _lorentz(um: float, eps_inf: float, oscillators) -> complex:
    w = 1e4 / um
    return eps_inf + sum(s * w0**2 / (w0**2 - w**2 - 1j * g * w) for w0, s, g in oscillators)


def n_sio2(um: float) -> complex:
    if um < 3.0:
        return 1.45 + 0j
    return np.sqrt(_lorentz(um, 2.09, _SIO2_OSC))


def n_tio2(um: float) -> complex:
    return (2.4 + 0j) if um < 3.0 else (2.2 + 0j)


def n_ag(um: float) -> complex:
    energy = 1.23984 / um  # eV
    return np.sqrt(3.7 - 9.0**2 / (energy**2 + 1j * 0.02 * energy))


MATERIALS = {"SiO2": n_sio2, "TiO2": n_tio2, "Ag": n_ag}


def window_blackbody_power(temp: float = T_AMBIENT) -> float:
    """Hemispherical blackbody power in the 8-13 um window (W/m^2)."""
    return float(np.pi * np.trapezoid(planck(WINDOW_UM, temp), WINDOW_UM * 1e-6))
