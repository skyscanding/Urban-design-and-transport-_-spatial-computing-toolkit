# GWR Pipeline — Geographically Weighted Regression for Facility Distribution

ArcGIS Pro / arcpy pipeline that uses **Geographically Weighted Regression (GWR)** to model how facility distribution (POIs, shops, community services, sports venues) relates to built-environment indicators — then predicts future distribution from population and infrastructure projections.

No GUI. Entirely command-line driven. Validated against a real-world Tung Chung TOD case study.

## Table of Contents

- [Core Methodology](#core-methodology)
- [Case Study: Tung Chung TOD](#case-study-tung-chung-tod)
- [5-Step Pipeline Overview](#5-step-pipeline-overview)
- [Quick Start](#quick-start)
- [Step 1: POI Time Classification](#step-1-poi-time-classification)
- [Step 2: Dasymetric Population Allocation](#step-2-dasymetric-population-allocation)
- [Step 3: Indicator Grid Construction](#step-3-indicator-grid-construction)
- [Step 4: GWR Model Fitting](#step-4-gwr-model-fitting)
- [Step 5: Future Scenario Prediction](#step-5-future-scenario-prediction)
- [Step 5b: Pedestrian Network Flow Assignment](#step-5b-pedestrian-network-flow-assignment)
- [Result Interpretation](#result-interpretation)
- [Built-in Classification Dictionaries](#built-in-classification-dictionaries)
- [Full Config Reference](#full-config-reference)
- [Troubleshooting](#troubleshooting)
- [Validation Results](#validation-results)
- [Files](#files)

---

## Core Methodology

```
Population Change (independent variable)
       +
Infrastructure / Transit (co-variates)
       ↓
  GWR Spatial Regression
       ↓
Future Facility Distribution (predicted)
```

**Why GWR?** Facility demand relationships vary spatially. Near metro stations, population density may strongly predict POI count; in rural areas, road access may matter more. Global models like OLS assume a single, stationary relationship — GWR captures this spatial heterogeneity by fitting separate regression models at every location, weighted by nearby observations.

### The Regression Model

```
poi_count_i = β₀(uᵢ, vᵢ) + β₁(uᵢ, vᵢ)·pop_density_i + β₂(uᵢ, vᵢ)·road_density_i + ε_i
```

Each location `(uᵢ, vᵢ)` gets its own set of coefficients β, estimated from nearby observations weighted by a bisquare kernel.

---

## Case Study: Tung Chung TOD

This pipeline was developed and validated for the **Tung Chung Tat Tung Road Bus Terminus** site — a 4.61 ha TOD project in Hong Kong's Tung Chung New Town Extension.

| Parameter | Value |
|-----------|-------|
| Site area | 4.61 ha |
| Site centroid | E811711, N816894 (EPSG:2326) |
| GFA estimate | 82,947 m² (60% coverage × 3 floors) |
| Land-use program | Sports Centre |
| Projected footfall | 3,733 peak-hour trips |
| Catchment population (600m) | 100,531 |
| Buildings within range | 598 |
| Study grid | 50m × 50m cells, 1,500m buffer |
| Road segments in study area | 2,408 |
| Future scenario | TCNTE 2033: population 116k → 320k, +877,000 m² GFA |

### Data Inputs

| Dataset | Source | Key Fields |
|---------|--------|------------|
| `Designsite.shp` | Design boundary | Site polygon |
| `HK_population.gpkg` | Census (SSBG level) | `Averag_pop` |
| `Site_buildings.gpkg` | HK Lands Dept | `Elevation` (building height) |
| `HK_roads.gpkg` | OSM / gov data | `Shape_Leng`, `time_walk`, `rest_walk` |
| 4 POI shapefiles | Amap 2025 | `midType` (sub-category in Chinese) |
| `LandUse_Vector_Polygons.gpkg` | LUCC classification | `type_code` |
| `Result_Stations_InROI.shp` | Transit analysis | Bus stop locations |
| `tcnte_east_bbox.gpkg` / `tcnte_west_bbox.gpkg` | Gov planning | TCNTE development zones |

---

## 5-Step Pipeline Overview

| Step | Name | What It Does | Input | Output | Core Tool |
|------|------|-------------|-------|--------|-----------|
| 1 | **POI Classification** | Classify facilities by time-of-day operation | 4 raw POI shapefiles by category | `poi_all_time_classified` with `time_class` field | `CalculateField` |
| 2 | **Dasymetric Population** | Allocate census population to individual buildings by height | Census blocks + building footprints | Buildings with `bldg_pop` field | `Intersect` |
| 3 | **Indicator Grid** | Build 50m fishnet + join 3-6 indicators per cell | Site, POIs, population, roads, LUCC, transit | `grid_indicators_full`, `grid_active_cells` | `CreateFishnet` + `SpatialJoin` |
| 4 | **GWR Fit** | Fit spatially-varying regression on active cells | `grid_active_cells` | GWR coefficients, local R², residuals, AICc | `arcpy.stats.GWR` |
| 5 | **Future Prediction** | Apply GWR to TCNTE 2033 scenario grid | GWR model + `prediction_fc` | `gwr_prediction_future` | `arcpy.stats.GWR` |
| 5b | *(Supplementary)* **Network Flow** | Assign pedestrian trips to network, compute LOS + gaps | Road network + pop origins + corporate POIs | `link_loads_200m`, `gap_zones` | `networkx` |

---

## Quick Start

### Prerequisites

- **ArcGIS Pro 3.x** installed (provides `arcpy`)
- Python libraries: `numpy`, `scipy`, `networkx`, `shapely`

```bash
# Install dependencies into your arcgispro-py3 environment
pip install -r requirements.txt
```

### Verify your environment

```bash
# Check arcpy is available
python -c "import arcpy; print(arcpy.GetInstallInfo()['Version'])"

# Check installed packages
python -c "import numpy, scipy, networkx, shapely; print('All OK')"
```

### 1. Prepare your data

Each step has specific input requirements. At minimum you need:

| Layer | Geometry | Required Fields | Notes |
|-------|----------|-----------------|-------|
| **Site boundary** | Polygon | — | Your design site |
| **POIs** | Point | `midType` or equivalent category field | Can be split into multiple files by category |
| **Population** | Polygon | Population count (e.g. `Averag_pop`) | Census SSBG or street-block level |
| **Buildings** | Polygon | Building elevation/height (e.g. `Elevation`) | Footprint polygons |
| **Roads** | Line | Length + optional travel time | Must intersect study area |

### 2. Create a config file

Copy `config_template.json` and fill in your data paths:

```json
{
  "output_gdb": "D:/MyProject/output.gdb",
  "crs": "EPSG:2326",
  "steps": ["grid", "gwr_fit", "gwr_predict"],

  "field_mapping": {
    "population_count": "Averag_pop",
    "building_elevation": "Elevation",
    "poi_midtype": "midType",
    "road_length": "Shape_Leng",
    "census_block_id": "ssbg"
  },

  "grid": {
    "site_fc": "D:/data/my_site.shp",
    "poi_fc": "D:/data/my_poi.gpkg",
    "pop_fc": "D:/data/my_population.gpkg",
    "roads_fc": "D:/data/my_roads.gpkg",
    "cell_size": 50,
    "study_buffer": 1500
  },

  "gwr": {
    "dependent": "poi_count",
    "explanatory": ["pop_density", "road_density"]
  },

  "prediction": {
    "prediction_fc": "D:/data/future_grid.gpkg",
    "explanatory": ["pop_density", "road_density"]
  }
}
```

> **Field Mapping**: Use `field_mapping` to declare your dataset's actual column names. Scripts use these exact names first, then fall back to keyword-based auto-detection, then fail with a clear error message listing available fields. This avoids silent failures when column names differ from defaults.

### 3. Run

```bash
# Full pipeline (all 6 steps including classification, dasymetric, and network)
python scripts/master_pipeline.py my_config.json

# Specific steps only
python scripts/master_pipeline.py my_config.json --steps 3,4,5

# Standalone: run a single step with CLI arguments
python scripts/step4_gwr_model.py --grid-active D:/output/grid_active_cells \
    --dependent poi_count --explanatory pop_density road_density \
    --output-gdb D:/output/output.gdb
```

### 4. View results

All outputs land in the File Geodatabase. Open in ArcGIS Pro or QGIS:

| Layer | Contents |
|-------|----------|
| `grid_indicators_full` | All grid cells with poi_count, pop_density, road_density |
| `grid_active_cells` | Subset with POI > 0 (training data for GWR) |
| `gwr_results` | Local R², coefficients, residuals, StdResidual, AICc |
| `gwr_prediction_future` | Predicted facility counts for future scenario |
| `poi_all_time_classified` | Merged classified POIs with `time_class` field |
| `site_buildings` | Buildings with `bldg_pop` field (elevation-weighted) |
| `link_loads_200m` | Loaded pedestrian edges within 200m of site, with LOS |
| `gap_zones` | Straight-line connections showing connectivity gaps |

---

## Step 1: POI Time Classification

Classifies facilities into **daytime** / **nighttime** / **all-day** operation based on their sub-category (`midType`) field.

**Script**: `scripts/step1_classify_poi.py`

### Why This Matters

Daytime-oriented facilities (offices, banks, schools) cluster around existing CBDs — Tung Chung's Citygate outlet dominates daytime activity. Nighttime facilities (F&B, leisure) are systematically underrepresented near transit hubs. This classification reveals the **evening economy gap** that TOD should fill.

In the Tung Chung case, the existing POI mix within 600m of the bus terminus showed:
- 72% of POIs classified as "both" (all-day retail, healthcare)
- 18% daytime (offices, banks, education)
- 10% nighttime (evening F&B, leisure)

The design recommendation: prioritise community sports and evening leisure programming to balance the area's existing daytime commercial bias.

### Input Schema

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `midType` (or configured name) | String | Yes | POI sub-type in Chinese (e.g. `公司`, `中餐厅`, `休闲餐饮场所`) |
| `geometry` | Point | Yes | POI location |

### Output Schema

| Field | Type | Description |
|-------|------|-------------|
| `time_class` | TEXT(20) | `daytime` / `nighttime` / `both` |
| `time_label` | TEXT(60) | Human-readable: `1-Daytime (8am-6pm)`, etc. |
| `category` | TEXT(20) | Original POI category (e.g. `commercial`, `community`) |

### Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `midtype_field` | `midType` | Field containing POI sub-type category |
| `day_set` | Built-in list | Chinese midType values for daytime classification |
| `night_set` | Built-in list | Chinese midType values for nighttime classification |
| `both_set` | Built-in list | Chinese midType values for all-day classification |

### Usage

```bash
# Via master pipeline
python scripts/master_pipeline.py config.json --steps classify

# Standalone
python scripts/step1_classify_poi.py \
    --poi-dir D:/data/poi_categories/ \
    --output-gdb D:/output/study.gdb
```

The classification dictionaries are configurable — see [Built-in Classification Dictionaries](#built-in-classification-dictionaries) for the default Hong Kong-context values.

### Pitfalls

1. **midType field not found**: If your POI data uses a different field name (e.g. `subType`, `category`), set `field_mapping.poi_midtype` in config. The script will list all available fields on failure.
2. **Empty classification**: If all POIs fall into "both", your `day_set`/`night_set` might not match actual midType values. Run a quick check: `ogrinfo poi.gpkg -al -limit 20 | grep midType` to verify.

---

## Step 2: Dasymetric Population Allocation

Distributes census population from areal units (SSBGs) to individual building footprints, weighted by building elevation — a proxy for gross floor area (GFA).

**Script**: `scripts/step2_pop_allocate.py`

### Why This Matters

Census data is areal — a single SSBG polygon may cover 50+ buildings. Buildings are the actual dwelling units. Elevation-weighting ensures high-rise residential towers receive proportionally more population than low-rise structures, producing a more realistic distribution.

### Formula

```
pop_building = census_pop × (footprint_area × elevation)
               ─────────────────────────────────────────
               Σ(footprint_area × elevation) per census block
```

### Input Schema

| Layer | Required Fields | Notes |
|-------|-----------------|-------|
| Population polygons | Population count (e.g. `Averag_pop`) | Census SSBG level |
| Building footprints | Building elevation (e.g. `Elevation`) in metres | Height above ground |

### Output Schema

| Field | Type | Description |
|-------|------|-------------|
| `Area_m2` | DOUBLE | Building footprint area |
| `Elev_m` | DOUBLE | Building elevation (with fallback for nulls) |
| `Volume` | DOUBLE | Area × Elev (proxy for GFA) |
| `bldg_pop` | DOUBLE | Allocated population |
| `est_floors` | DOUBLE | Estimated floor count (Elev / 3.0) |

### Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `pop_field` | `Averag_pop` | Population count field in census data |
| `elev_field` | `Elevation` | Building height field |
| `fallback_height` | 3.0 | Height (m) for buildings with missing/zero elevation data |

### Pitfalls

1. **SSBG identifier field not found**: The script auto-detects census block ID fields by searching for `ssbg` in field names. If your data uses a different naming convention (e.g. `zone_id`, `block_code`), update `field_mapping.census_block_id`.
2. **All buildings get equal population**: If the elevation field is missing for all buildings, every building gets an equal share of block population. Verify with `gdalinfo` that your building layer actually contains the height column.

---

## Step 3: Indicator Grid Construction

Creates a regular fishnet grid (default 50m × 50m) covering the study area, then spatial-joins built-environment indicators to each cell.

**Script**: `scripts/step3_build_grid.py`

### Why 50m Cells?

50m resolution provides fine-grained spatial detail for facility-level prediction while keeping computation tractable. At 1,500m buffer, approximately 3,600 grid cells are generated — enough for GWR's local regressions without excessive runtime.

### Indicators Computed

| Indicator | Computation | Unit |
|-----------|-------------|------|
| **poi_count** | Number of facilities intersecting cell | count |
| **pop_density** | Census population / cell area | persons/hectare |
| **road_density** | Total road length / cell area | m/m² |

The pipeline supports additional indicators (LUCC type, transit proximity) by extending the field list.

### Input Schema

| Layer | Geometry | Required Fields |
|-------|----------|-----------------|
| `site_fc` | Polygon | — |
| `poi_fc` | Point | — |
| `pop_fc` | Polygon | Population count |
| `roads_fc` | Line | Length field |

### Output Schema

| Field | Type | Description |
|-------|------|-------------|
| `poi_count` | LONG | Facility count per cell |
| `pop_density` | DOUBLE | Population density (ppl/ha) |
| `road_density` | DOUBLE | Road density (m/m²) |
| `cell_area` | DOUBLE | Cell area (m²) |

### Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `cell_size` | 50 | Grid cell size in metres |
| `study_buffer` | 1500 | Distance (m) around site defining study extent |
| `pop_field` | `Averag_pop` | Population count field |
| `road_length_field` | `Shape_Leng` | Road segment length field |

### Pitfalls

1. **Grid cells over water**: Fishnet covers the rectangular extent, including sea. Purely marine cells will have 0 POIs and will be filtered out when creating `grid_active_cells` (POI > 0). No problem for training, but prediction grids should also follow land mask.
2. **Spatial join double-counting**: POIs on cell boundaries may be counted twice if using `INTERSECT` without `LARGEST_OVERLAP`. This is rare with fine grids and has negligible impact on GWR results.

---

## Step 4: GWR Model Fitting

Fits a Geographically Weighted Regression model using `arcpy.stats.GWR`.

**Script**: `scripts/step4_gwr_model.py`

### The Model

```
poi_count_i = β₀(uᵢ, vᵢ) + β₁(uᵢ, vᵢ)·pop_density_i + β₂(uᵢ, vᵢ)·road_density_i + ε_i
```

### Why GWR over OLS?

An OLS model would ask: "What is THE relationship between population density and POI count across the entire study area?" But the answer differs by location — near the metro station, population density is the dominant predictor; in peripheral areas, road access is what matters. GWR estimates **local coefficients** at every grid cell.

### Input Schema

| Layer | Required Fields |
|-------|-----------------|
| `grid_active_cells` | `dependent_var` + all `explanatory_vars` |

All fields must be numeric. Nulls are replaced with 0 before fitting.

### Output Schema

| Field | Description |
|-------|-------------|
| `R2` | Local R² — model fit at each location |
| `Residual` | Observed − Predicted |
| `StdResidual` | Standardised residual (> |2.5| = outlier) |
| `AICc` | Corrected Akaike Information Criterion |
| `Condition Number` | Local multicollinearity indicator |
| `C1_<varname>` | Local coefficient for each explanatory variable |
| `C0_Intercept` | Local intercept |

### Parameters

| Parameter | Default | Options | Guidance |
|-----------|---------|---------|----------|
| `dependent` | `poi_count` | Any numeric field | Must have variation (variance > 0) |
| `explanatory` | `[pop_density, road_density]` | List of numeric field names | 2-5 variables recommended; avoid highly correlated pairs |
| `neighborhood_type` | `NUMBER_OF_NEIGHBORS` | `DISTANCE_BAND` | Use adaptive (Number of Neighbors) when point density varies across study area |
| `selection_method` | `GOLDEN_SEARCH` | `MANUAL_INTERVALS`, `USER_DEFINED` | Golden Search auto-optimizes; use Manual for diagnostics; use User-Defined for production with known bandwidth |
| `min_neighbors` | 30 | Any integer ≥ 10 | More = smoother coefficients but less local detail. For 50m grid, 30-100 is sensible |
| `scale_data` | `true` | `true` / `false` | Always scale; un-scaled coefficients are hard to compare across variables |

**When to use each neighborhood type:**

| Scenario | Use |
|----------|-----|
| Grid cells are evenly spaced (fishnet) | `DISTANCE_BAND` |
| Point density varies (some areas sparse, others dense) | `NUMBER_OF_NEIGHBORS` |
| Unknown — let the tool decide | `NUMBER_OF_NEIGHBORS` + `GOLDEN_SEARCH` |

### Diagnostics

| Diagnostic | Good | Bad |
|-----------|------|-----|
| **Local R²** | > 0.4 at most locations | < 0.1 globally — model explains little |
| **StdResidual** | |z| < 2.5 for 95%+ of cells | Clusters of > |2.5| → missing variable or spatial process |
| **AICc** | Lower relative to alternative models | Higher than OLS → GWR not helping |
| **Condition Number** | < 30 | > 30 → local multicollinearity. Increase `min_neighbors` or drop a correlated variable |

### Pitfalls

1. **All-zero explanatory variable**: If `pop_density` is 0 for most cells (e.g. study area covers only water/unpopulated land), GWR will fail with `110222`. Filter your grid: only cells with POI > 0 AND population > 0.
2. **GOLDEN_SEARCH stalls**: With very large datasets (>10,000 cells), Golden Search can be slow. Use `MANUAL_INTERVALS` for large grids, or crop to a tighter study buffer.

---

## Step 5: Future Scenario Prediction

Applies the fitted GWR model to a **future scenario grid** where population and infrastructure have been projected.

**Script**: `scripts/step4_gwr_model.py` (prediction mode: `predict_future()`)

### How Future Scenarios Work

The prediction grid must have the **same field names** as the training data's explanatory variables. You apply growth factors to these fields before prediction.

### Tung Chung 2033 Example

| Variable | Current (2025) | Future (2033) | Growth Factor | Source |
|----------|---------------|---------------|---------------|--------|
| Population | 100,531 (600m catchment) | ~320,000 | ×3.18 | TCNTE gov projections |
| Population on-site | 0 | 12,000-22,000 | — | TCNTE East development |
| Road density | Existing network | +40% (new internal roads) | ×1.4 on TCNTE cells | Infrastructure plan |
| GFA | Existing Citygate | +877,000 m² | — | TCNTE zoning |

### Input Schema

| Layer | Required Fields |
|-------|-----------------|
| `prediction_fc` | All `explanatory_vars` matching training field names |

### Output Schema

| Field | Description |
|-------|-------------|
| `predicted` | GWR-predicted value for each cell |
| (all explanatory fields) | Preserved from input prediction grid |

### Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `prediction_fc` | — | Path to future scenario grid |
| `explanatory` | — | Must match training `explanatory_vars` list |

### Growth Factor Guidelines (Hong Kong)

| Land-Use Context | Population Factor | Road Factor | Transit Factor |
|-----------------|-------------------|-------------|----------------|
| On-site (TCNTE East) | ×3-5 (from ~0 to estate levels) | +40% (new internal roads) | ×1.0 (same transit) |
| Adjacent (within 500m) | ×1.2 (infill) | ×1.1 (minor upgrades) | ×1.0 |
| Peripheral (>500m) | ×1.0 (existing) | ×1.0 | ×1.0 |

### Pitfalls

1. **Field name mismatch**: The most common error. The prediction grid must have fields with the **exact same names** as the training explanatory variables. Use the field list from `gwr.explanatory` in your config.
2. **Null values in prediction grid**: Nulls are coerced to 0, which may produce misleading predictions for cells that should have positive values. Fill all explanatory fields before running.

---

## Step 5b: Pedestrian Network Flow Assignment

Supplementary analysis modeling how people move through the pedestrian network to reach the site. Complements grid-level GWR by providing the **human-scale lens** — which specific paths, crossings, and entry points experience highest flow.

**Script**: `scripts/step5_net_assign.py`

**Dependencies**: `networkx`, `scipy`, `shapely`

### Methodology

```
Road network → graph (nodes = intersections, edges = walkways)
     ↓
Population origins → snapped to nearest graph nodes
     ↓
Shortest-path routing (Dijkstra, weight = travel_time)
     ↓
Flow accumulation on each edge:
  - Population → site: trips = pop × trip_share × peak_trips
  - Corporate POI → site: constant 2 trips/POI (employee/visitor baseline)
     ↓
LOS classification (HCM pedestrian, per metre walkway width)
     ↓
Gap detection: detour ratio = network_distance / straight_line > threshold
```

### Input Schema

| Layer | Geometry | Required Fields | Notes |
|-------|----------|-----------------|-------|
| `site_fc` | Polygon | — | Destination |
| `roads_fc` | Line | Length + travel time | `time_walk` preferred; fallback: length / 1.25 m/s |
| `pop_fc` | Polygon | Population count, SSBG ID | Census blocks intersecting study buffer |

### Output Schema

**`link_loads_200m`** — loaded edges within 200m of site:

| Field | Type | Description |
|-------|------|-------------|
| `load` | DOUBLE | Total pedestrian trips on this edge |
| `length_m` | DOUBLE | Edge length (m) |
| `tt_sec` | DOUBLE | Travel time (s) |
| `flow_pmpm` | DOUBLE | Flow per metre width per minute |
| `LOS` | TEXT(4) | Level of Service (B-E) |
| `load_norm` | DOUBLE | Normalized load (0-100%) |

**`gap_zones`** — straight-line connections showing detour problems:

| Field | Type | Description |
|-------|------|-------------|
| `ssbg_eng` | TEXT | Census block name (English) |
| `pop` | LONG | Block population |
| `trips_ph` | DOUBLE | Estimated trips/hour from this block |
| `straight` | DOUBLE | Straight-line distance (m) |
| `network_m` | DOUBLE | Network path distance (m) |
| `detour_x` | DOUBLE | Detour ratio (>1.4 = gap) |
| `priority` | TEXT | `HIGH` (trips > 3/hr), `MEDIUM`, `CRITICAL` (no path) |

### LOS Thresholds (HCM Pedestrian, 3m Walkway)

| LOS | Flow (ped/m/min) | Condition |
|-----|------------------|-----------|
| **A** | — | (not classified — negligible) |
| **B** | < 0.38 | Free flow |
| **C** | 0.38 – 0.55 | Slightly restricted |
| **D** | 0.55 – 0.82 | Noticeable restriction — intervention recommended |
| **E** | ≥ 0.82 | At capacity — redesign required |

### Trip Generation Rates (TPDM)

| Program Type | Rate (trips/100m² GFA/hr) |
|-------------|---------------------------|
| Sports Centre | 4.5 |
| Library | 3.2 |
| Town Hall | 6.0 |
| Training Centre | 5.5 |
| Student Hostel | 2.8 |
| Research Centre | 4.0 |

### Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `pop_field` | `Averag_pop` | Population count field |
| `program_type` | `Sports Centre` | Land-use program (drives trip generation rate) |
| `walkway_width` | 3.0 | Effective walkway width in metres |
| `clip_buffer` | 600 | Road network buffer around site (m) |
| `gap_threshold` | 1.4 | Detour ratio above which a gap is flagged |

### Pitfalls

1. **Disconnected graph**: If the building and site belong to different connected components, routing fails → "CRITICAL" gap. This is correct behaviour — it flags a genuine connectivity problem. The Tung Chung case had exactly 1 such gap (SSBG 950/01-02, no footbridge across the main road).
2. **Restricted access edges**: If your road data has a `rest_walk` flag, segments with walking restrictions will be penalised (travel time ×10) to route pedestrians away from them. Without this, the model may send pedestrians along roads not actually walkable.

### Tung Chung Results

From the case study validation run:

```
Peak-hr trips: 3,733 (Sports Centre, 82,947 m² GFA)
Catchment: 100,531 population, 5 SSBGs within 600m
Loaded edges (within 200m): 182
LOS E (redesign needed): 50 segments
Gap zones: 1 CRITICAL (no path across highway), 1 HIGH (1.69× detour)
Top detour: 950/36 — 857 trips/hr, 832m straight → 1,410m network (elongated block)
```

**Design implications**: Widen north-south approach paths, add a grade-separated pedestrian link to SSBG 950/01-02, and provide direct connections through elongated residential blocks.

---

## Result Interpretation

### Reading GWR Coefficient Maps

After running Step 4, open `gwr_results` in GIS:

1. **Local R²** → Identify where the model explains facility distribution well (R² > 0.4) vs. poorly (R² < 0.1). Low R² areas suggest missing explanatory variables — consider adding transit proximity or LUCC type.
2. **Pop_density coefficient (β₁)** → Positive values indicate population density drives POI count (expected near transit). Near-zero or negative values indicate other factors dominate (e.g. land-use zoning, road access).
3. **StdResidual clusters** → Hotspots of > |2.5| suggest spatial processes not captured by the model — possibly agglomeration effects, zoning constraints, or historical path-dependency.

### Reading Flow Assignment Maps

1. **LOS distribution** → The ratio of LOS E to total loaded edges tells you whether the pedestrian network is adequate. >10% LOS E = significant redesign needed.
2. **Gap priority** → Address CRITICAL gaps (no path) first — these represent total disconnect. Then HIGH gaps (detour >1.4×) — these indicate unnecessarily elongated routes.
3. **Flow concentration** → If >50% of flow is on <10% of edges, those edges are pinch-points. Consider parallel routes or wider footpaths.

### QGIS Symbology Reference

| Layer | Symbology | Colour Scheme |
|-------|-----------|---------------|
| `link_loads_200m` | Width by `load_norm`, colour by `LOS` | B=#1D9E75, C=#EF9F27, D=#D85A30, E=#E24B4A |
| `gap_zones` | Dashed red, width by `trips_ph` | CRITICAL=#E24B4A, HIGH=#EF9F27, MEDIUM=#1D9E75 |
| `gwr_results` | Graduated by `R2` | YlOrRd |
| `grid_prediction_future` | Graduated by `predicted` | Blues |

---

## Built-in Classification Dictionaries

### Daytime (offices, education, administration) — Time Class 1

`公司` `知名企业` `公司企业` `银行` `金融保险服务机构` `银行相关` `中介机构` `邮局` `物流速递` `家居建材市场` `花鸟鱼虫市场` `维修站点` `摄影冲印店` `学校` `培训机构` `科研机构` `传媒机构` `文艺团体` `会展中心` `住宅区`

### Nighttime (evening F&B, leisure, nightlife) — Time Class 2

`休闲餐饮场所` `茶艺馆` `冷饮店` `休闲场所`

### All-Day (retail, healthcare, sports, hotels, civic) — Time Class 3

`中餐厅` `外国餐厅` `快餐厅` `咖啡厅` `糕饼店` `甜品店` `餐饮相关场所` `便民商店/便利店` `超级市场` `商场` `专卖店` `服装鞋帽皮具店` `体育用品店` `家电电子卖场` `个人用品/化妆品店` `文化用品店` `购物相关场所` `宾馆酒店` `旅馆招待所` `美容美发店` `洗衣店` `自动提款机` `电讯营业厅` `旅行社` `生活服务场所` `诊所` `综合医院` `专科医院` `急救中心` `医药保健销售店` `医疗保健服务场所` `图书馆` `博物馆` `美术馆` `展览馆` `科教文化场所` `科技馆` `天文馆` `文化宫` `运动场馆` `体育休闲服务场所` `高尔夫相关`

These dictionaries are overridable via `poi_classification.{day_set, night_set, both_set}` in your config.

---

## Full Config Reference

```yaml
# ── Global ──
output_gdb: "D:/MyProject/output.gdb"
output_gpkg: "D:/MyProject/output.gpkg"       # optional dual-format export
crs: "EPSG:2326"
steps: [classify, dasymetric, grid, gwr_fit, gwr_predict, network]

# ── Field Mapping ──
field_mapping:
  population_count: "Averag_pop"
  building_elevation: "Elevation"
  poi_midtype: "midType"
  road_length: "Shape_Leng"
  road_travel_time: "time_walk"
  census_block_id: "ssbg"
  census_block_name: "ssbg_eng"

# ── POI Classification (Step 1, optional) ──
poi_classification:
  poi_layers:
    commercial: "D:/data/poi_commercial.gpkg"
    community:  "D:/data/poi_community.gpkg"
    sports_rec: "D:/data/poi_sports_rec.gpkg"
  midtype_field: "midType"
  day_set: ["公司","银行","学校"]
  night_set: ["休闲餐饮场所","茶艺馆"]
  both_set: ["中餐厅","咖啡馆","诊所"]

# ── Dasymetric Population (Step 2, optional) ──
dasymetric:
  pop_fc: "D:/data/HK_population.gpkg"
  bldg_fc: "D:/data/Site_buildings.gpkg"
  pop_field: null                        # null → use field_mapping
  elev_field: null                       # null → use field_mapping
  fallback_height: 3.0

# ── Grid (Step 3) ──
grid:
  site_fc: "D:/data/Designsite.shp"
  poi_fc: null                           # null → use Step 1 result
  pop_fc: "D:/data/HK_population.gpkg"
  roads_fc: "D:/data/HK_roads.gpkg"
  cell_size: 50
  study_buffer: 1500
  pop_field: null
  road_length_field: null

# ── GWR Model (Step 4) ──
gwr:
  dependent: "poi_count"
  explanatory: [pop_density, road_density]
  neighborhood_type: "NUMBER_OF_NEIGHBORS"
  selection_method: "GOLDEN_SEARCH"
  min_neighbors: 30
  num_neighbors: null                    # only for USER_DEFINED
  scale_data: true
  output_name: "gwr_results"

# ── Prediction (Step 5) ──
prediction:
  prediction_fc: "D:/data/grid_future_2033.gpkg"
  dependent: "poi_count"
  explanatory: [pop_density, road_density]   # must match gwr.explanatory
  output_name: "gwr_prediction_future"

# ── Network Flow (Step 5b, optional) ──
network:
  site_fc: "D:/data/Designsite.shp"
  roads_fc: "D:/data/HK_roads.gpkg"
  pop_fc: "D:/data/HK_population.gpkg"
  pop_field: null
  road_length_field: null
  road_travel_time_field: null
  program_type: "Sports Centre"
  walkway_width: 3.0
  clip_buffer: 600
  gap_threshold: 1.4
```

---

## Troubleshooting

| Error | Likely Cause | Fix |
|-------|-------------|-----|
| `ERROR 110222: multicollinearity` | Explanatory variables too correlated; too few neighbors | Enable `scale_data`; increase `min_neighbors` to 100; remove correlated variables |
| `ERROR 000732: dataset not supported` | GPKG not directly supported by arcpy | Convert to shapefile/GDB first via `ogr2ogr` or geopandas |
| Field not found: `<name>` | Column names don't match defaults | Set explicit names in `field_mapping` section of config. The error message lists all available fields |
| Prediction fails with field mismatch | Prediction grid has different field names from training | Rename prediction grid fields to exactly match `gwr.explanatory` list |
| `WARNING 110259: very limited variation` | Sparse data in some neighborhoods (e.g. water cells, all-zero zones) | Increase `min_neighbors`; verify active cells have non-zero values for all explanatory variables |
| GOLDEN_SEARCH very slow (>10 min) | Too many cells in training data | Reduce `study_buffer` or increase `cell_size` to 100m |
| `ImportError: No module named 'arcpy'` | Not running in ArcGIS Pro Python environment | Use the correct Python executable (ArcGIS Pro install dir) |
| Network assignment: "No path" for all blocks | Road graph is fragmented | Increase `SNAP_TOLERANCE` (default 2.0m); check for disconnected road segments in QGIS |
| LOS E on all edges | Trip rate or walkway_width unrealistic | Verify GFA calculation; check `walkway_width` matches actual path widths (3.0m = standard footpath) |

---

## Validation Results

The pipeline was validated against the original Python-based analysis (`Analysis_try6` notebooks, Tung Chung Bus Terminus):

| Analysis | Key Metric | Original (geopandas/mgwr) | This Pipeline (arcpy) | Match |
|----------|-----------|--------------------------|----------------------|-------|
| POI Classification | Total POIs | 1,184 | 1,184 | 100% |
| Dasymetric Population | Buildings processed | 598 | 598 | 100% |
| GWR Model | Local R² (mean) | 0.18 | 0.20 | Comparable |
| Network Assignment | Loaded edges (200m) | 182 | Matches | ✓ |
| Network Assignment | Critical gaps | 1 | 1 | 100% |
| Network Assignment | LOS E segments | 50 | Reproduced | ✓ |

Minor differences in GWR metrics are attributable to `arcpy.stats.GWR` using a bisquare kernel vs. `mgwr` library's adaptive bandwidth — both produce spatially consistent coefficient maps.

---

## Files

```
gwr-pipeline/
├── README.md
├── requirements.txt              # numpy, scipy, networkx, shapely
├── config_template.json          # Copy and customize for your project
├── .gitignore
└── scripts/
    ├── _utils.py                 # Shared field resolution utility
    ├── master_pipeline.py        # Orchestrator — run this
    ├── step1_classify_poi.py     # POI time-of-day classification
    ├── step2_pop_allocate.py     # Dasymetric population to buildings
    ├── step3_build_grid.py       # Fishnet grid + indicator spatial join
    ├── step4_gwr_model.py        # GWR fit + future scenario prediction
    └── step5_net_assign.py       # Pedestrian network flow assignment
```

## License

MIT
