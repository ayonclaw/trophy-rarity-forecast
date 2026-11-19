"""Forecast model for the GTA VI week-one trophy-rarity contest.

The page prints, for every trophy, the percent of the players Exophase tracks who
hold it, plus the tracked-player count.  Two things move that percent between
reads: players who were not tracked before join the denominator (which pushes the
percent down) and tracked players unlock more trophies (which pushes it up).  A
read only changes when Exophase refreshes its own cache, so a run of identical
reads means the page is stale and the next refresh may move every rate at once.

The model therefore works in three steps:

1. collapse consecutive identical page snapshots, so one refresh counts once;
2. for each trophy, fit the recent slope of its logit rate against wall-clock
   hours, and shrink that slope toward a prior chosen from the trophy's tier and
   its description (a story trophy climbs faster than a grind trophy);
3. convert the slope into a forecast with a saturating projection (a share cannot
   grow exponentially for a week) and an uncertainty that widens with the
   horizon and with the coarseness of the sample the rate was measured on.

A case whose whole history is one snapshot has no slope to fit: its page is stale
and, on launch night, measured on a sample that is about to be replaced by a much
larger one.  That case gets a dilution prior instead, with a wide spread.
"""

import math
from datetime import datetime, timezone

LEVELS = [0.05, 0.25, 0.5, 0.75, 0.95]
Z = [-1.645, -0.674, 0.0, 0.674, 1.645]

# Logit-units per hour priors, by tier, for a trophy whose recent history is too
# short to fit.  Story trophies move fastest in the first week.
TIER_PRIOR = {
    "bronze": 0.011,
    "silver": 0.008,
    "gold": 0.005,
    "platinum": 0.003,
}
STORY_PRIOR = 0.014          # a bronze story/chapter trophy
TAU_HOURS = 60.0             # saturation time of the rate's climb
MAX_SHIFT = 1.35             # caps the total logit move a single case may take
MIN_SLOPE, MAX_SLOPE = -0.002, 0.030
SPREAD_BASE, SPREAD_GROWTH = 0.30, 0.75


def clamp(x, lo, hi):
    return lo if x < lo else hi if x > hi else x


def logit(pct):
    p = clamp(pct, 0.01, 99.99) / 100.0
    return math.log(p / (1.0 - p))


def inv_logit(lg):
    return 100.0 / (1.0 + math.exp(-clamp(lg, -20.0, 20.0)))


def round4(x):
    scaled = x * 10000.0
    whole = math.floor(scaled)
    if scaled - whole >= 0.5:
        whole += 1
    value = whole / 10000.0
    return int(value) if value.is_integer() else value


def parse_time(text):
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def release_time(case):
    day = case.get("game", {}).get("release_date") or "2026-11-19"
    return datetime(int(day[0:4]), int(day[5:7]), int(day[8:10]), tzinfo=timezone.utc)


def dedup_snapshots(history):
    """Drop consecutive reads that repeat the previous snapshot exactly."""
    snaps = []
    for read in history:
        key = (read.get("players_tracked"), tuple(read.get("rates") or ()))
        if snaps and snaps[-1][0] == key:
            continue
        snaps.append((key, read))
    return [snap for _, snap in snaps]


def wls(xs, ys, ws):
    """Weighted least squares of y on x; returns slope, mean-centred residual sd."""
    sw = sum(ws)
    if sw <= 0 or len(xs) < 2:
        return 0.0, 0.0
    mx = sum(w * x for w, x in zip(ws, xs)) / sw
    my = sum(w * y for w, y in zip(ws, ys)) / sw
    sxx = sum(w * (x - mx) ** 2 for w, x in zip(ws, xs))
    if sxx <= 1e-9:
        return 0.0, 0.0
    slope = sum(w * (x - mx) * (y - my) for w, x, y in zip(ws, xs, ys)) / sxx
    resid = [y - (my + slope * (x - mx)) for x, y in zip(xs, ys)]
    dof = max(1, len(xs) - 2)
    sd = math.sqrt(sum(w * r * r for w, r in zip(ws, resid)) / sw * len(xs) / dof)
    return slope, sd


