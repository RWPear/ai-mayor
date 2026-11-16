"""Tuning knobs. Everything here can be overridden in content/balance.yaml, so
balancing never needs a code change - change the YAML, rerun a scenario.
"""
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CONTENT = ROOT / "content"

DEFAULTS = {
    # ---- wards (neighbourhoods)
    "ward_cap": 500,              # a new ward opens when every ward has this many people
    "first_wards": 3,             # wards the city starts with
    # ---- economy
    "start_treasury": 20000.0,
    "start_tax_rate": 0.15,
    "max_tax_rate": 0.45,
    "cost_of_living": 55.0,       # per citizen per day, before housing quality
    "service_cost_per_capita": 4.5,  # per service: spending per citizen per day to hold quality at 1.0
    "service_drift": 0.12,        # how fast service quality moves toward what's funded
    "debt_interest": 0.002,       # per day on negative treasury
    "debt_limit_pc": 25.0,        # the city can't spend into debt deeper than this per citizen
    # ---- people
    "mood_drift": 0.25,           # how fast mood moves toward its target each day
    "service_weight": 0.8,        # how much city services move moods
    "tax_sensitivity": 2.2,       # how much taxes hurt (business feels it most)
    "loyalty_drift": 0.05,        # how fast approval drifts back toward mood (low = grudges last)
    "approval_fatigue": 0.004,    # approval quietly erodes each day unless the mayor earns it back
    "timeout_penalty": 0.04,      # approval lost when an event runs out with nothing fixed
    "helped_bonus": 0.02,         # approval gained when the city pulls through an event
    "tax_shock": 1.5,             # approval hit per point of tax rise (x faction tax pain)
    "leave_mood": 0.15,           # below this for leave_days -> they move away
    "leave_days": 3,
    "protest_share": 0.12,        # share of a ward protesting that turns into a street protest
    "riot_unrest": 0.75,          # ward unrest that turns a protest into a riot
    # ---- commands
    "command_weight": 1.0,        # how strongly a command moves its citizen
    "status_cooldown_days": 1,
    # ---- seasons
    "season_days": 30,
    "recall_threshold": 0.5,      # share voting RECALL needed to remove the mayor
    "silent_vote_weight": 0.1,    # residents who don't comment still vote, but each counts this much
                                  # (keeps the comment section in charge, without ignoring everyone else)
    # ---- storyteller
    "tension_target_start": 0.25,
    "tension_target_end": 0.7,    # tension ramps up across a season toward the finale
    "max_active_events": 2,
    "event_effort": 0.6,          # lower = events need fewer helpers (tune to your real comment rate)
    "event_cooldown_days": 2,     # at least this many days between new events
    "protest_contagion": 0.02,    # approval lost by everyone in a ward with a street protest, per day
}


def load():
    cfg = dict(DEFAULTS)
    f = CONTENT / "balance.yaml"
    if f.exists():
        cfg.update(yaml.safe_load(f.read_text()) or {})
    return cfg
