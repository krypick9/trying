"""Two fixed scenarios: `normal` and `stress`.

These are CHOSEN, reasonable settings, not calibrated fits. The Phase-0 matrix
(2 regimes x 2 depths x 3 paths = 12 scenarios, incl. replay and scheduled
events) is collapsed to the two the experiment actually needs: a calm baseline
and a volatile one in which the LP retreats. Depth is a single fixed mini-market
value per scenario.

sigma/jump values are in the right ballpark for 1-minute BTC but are not claimed
to match any specific day. bg_half_spread is set so the quoted spread is a few
tenths of a bp (order-of-magnitude realistic), not fitted.
"""

from .config import Scenario

SCENARIOS = {
    "normal": Scenario(
        name="normal",
        regime="normal",
        sigma_hourly=0.0026,
        jump_rate_per_hour=0.85,
        jump_mean=-0.0017,
        jump_std=0.0007,
        bg_depth_btc=0.5,
        bg_half_spread=1.0e-06,
        bg_walkaway=False,
        vol_cluster_rho=0.95,
        vol_cluster_vov=0.7,
    ),
    "stress": Scenario(
        name="stress",
        regime="stress",
        sigma_hourly=0.0043,
        jump_rate_per_hour=0.75,
        jump_mean=-0.0019,
        jump_std=0.0005,
        bg_depth_btc=0.5,
        bg_half_spread=1.0e-06,
        bg_walkaway=True,
        vol_cluster_rho=0.97,
        vol_cluster_vov=0.9,
        # optional endogenous-stress trigger: one scheduled -5% index shock
        # near the middle of the run. Set shock_frac=None to disable.
        shock_frac=0.5,
        shock_return=-0.05,
    ),
}


def get_scenario(name: str) -> Scenario:
    if name not in SCENARIOS:
        raise ValueError(f"unknown scenario {name!r}; choose from {list(SCENARIOS)}")
    return SCENARIOS[name]