def prior_slope(trophy):
    text = (trophy.get("description") or "").lower()
    tier = (trophy.get("tier") or "bronze").lower()
    if tier == "bronze" and ("chapter" in text or "final mission" in text or "mission" in text):
        return STORY_PRIOR
    return TIER_PRIOR.get(tier, 0.010)


def trophy_series(snaps, index, t0):
    """Points (hours, logit rate, earned count) for one trophy, oldest first."""
    pts = []
    for snap in snaps:
        rates = snap.get("rates") or []
        if index >= len(rates):
            continue
        rate = rates[index]
        if rate is None:
            continue
        players = snap.get("players_tracked") or 0
        stamp = parse_time(snap["at"])
        hours = (stamp - t0).total_seconds() / 3600.0
        earned = max(0.0, float(rate) * max(players, 0) / 100.0)
        pts.append((max(hours, 0.25), logit(float(rate)), earned, float(rate)))
    return pts


def forecast_row(trophy, index, snaps, t0, target_hours):
    pts = trophy_series(snaps, index, t0)
    if not pts:
        return {"id": trophy["id"], "q": [0.01, 0.01, 0.01, 0.01, 0.01]}

    last_h, last_lg, last_earned, last_rate = pts[-1]
    dt = max(0.0, target_hours - last_h)

    if len(snaps) < 2 or len(pts) < 2:
        # One frozen snapshot: the page is stale and its rates were measured on a
        # small sample.  On launch night the next refresh lands on a far bigger
        # tracked population than the page currently reports.
        if last_h < 6.0:
            shift = -1.45 + 0.012 * dt
        elif last_h < 30.0:
            shift = -0.50 + 0.004 * dt
        else:
            shift = -0.10 + 0.002 * dt
        shift = clamp(shift, -1.6, 0.6)
        spread = 1.10
        if last_earned < 15.0:
            spread += 0.10
    else:
        window = [p for p in pts if p[0] >= last_h - 30.0] or pts
        window = window[-12:]
        xs = [p[0] for p in window]
        ys = [p[1] for p in window]
        ws = []
        for h, _, earned, _ in window:
            recency = 1.0 / (1.0 + 0.04 * (last_h - h))
            ws.append(clamp(math.sqrt(max(earned, 1.0)), 0.3, 3.0) * recency)
        slope, resid = wls(xs, ys, ws)
        slope = clamp(slope, MIN_SLOPE, MAX_SLOPE)
        prior = prior_slope(trophy)
        weight = len(window) / (len(window) + 4.0)
        slope = (1.0 - weight) * prior + weight * slope
        damp = 1.0 - math.exp(-dt / TAU_HOURS)
        shift = clamp(slope * TAU_HOURS * damp, -MAX_SHIFT, MAX_SHIFT)
        spread = math.sqrt(SPREAD_BASE ** 2 + (SPREAD_GROWTH * damp) ** 2)
        if len(window) >= 4:
            spread += min(0.35, 0.5 * resid)
        if last_earned < 15.0:
            spread += 0.10
    spread = clamp(spread, 0.30, 1.60)

    centre = last_lg + shift
    if last_rate >= 99.5:
        centre = max(centre, logit(99.5))
    qs = []
    previous = 0.01
    for z in Z:
        value = inv_logit(centre + z * spread)
        value = clamp(value, 0.01, 99.99)
        value = max(value, previous)
        qs.append(round4(value))
        previous = value
    return {"id": trophy["id"], "q": qs}


def forecast(case):
    if case.get("levels") != LEVELS:
        raise ValueError("unexpected levels: %r" % (case.get("levels"),))
    history = case.get("history") or []
    trophies = case.get("trophies") or []
    if not history:
        # Degenerate case: no read at all.  Say something wide and neutral rather
        # than crash, so the run still completes and the case stays valid.
        return {"trophies": [
            {"id": t["id"], "q": [0.05, 0.20, 0.50, 1.20, 3.50]} for t in trophies
        ]}
    snaps = dedup_snapshots(history)
    t0 = release_time(case)
    target_hours = (parse_time(case["target"]) - t0).total_seconds() / 3600.0
    rows = []
    for index, trophy in enumerate(trophies):
        rows.append(forecast_row(trophy, index, snaps, t0, target_hours))
    return {"trophies": rows}
