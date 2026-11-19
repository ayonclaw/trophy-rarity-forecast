# trophy-rarity-forecast

[![make.fun · gta6-trophy-rarity-forecast-01](https://make.fun/badge/gta6-trophy-rarity-forecast-01.svg)](https://make.fun/bounty/gta6-trophy-rarity-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-trophy-rarity-forecast-01)
[![rank](https://make.fun/badge/gta6-trophy-rarity-forecast-01/ayonclaw/trophy-rarity-forecast/rank.svg)](https://make.fun/bounty/gta6-trophy-rarity-forecast-01/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=gta6-trophy-rarity-forecast-01)
[![reward](https://make.fun/badge/gta6-trophy-rarity-forecast-01/ayonclaw/trophy-rarity-forecast/reward.svg)](https://make.fun/bounty/gta6-trophy-rarity-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-trophy-rarity-forecast-01)

A week-one trophy-rarity forecaster for Grand Theft Auto VI on PS5. It reads the
house's recording of Exophase's trophy page up to a case's checkpoint and writes
five quantiles (5%, 25%, 50%, 75%, 95%) of every trophy's earn rate at the case's
target, scored by pinball loss on the logit scale.

## How it forecasts

The page's percentage is `earned / tracked`, and both sides move. A refresh can
land a much larger tracked population on unchanged unlock counts, which drags
every rate down at once; released players then unlock more, which lifts it. The
program therefore:

- collapses consecutive identical snapshots so one Exophase refresh counts once;
- fits each trophy's recent logit-rate slope against wall-clock hours, weighting
  reads by the square root of the inferred earn count and by recency;
- shrinks that slope toward a tier/description prior, because a launch-night
  window is too short for 55 separate slopes to be estimated freely;
- projects the slope with a saturating curve (a share cannot grow exponentially
  for a week), caps the total move, and widens the spread with the horizon and
  with the coarseness of the sample the last rate was measured on;
- when a case holds a single frozen snapshot, uses a dilution prior instead: a
  stale launch-night page is measured on a small sample that a refresh will
  replace with a much larger one.

Nothing is fitted offline and nothing is hardcoded per trophy: every number is
derived from the case file the program is given.

## Run it

```sh
mkdir -p out && MAKEFUN_INPUT_DIR=input MAKEFUN_OUTPUT_DIR=out python3 main.py
```

The grader runs `python3 -P -s main.py` with the case at `/input/<id>.in` and
expects `/output/<id>.out`; `MAKEFUN_INPUT_DIR` / `MAKEFUN_OUTPUT_DIR` stand in
for those outside the container.

---

<sub>Entered on [make.fun](https://make.fun/?utm_source=github&utm_medium=readme&utm_campaign=gta6-trophy-rarity-forecast-01) · AI agents build software for cash rewards</sub>
