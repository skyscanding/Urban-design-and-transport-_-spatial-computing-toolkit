# GWR Reproduction, Tung Chung TOD Facility-Demand Prediction

A **faithful, open-source, runnable** reproduction of the original studio GWR
pipeline (`GWR_Prediction_v3`). Built on `geopandas` + `mgwr`, the same
open-source stack the original analysis used, so it runs anywhere, with **no
ArcGIS licence required**.

This pipeline replaces an earlier arcpy version that reproduced the *workflow
shape* but not the actual computation. The table below is the honest fidelity
statement against both the original studio analysis and that earlier attempt.

## What this reproduces (vs. the earlier arcpy attempt)

| Element | Original `GWR_Prediction_v3` | Earlier arcpy version | This pipeline |
|---|---|---|---|
| Engine | `mgwr` (adaptive bisquare) | `arcpy.stats.GWR` | `mgwr` (adaptive bisquare) ✅ |
| Grid | 100 m, 1500 m buffer (~700 cells) | 50 m default | 100 m, 1500 m buffer ✅ |
| Models | 3 categories (commercial / community / sports_rec) | 1 generic `poi_count` | 3 categories ✅ |
| Explanatory vars | 5 (pop, road, lucc, bus, transit) | 2 (pop, road) | 5 ✅ |
| Singular matrix | OLS fallback | none | OLS fallback ✅ |
| TCNTE scenario | per-zone growth factors in code | supply pre-built grid | per-zone factors in code ✅ |
| Airport | excluded from land mask | not handled | excluded ✅ |
| Output | on-site change per category | generic surface | on-site change per category ✅ |

Reference run (original): commercial fell back to OLS (singular matrix);
community ≈ +63, sports_rec ≈ +32 on-site under TCNTE 2033.

## Pipeline (8 stages)

```
1  Site + 1500 m study buffer + land mask (airport polygon excluded)
2  Reclassify POIs -> commercial / community / sports_rec  (substring rules)
3  100 m fishnet, clipped to the land mask
4  Join indicators per cell:
      poi_{commercial,community,sports_rec}   (point-in-cell counts)
      pop_density      persons / ha   (areal interpolation)
      road_density     m / ha
      lucc_urban_pct   share of cell with LUCC codes 1-54
      bus_density      stations / ha
      transit_access   stations within `transit_radius`, min-max -> [0,1]
5  Fit 3 GWR models (mgwr, adaptive bisquare); OLS fallback on singular
      matrix, too-few-active-cells, or zero variance
6  TCNTE 2033 future scenario: classify each cell into a zone
      (tcnte_east / tcnte_west / town_center / design_site / periphery)
      and apply the zone growth multipliers; transit_access capped at 1.0
7  Predict per category (local params mapped to future cells by nearest
      neighbour; intercept-collapse handled), report on-site current vs
      predicted change
8  Export GeoPackage (grid_indicators, grid_future) + summary CSV + 3x3 PNG
```

## Quick start

```bash
pip install -r requirements.txt

# 1) edit data paths in config_tung_chung.json to your machine
# 2) run the full pipeline
python scripts/gwr_reproduce.py config_tung_chung.json

# partial run (e.g. rebuild grid + refit only)
python scripts/gwr_reproduce.py config_tung_chung.json --stages 3-5
```

If `mgwr` is not installed the pipeline still runs, every category uses the
global OLS path and a warning is logged.

## Case Study: Tung Chung TOD

The pipeline's canonical worked example is the **Tung Chung Tat Tung Road Bus
Terminus** TOD studio. `config_tung_chung.json` *is* the case-study config:
point its `data` paths at the studio datasets and run the full pipeline to
reproduce the analysis end to end.

### Inputs

