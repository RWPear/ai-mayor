"""One simulated day for every subject, all vectorised.

Order: income -> taxes -> crown spending -> services -> moods -> loyalty ->
activism/unrest -> angry crowds/riots -> people leaving -> projects ->
milestones -> lords -> petitions.
"""
import numpy as np

from . import effects
from .model import FACTION_WANTS, SERVICES, TAX_PAIN, load_yaml
from .roles import FACTIONS, FACTION_LABEL, the

MILESTONES = None
PROJECTS = None


def milestones():
    global MILESTONES
    if MILESTONES is None:
        MILESTONES = load_yaml("milestones.yaml")
    return MILESTONES


def projects_catalog():
    global PROJECTS
    if PROJECTS is None:
        PROJECTS = {p["id"]: p for p in load_yaml("projects.yaml")}
    return PROJECTS


def available_projects(city):
    building = {p["id"] for p in city.projects}
    return [p for p in projects_catalog().values()
            if p["id"] not in building and (not p.get("unlock") or p["unlock"] in city.milestones)]


def simulate(city, ctx):
    cfg, c = city.cfg, city.citizens
    a = c.active()
    report = {"notes": []}
    if not a.any():
        return report
    f = ctx.flags
    n_active = int(a.sum())

    # ---------------------------------------------------------------- economy & income
    share = lambda flag: float(f[flag][a].mean()) if n_active else 0.0
    city.economy += (1.0 + 0.15 * (city.quality["roads"] - 0.8) - city.economy) * 0.08  # drifts to its base
    economy = float(np.clip(city.economy + ctx.economy_offset + 0.6 * share("shop") - 0.8 * share("strike")
                            + 0.2 * share("work"), 0.3, 2.0))
    income = c.wage() * economy * np.where(f["work"], 1.25, 1.0) * np.where(f["strike"], 0.0, 1.0)
    business = c.faction == FACTIONS.index("guilds")
    income = income * np.where(business, 0.85 + 0.6 * share("shop") + 0.15 * (economy - 1), 1.0)
    income = np.where(a, income, 0).astype(np.float32)

    revenue = float(income.sum() * city.tax_rate)
    spending = revenue * city.spend_ratio
    cost_of_living = cfg["cost_of_living"] * (1.35 - 0.35 * city.quality["food"])
    shop_spend = np.where(f["shop"], 30.0, 0.0)
    donate = np.where(f["donate"] & (c.wealth > 60), 50.0, 0.0)
    c.wealth += np.where(a, income * (1 - city.tax_rate) - cost_of_living - shop_spend - donate, 0).astype(np.float32)
    c.wealth = np.maximum(c.wealth, -3000)
    city.treasury += revenue - spending + float(donate[a].sum())
    if city.treasury < 0:
        city.treasury *= 1 + cfg["debt_interest"]

    # ---------------------------------------------------------------- services
    pop = max(1, n_active)
    for s in SERVICES:
        funded = spending * city.budget.get(s, 0.25) / (pop * cfg["service_cost_per_capita"])
        goal = min(1.5, funded ** 0.8)
        city.quality[s] += (goal - city.quality[s]) * cfg["service_drift"]
    city.quality["festivals"] = min(1.5, city.quality["festivals"] + 0.15 * share("volunteer"))
    city.quality["defense"] = min(1.5, city.quality["defense"] + 0.15 * share("train"))

    # ---------------------------------------------------------------- mood
    ward_mod = np.zeros((len(city.wards), len(SERVICES)), np.float32)
    for wi, w in enumerate(city.wards):
        for si, s in enumerate(SERVICES):
            ward_mod[wi, si] = w["mods"].get(s, 0)
    q = np.array([city.quality[s] for s in SERVICES], np.float32)
    wants = np.array([[FACTION_WANTS[fa][s] for s in SERVICES] for fa in FACTIONS], np.float32)
    citizen_q = q[None, :] + ward_mod[c.ward]                         # each citizen's local service levels
    service_term = (wants[c.faction] * citizen_q).sum(axis=1) - 0.9
    pain = np.array([TAX_PAIN[fa] for fa in FACTIONS], np.float32)[c.faction]
    tax_term = -pain * (city.tax_rate - 0.12) * cfg["tax_sensitivity"]
    wealth_term = 0.15 * np.tanh((c.wealth - 500) / 1500)
    afford = income * (1 - city.tax_rate) - cost_of_living
    afford_term = 0.08 * np.tanh(afford / 60)
    cmd_term = 0.03 * f["protest"] + 0.04 * f["volunteer"] + 0.02 * f["shop"] - 0.01 * f["work"] + 0.01 * f["train"]
    # an empty treasury hurts: guards unpaid, roads rotting, the king borrowing from moneylenders
    debt_term = -cfg["debt_mood"] * min(1.0, max(0.0, -city.treasury) / (n_active * 15)) if city.treasury < 0 else 0.0
    unrest = np.array([w["unrest"] for w in city.wards], np.float32)[c.ward]
    target = np.clip(0.55 + cfg["service_weight"] * service_term + tax_term + wealth_term + afford_term + cmd_term
                     - 0.15 * unrest + c.temper + ctx.mood_offset + debt_term, 0, 1)
    c.mood = np.where(a, c.mood + (target - c.mood) * cfg["mood_drift"], c.mood).astype(np.float32)

    # ---------------------------------------------------------------- loyalty to the king
    nudge = (0.05 * f["support"] - 0.05 * f["oppose"] - 0.03 * (f["protest"] | f["strike"])
             - cfg["approval_fatigue"])
    c.loyalty = np.where(a, np.clip(c.loyalty + (c.mood - c.loyalty) * cfg["loyalty_drift"] + nudge, 0, 1),
                         c.loyalty).astype(np.float32)

    # ---------------------------------------------------------------- activism, unrest, protests
    c.activism = np.where(a, np.clip(0.85 * c.activism + 0.4 * (f["protest"] | f["strike"])
                                     + 0.3 * np.maximum(0, 0.35 - c.mood), 0, 1), c.activism).astype(np.float32)
    for wi, w in enumerate(city.wards):
        m = a & (c.ward == wi)
        w["protest"] = 0
        if not m.any():
            w["unrest"] *= 0.8
            continue
        protesting = float((f["protest"] | f["strike"])[m].mean())
        w["unrest"] = float(np.clip(0.7 * w["unrest"] + 0.3 * (c.activism[m].mean() + max(0, 0.5 - c.mood[m].mean())),
                                    0, 1))
        if protesting >= cfg["protest_share"] or w["unrest"] > 0.55:
            riot = w["unrest"] > cfg["riot_unrest"] and city.quality["defense"] < 0.8
            w["protest"] = 2 if riot else 1
            # protests drag on everyone nearby: approval drops, shops lose business
            c.loyalty[m] = np.clip(c.loyalty[m] - cfg["protest_contagion"] * (2 if riot else 1), 0, 1)
            city.economy = max(0.4, city.economy - 0.01 * (2 if riot else 1))
            if riot:
                effects.apply(city, {"wealth_pc.guilds": -40, "mood": -0.04, "loyalty.ward": -0.05}, wi)
                city.quality["defense"] = max(0, city.quality["defense"] - 0.04)
                report["notes"].append(f"Riot in {w['name']}! Market stalls smashed and torches lit.")
            else:
                report["notes"].append(f"An angry crowd gathers in {w['name']} ({int(protesting * 100)}% of the hold "
                                       f"is out).")

    protesting_wards = sum(1 for w in city.wards if w["protest"])
    if len(city.wards) > 1 and protesting_wards >= max(2, len(city.wards) / 2):
        report["notes"].insert(0, f"Unrest across the kingdom: {protesting_wards} of {len(city.wards)} holds "
                                  f"in the streets!")

    # ---------------------------------------------------------------- moving away
    c.low_days = np.where(a & (c.mood < cfg["leave_mood"]), c.low_days + 1, 0).astype(np.int16)
    leaving = np.where(a & (c.low_days >= cfg["leave_days"]))[0]
    for i in leaving:
        c.status[i] = 1
        c.log(i, city.day, "gave up and left the kingdom")
    if len(leaving):
        report["notes"].append(f"{len(leaving)} subjects packed up and left the kingdom.")
    if city.treasury < 0 and city.day % 3 == 0:
        report["notes"].append(f"The royal treasury is {-city.treasury:,.0f} gold in debt. The guards grumble "
                               "about unpaid wages.")
    report["left"] = int(len(leaving))

    # ---------------------------------------------------------------- projects
    for p in city.projects:
        if p["status"] == "building":
            p["days_left"] -= 1
            if p["days_left"] <= 0:
                p["status"] = "done"
                p["finished"] = city.day
                effects.apply(city, projects_catalog()[p["id"]].get("effects"))
                report["notes"].append(f"{the(p['name'])[0].upper()}{the(p['name'])[1:]} is finished!")

    # ---------------------------------------------------------------- milestones
    newpop = city.population()
    report["unlocked"] = []
    for ms in milestones():
        if ms["id"] not in city.milestones and newpop >= ms["pop"]:
            city.milestones.append(ms["id"])
            # silent_if: the story already introduced this (e.g. the rival showed up in the season plan)
            from .storyteller import condition_ok
            if ms.get("silent_if") and condition_ok(city, ms["silent_if"]):
                continue
            report["unlocked"].append(ms)
            report["notes"].append(f"MILESTONE: {ms['title']} - {ms['text']}")

    # ---------------------------------------------------------------- lords (after the court unlocks)
    # the king names a lord for each hold every week: its most active, most loyal subject
    if ("court" in city.milestones or "council" in city.milestones) and city.day % 7 == 1:
        for wi, w in enumerate(city.wards):
            m = np.where(a & (c.ward == wi))[0]
            if len(m):
                score = c.counts["commands"][m] * 0.5 + c.loyalty[m] * 3 + c.counts["volunteer"][m]
                best = int(m[np.argmax(score)])
                if w["councilor"] != best:
                    w["councilor"] = best
                    c.log(best, city.day, f"was named Lord of {w['name']}")
                    report["notes"].append(f"The king named @{c.handles[best]} Lord of {w['name']}.")

    report["economy"] = round(economy, 3)
    report["revenue"] = round(revenue, 1)
    report["spending"] = round(spending, 1)
    city.petitions = petitions(city)
    return report


