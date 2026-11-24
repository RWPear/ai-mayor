"""Tuning knobs. Everything here can be overridden in content/balance.yaml, so
balancing never needs a code change - change the YAML, rerun a scenario.
"""
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CONTENT = ROOT / "content"

DEFAULTS = {
    # ---- holds (regions of the kingdom; "ward" in the code)
    "ward_cap": 500,              # a new hold opens when every hold has this many people
    "first_wards": 3,             # holds the kingdom starts with
    # ---- people
    "loyalty_drift": 0.08,        # how fast loyalty to the king drifts toward mood (low = grudges last)
    "approval_fatigue": 0.004,    # loyalty quietly erodes each day unless the king earns it back
    "timeout_penalty": 0.06,      # loyalty lost when an event runs out with nothing fixed
    "helped_bonus": 0.04,         # loyalty gained when the kingdom pulls through an event
    "heed_bonus": 0.04,           # a decree vote where the king sides with the people
    "overrule_penalty": 0.06,     # ...or overrules them (those who voted the other way lose 2x this)
    "champion_weight": 2.0,       # in battles, a soldier's FIGHT counts this many times
    "leave_mood": 0.15,           # below this for leave_days -> they move away
    "leave_days": 3,
    # ---- commands
    "command_weight": 1.0,        # how strongly a command moves its citizen
    "status_cooldown_days": 1,
    # ---- seasons
    "season_days": 30,
    "recall_threshold": 0.5,      # share voting REVOLT needed to overthrow the king
    "silent_vote_weight": 0.1,    # subjects who don't comment still vote, but each counts this much
                                  # (keeps the comment section in charge, without ignoring everyone else)
    # ---- storyteller
    "tension_target_start": 0.25,
    "tension_target_end": 0.7,    # tension ramps up across a season toward the finale
    "max_active_events": 2,
    "event_effort": 0.6,          # lower = events need fewer helpers (tune to your real comment rate)
    "event_cooldown_days": 2,     # at least this many days between new events
    # ---- the island (city/living/frontier.py)
    "frontier_gold": 15,          # coins in his pocket at the start
    "frontier_passive_hours": 1.5,   # hours a settler works on an ordinary day
    "frontier_work_hours": 5.0,      # ...and on a day they comment WORK (or describe their work)
    "frontier_crown_at": 10,      # settlers needed before they vote on crowning him
    "frontier_warlord_pop": 15,   # Skarn comes once this many people live there (and it's day 6+)
}


def load():
    cfg = dict(DEFAULTS)
    f = CONTENT / "balance.yaml"
    if f.exists():
        cfg.update(yaml.safe_load(f.read_text()) or {})
    return cfg