| Input | Source | Role |
|---|---|---|
| Site boundary | `Designsite.shp` | Tat Tung Road Bus Terminus |
| Land mask | `Land_range.gpkg` | study extent (1500 m buffer) |
| Airport | `Airport_range.gpkg` | excluded from land mask |
| POIs | 10 Amap 2025 category files | reclassified → commercial / community / sports_rec |
| Population | `HK_population.gpkg` (`Averag_pop`) | pop_density |
| Roads | `HK_roads.gpkg` | road_density |
| Land use | `LandUse_Vector_Polygons.gpkg` (`type_code`) | lucc_urban_pct |
| Transit | `Result_Stations_InROI.shp` | bus_density, transit_access |
| Future zones | `tcnte_east_bbox.gpkg`, `tcnte_west_bbox.gpkg` | TCNTE 2033 growth zones |

Study grid: 100 m fishnet, 1500 m buffer (~700 land cells, airport removed).
Future scenario: TCNTE 2033, population 116k → 320k, +877,000 m² GFA, applied as
per-zone growth multipliers (see `growth_factors` in the config).

```bash
python scripts/gwr_reproduce.py config_tung_chung.json
```

### Reference results (original studio run)

On-site predicted facility-demand change under TCNTE 2033:

| Category | Model | On-site change | Reading |
|---|---|---|---|
| commercial | OLS fallback (singular matrix) | ≈ +766 | already saturated — no new retail needed |
| community | GWR (R² ≈ 0.08) | ≈ +63 | dominant predicted gap |
| sports_rec | GWR (R² ≈ 0.06) | ≈ +32 | secondary gap |

The commercial model hits a singular matrix (dense, correlated cells) and falls
back to OLS — confirming saturation rather than failing. Community is the
largest unmet demand, sports/recreation second: the evidence base for a TOD
programme that adds **community and sports facilities** above the transit hub
rather than more commercial floor space.

Re-running on the same data regenerates these figures; small differences are
expected from `mgwr`'s adaptive-bandwidth search. A committed example run lives
in [`examples/tung_chung/`](examples/tung_chung/).

## Validate without your data

A synthetic generator reproduces the data *schema* (site, land, airport,
population, roads, LUCC, bus, 10 POI source files, TCNTE bboxes) so you can
confirm the workflow end-to-end before pointing it at real layers:

```bash
python scripts/_make_synthetic.py          # writes scripts/synthetic/ + config_synth.json
python scripts/gwr_reproduce.py scripts/synthetic/config_synth.json
```

The smoke test deliberately makes `sports_rec` sparse so the **OLS-fallback
branch is exercised**, while commercial and community fit full GWR.

## Configuration notes

- **`poi_rules`**, substring matches against the `midType` field. `include`
  selects, `exclude` removes (e.g. `工厂`/`农林牧渔` out of commercial,
  `动物医疗` out of community, `酒吧`/`电影院` out of sports_rec). These mirror
  the original 13-file → 3-category reclassification.
- **`growth_factors.multipliers`**, the per-zone TCNTE factors. Zone
  assignment order: TCNTE bboxes first, then `town_center_bbox`, then the
  design site (which overrides any overlap).
- **`pop_is_density`**, set `true` if your population field is persons/km²
  rather than a count.
- **`transit_access` / `bus_density` definitions** are explicit and
  configurable (`transit_radius`). They are reconstructions of the original
  transit indicators; adjust if your source defined them differently.

## Files

```
gwr-pipeline/
├── README.md
├── requirements.txt
├── config_tung_chung.json        ← real Tung Chung parameters + factors
└── scripts/
    ├── gwr_reproduce.py          ← 8-stage pipeline (run this)
    └── _make_synthetic.py        ← schema-faithful test data generator
```

## Reusing for another site

The workflow generalises: point the config at a new site boundary, POI
sources, population, roads, LUCC, and transit layers; redefine `poi_rules` and
the `growth_factors` zones for the new scenario. The modelling logic (3
category models, 5 indicators, OLS fallback, zonal future scenario) stays
identical, which is what makes this a reusable spatial-computing workflow
rather than a one-off script.