def petitions(city):
    """The loudest complaints, built from the numbers - no language model needed."""
    c, a = city.citizens, city.citizens.active()
    out = []
    worst_service = min(SERVICES, key=lambda s: city.quality[s])
    for fi, fa in enumerate(FACTIONS):
        m = a & (c.faction == fi)
        if not m.any():
            continue
        mood = float(c.mood[m].mean())
        if mood > 0.55:
            continue
        top = max(FACTION_WANTS[fa], key=lambda s: FACTION_WANTS[fa][s] * (1.2 - city.quality[s]))
        ask = "lower taxes" if fa == "guilds" and city.tax_rate > 0.18 else f"better {top}"
        signers = np.where(m)[0]
        loud = signers[np.argsort(-c.activism[signers])][:3]
        out.append({"id": f"p{city.day}-{fa}", "faction": fa, "from": FACTION_LABEL[fa], "ask": ask,
                    "mood": round(mood, 2), "signatures": int(m.sum()),
                    "voices": ["@" + c.handles[i] for i in loud]})
    for w in sorted(city.ward_stats(), key=lambda w: -(w["unrest"] or 0))[:2]:
        if w["unrest"] > 0.4:
            out.append({"id": f"p{city.day}-w{w['id']}", "faction": "ward", "from": w["name"],
                        "ask": f"fix {worst_service} in {w['name']}", "mood": w["mood"], "signatures": w["pop"],
                        "voices": []})
    return out
