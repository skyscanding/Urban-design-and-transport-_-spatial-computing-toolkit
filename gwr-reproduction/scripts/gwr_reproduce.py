"""
GWR Reproduction Pipeline — Tung Chung TOD facility-demand prediction
=====================================================================
Open-source (geopandas + mgwr) reproduction of the original studio pipeline
(GWR_Prediction_v3). Faithfully replicates the analytically load-bearing
choices that the arcpy toolkit did NOT reproduce:

  * 100 m grid, 1500 m study buffer, land-masked (airport polygon excluded)
  * THREE independent category models: commercial / community / sports_rec
  * FIVE explanatory variables:
        pop_density, road_density, lucc_urban_pct, bus_density, transit_access
  * mgwr adaptive bisquare GWR, with an OLS fallback on singular matrix
    or on too-few active cells (the commercial model historically fell back)
  * TCNTE 2033 future scenario applied by ZONE growth factors, then
    on-site predicted change reported per category.

Everything is driven by a JSON config. Run:

    python gwr_reproduce.py config_tung_chung.json
    python gwr_reproduce.py config_tung_chung.json --stages 1-5   # partial

Author's note: variable *definitions* for transit_access and bus_density are
documented in the README and configurable; the modelling structure, factors
and fallback logic mirror the original run.
"""
from __future__ import annotations
import argparse, json, sys, time, warnings
from pathlib import Path

import numpy as np
import pandas as pd
import geopandas as gpd
from shapely.geometry import box
from scipy.spatial import cKDTree

warnings.filterwarnings("ignore")

# ----------------------------------------------------------------------------- 
# mgwr is optional at import time so the OLS path still works without it
try:
    from mgwr.gwr import GWR
    from mgwr.sel_bw import Sel_BW
    HAVE_MGWR = True
except Exception:                                            # pragma: no cover
    HAVE_MGWR = False

CRS_PROJ = "EPSG:2326"            # Hong Kong 1980 Grid
CATEGORIES = ["commercial", "community", "sports_rec"]
X_COLS = ["pop_density", "road_density", "lucc_urban_pct",
          "bus_density", "transit_access"]

_T0 = time.time()
def log(msg=""):
    print(f"  [{time.time()-_T0:6.0f}s] {msg}", flush=True)
def banner(msg):
    print("\n" + "=" * 70 + f"\n{msg}\n" + "=" * 70, flush=True)


# =============================================================================
# helpers
# =============================================================================
def read_layer(path, want_crs=CRS_PROJ):
    """Read any vector layer, force projected CRS."""
    gdf = gpd.read_file(path)
    if gdf.crs is None:
        gdf = gdf.set_crs("EPSG:4326")
    if gdf.crs.to_epsg() != int(want_crs.split(":")[1]):
        gdf = gdf.to_crs(want_crs)
    return gdf


def first_field(gdf, candidates):
    """Return the first column present from a candidate list (case-insensitive)."""
    lut = {c.lower(): c for c in gdf.columns}
    for cand in candidates:
        if cand.lower() in lut:
            return lut[cand.lower()]
    return None


def classify_poi(gdf, midtype_field, rules):
    """
    Apply category rules to a POI layer.
    `rules` is {category: {"include": [...], "exclude": [...]}}, matched against
    the midType (sub-category) string by substring.
    Returns a copy with a 'category' column (or None where unmatched).
    """
    s = gdf[midtype_field].fillna("").astype(str)
    cat = pd.Series([None] * len(gdf), index=gdf.index, dtype=object)
    for c in CATEGORIES:
        rule = rules.get(c, {})
        inc = rule.get("include", [])
        exc = rule.get("exclude", [])
        if not inc:
            continue
        hit = s.apply(lambda v: any(k in v for k in inc))
        if exc:
            hit &= ~s.apply(lambda v: any(k in v for k in exc))
        cat = cat.where(cat.notna() | ~hit, c)        # don't overwrite an earlier hit
    out = gdf.copy()
    out["category"] = cat
    return out[out["category"].notna()].copy()


# =============================================================================
# STAGE 1 — site, study area, land mask (airport excluded)
# =============================================================================
def stage_land(cfg):
    banner("STAGE 1: SITE + STUDY AREA + LAND MASK")
    g = cfg["data"]
    site = read_layer(g["site_fc"])
    site_geom = site.union_all()
    buf = cfg["params"]["study_buffer"]
    study = site_geom.buffer(buf)
    log(f"Site loaded; study buffer = {buf} m")

    land = study
    if g.get("land_fc"):
        land_gdf = read_layer(g["land_fc"])
        land = study.intersection(land_gdf.union_all())
        log("Land mask intersected")
    if g.get("airport_fc"):
        air = read_layer(g["airport_fc"]).union_all()
        land = land.difference(air)
        log("Airport polygon excluded from land mask")

    study_gdf = gpd.GeoDataFrame(geometry=[study], crs=CRS_PROJ)
    land_gdf = gpd.GeoDataFrame(geometry=[land], crs=CRS_PROJ)
    return site, site_geom, study_gdf, land_gdf


# =============================================================================
# STAGE 2 — reclassify POIs into 3 categories
# =============================================================================
def stage_poi(cfg, study_gdf):
    banner("STAGE 2: RECLASSIFY POIs -> 3 CATEGORIES")
    rules = cfg["poi_rules"]
    mt = cfg["field_mapping"].get("poi_midtype", "midType")
    frames = []
    for src in cfg["data"]["poi_sources"]:
        p = Path(src)
        if not p.exists():
            log(f"SKIP (missing): {p.name}")
            continue
        gdf = read_layer(p)
        f = first_field(gdf, [mt, "midType", "type", "fclass"])
        if f is None:
            log(f"SKIP (no midType): {p.name}")
            continue
        clipped = gpd.clip(gdf, study_gdf)
        cl = classify_poi(clipped, f, rules)
        frames.append(cl[["category", "geometry"]])
        log(f"{p.name}: {len(cl)} classified")
    if not frames:
        raise SystemExit("No POIs classified — check poi_sources / rules.")
    poi = gpd.GeoDataFrame(pd.concat(frames, ignore_index=True), crs=CRS_PROJ)
    for c in CATEGORIES:
        log(f"  {c:12s}: {(poi['category'] == c).sum()} POIs")
    return poi


# =============================================================================
# STAGE 3 — 100 m fishnet, land-masked
# =============================================================================
def make_fishnet(land_gdf, cell):
    minx, miny, maxx, maxy = land_gdf.total_bounds
    xs = np.arange(minx, maxx + cell, cell)
    ys = np.arange(miny, maxy + cell, cell)
    cells = [box(x, y, x + cell, y + cell) for x in xs[:-1] for y in ys[:-1]]
    grid = gpd.GeoDataFrame(geometry=cells, crs=CRS_PROJ)
    # keep cells that intersect the land mask
    land_u = land_gdf.union_all()
    grid = grid[grid.intersects(land_u)].reset_index(drop=True)
    grid["cell_id"] = np.arange(len(grid))
    grid["cell_area_m2"] = grid.geometry.area
    return grid


def stage_grid(cfg, land_gdf):
    banner("STAGE 3: CREATE 100 m GRID (land-masked)")
    cell = cfg["params"]["cell_size"]
    grid = make_fishnet(land_gdf, cell)
    log(f"{len(grid)} cells @ {cell} m")
    return grid


# =============================================================================
# STAGE 4 — join 5 indicators + 3 POI counts to each cell
# =============================================================================
def count_points_in_cells(grid, pts):
    if len(pts) == 0:
        return np.zeros(len(grid), dtype=int)
    j = gpd.sjoin(pts[["geometry"]], grid[["cell_id", "geometry"]],
                  how="inner", predicate="within")
    cnt = j.groupby("cell_id").size()
    out = np.zeros(len(grid), dtype=int)
    out[cnt.index.values] = cnt.values
    return out


def areal_pop(grid, pop_gdf, pop_field, is_density):
    """Areal interpolation of population to cells -> persons per cell."""
    pop = pop_gdf[[pop_field, "geometry"]].copy()
    if is_density:                                   # persons / km^2 -> count
        pop["__count"] = pop[pop_field] * (pop.geometry.area / 1e6)
    else:
        pop["__count"] = pop[pop_field]
    pop["__pa"] = pop["__count"] / pop.geometry.area  # persons per m^2
    inter = gpd.overlay(grid[["cell_id", "geometry"]],
                        pop[["__pa", "geometry"]], how="intersection")
    inter["__p"] = inter["__pa"] * inter.geometry.area
    s = inter.groupby("cell_id")["__p"].sum()
    out = np.zeros(len(grid))
    out[s.index.values] = s.values
    return out


def road_length_in_cells(grid, roads, len_field):
    inter = gpd.overlay(grid[["cell_id", "geometry"]],
                        roads[["geometry"]], how="intersection",
                        keep_geom_type=False)
    inter = inter[inter.geometry.geom_type.isin(["LineString", "MultiLineString"])]
    inter["__len"] = inter.geometry.length
    s = inter.groupby("cell_id")["__len"].sum()
    out = np.zeros(len(grid))
    out[s.index.values] = s.values
    return out


def lucc_urban_pct(grid, lucc, code_field, urban_max=54):
    lucc = lucc.copy()
    lucc["__urban"] = (lucc[code_field].fillna(0).astype(float) <= urban_max) & \
                      (lucc[code_field].fillna(0).astype(float) >= 1)
    inter = gpd.overlay(grid[["cell_id", "cell_area_m2", "geometry"]],
                        lucc[["__urban", "geometry"]], how="intersection")
    inter["__a"] = inter.geometry.area
    inter["__ua"] = inter["__a"] * inter["__urban"].astype(float)
    g = inter.groupby("cell_id").agg(u=("__ua", "sum"), a=("__a", "sum"))
    pct = (g["u"] / g["a"]).clip(0, 1)
    out = np.full(len(grid), 0.5)                    # neutral fallback
    out[pct.index.values] = pct.values
    return out


def stage_indicators(cfg, grid, poi, pop_gdf, roads, lucc, bus):
    banner("STAGE 4: JOIN INDICATORS TO GRID")
    fm = cfg["field_mapping"]
    area_ha = grid["cell_area_m2"].values / 1e4

    # 4a POI counts per category
    for c in CATEGORIES:
        grid[f"poi_{c}"] = count_points_in_cells(grid, poi[poi["category"] == c])
    log("4a POI counts: " +
        ", ".join(f"{c}={int(grid[f'poi_{c}'].sum())}" for c in CATEGORIES))

    # 4b population density (persons / ha)
    pf = first_field(pop_gdf, [fm.get("population_count", "Averag_pop"),
                               "Averag_pop", "pop", "POP"])
    pop_cnt = areal_pop(grid, pop_gdf, pf, cfg["params"].get("pop_is_density", False))
    grid["pop_density"] = pop_cnt / np.maximum(area_ha, 1e-9)
    log(f"4b pop_density: mean={grid['pop_density'].mean():.1f} /ha")

    # 4c road density (m / ha)
    rf = first_field(roads, [fm.get("road_length", "Shape_Leng"), "length", "Shape_Leng"])
    rlen = road_length_in_cells(grid, roads, rf)
    grid["road_density"] = rlen / np.maximum(area_ha, 1e-9)
    log(f"4c road_density: total={rlen.sum()/1000:.1f} km")

    # 4d LUCC urban %
    if lucc is not None:
        cf = first_field(lucc, [fm.get("lucc_code", "type_code"), "type_code", "code"])
        grid["lucc_urban_pct"] = lucc_urban_pct(grid, lucc, cf,
                                                cfg["params"].get("urban_code_max", 54))
    else:
        grid["lucc_urban_pct"] = 0.5
    log(f"4d lucc_urban_pct: mean={grid['lucc_urban_pct'].mean():.3f}")

    # 4e transit: bus_density (stations/ha) + transit_access (0-1 normalized)
    if bus is not None and len(bus):
        bcnt = count_points_in_cells(grid, bus)
        grid["bus_density"] = bcnt / np.maximum(area_ha, 1e-9)
        # transit_access = nearby-station accessibility, min-max normalized to 0-1
        cent = np.column_stack([grid.geometry.centroid.x, grid.geometry.centroid.y])
        bxy = np.column_stack([bus.geometry.x, bus.geometry.y])
        tree = cKDTree(bxy)
        r = cfg["params"].get("transit_radius", 500)
        near = tree.query_ball_point(cent, r=r)
        acc = np.array([sum(1.0 for _ in idx) for idx in near], dtype=float)
        grid["transit_access"] = (acc - acc.min()) / max(acc.max() - acc.min(), 1e-9)
        log(f"4e transit: {len(bus)} stations; "
            f"bus_density mean={grid['bus_density'].mean():.3f}")
    else:
        grid["bus_density"] = 0.0
        grid["transit_access"] = 0.0
        log("4e transit: no station layer")
    return grid


# =============================================================================
# STAGE 5 — fit 3 GWR models (mgwr) with OLS fallback
# =============================================================================
def ols_fit(Xs, y):
    """Global OLS with intercept. Returns params vector length k+1."""
    A = np.column_stack([np.ones(len(Xs)), Xs])
    beta, *_ = np.linalg.lstsq(A, y, rcond=None)
    return beta.flatten()


def fit_one_gwr(active, x_cols, ycol, min_active=20):
    """
    Fit a GWR for one category. Returns a store dict with everything needed
    to predict, or None if the category has no usable signal.
    Falls back to OLS on singular matrix / too few active cells / no mgwr.
    """
    n = len(active)
    log(f"Active: {n}")
    if n < min_active or active[ycol].std() == 0:
        log("  -> too few active cells / no variance — OLS fallback")
        mode = "ols"
    else:
        mode = "gwr" if HAVE_MGWR else "ols"

    X = active[x_cols].values.astype(float)
    y = active[ycol].values.astype(float).reshape(-1, 1)
    xm, xs = X.mean(0), X.std(0)
    xs[xs == 0] = 1.0
    Xs = (X - xm) / xs
    coords = np.column_stack([active.geometry.centroid.x,
                              active.geometry.centroid.y])

    store = {"xm": xm, "xs": xs, "coords": coords, "x_cols": x_cols}

    if mode == "gwr":
        try:
            bw = Sel_BW(coords, y, Xs, kernel="bisquare", fixed=False).search()
            res = GWR(coords, y, Xs, bw, kernel="bisquare", fixed=False).fit()
            store.update(mode="gwr", params=res.params, n_params=res.params.shape[1],
                         bw=bw, r2=res.R2, aicc=res.aicc)
            log(f"  BW={bw}  R2={res.R2:.4f}  params={res.params.shape[1]}")
            return store
        except Exception as e:                       # singular matrix etc.
            log(f"  GWR failed ({type(e).__name__}: {e}) — OLS fallback")

    # OLS fallback
    beta = ols_fit(Xs, y)
    store.update(mode="ols", params=beta, n_params=len(beta))
    yhat = np.column_stack([np.ones(len(Xs)), Xs]) @ beta
    ss_res = float(((y.flatten() - yhat) ** 2).sum())
    ss_tot = float(((y.flatten() - y.mean()) ** 2).sum())
    store["r2"] = 1 - ss_res / ss_tot if ss_tot > 0 else 0.0
    log(f"  OLS R2={store['r2']:.4f}")
    return store


def stage_gwr(cfg, grid):
    banner("STAGE 5: FIT 3 GWR MODELS")
    stores = {}
    rows = []
    for c in CATEGORIES:
        log(f"-- {c.upper()} --")
        active = grid[grid[f"poi_{c}"] > 0].copy()
        s = fit_one_gwr(active, X_COLS, f"poi_{c}",
                        min_active=cfg["params"].get("min_active_cells", 20))
        stores[c] = s
        rows.append({"category": c, "active": len(active),
                     "mode": s["mode"], "R2": round(s.get("r2", float("nan")), 4)})
    print()
    print(pd.DataFrame(rows).to_string(index=False))
    return stores


# =============================================================================
# STAGE 6 — TCNTE future scenario (zonal growth factors)
# =============================================================================
def assign_zone(cfg, grid, site_geom):
    z = pd.Series(["periphery"] * len(grid), index=grid.index, dtype=object)
    cent = grid.geometry.centroid
    g = cfg["data"]
    # order matters: design_site overrides any TCNTE bbox
    def mark(layer_key, name):
        nonlocal z
        if g.get(layer_key):
            poly = read_layer(g[layer_key]).union_all()
            z = z.mask(cent.within(poly), name)
    mark("tcnte_east_bbox", "tcnte_east")
    mark("tcnte_west_bbox", "tcnte_west")
    if g.get("town_center_bbox"):
        tc = read_layer(g["town_center_bbox"]).union_all()
        z = z.mask(cent.within(tc), "town_center")
    z = z.mask(cent.within(site_geom.buffer(0)), "design_site")
    return z.values


def stage_future(cfg, grid, site_geom):
    banner("STAGE 6: FUTURE SCENARIO — TCNTE")
    fut = grid.copy()
    fut["zone"] = assign_zone(cfg, grid, site_geom)
    counts = pd.Series(fut["zone"]).value_counts().to_dict()
    log("Zones: " + ", ".join(f"{k}={v}" for k, v in counts.items()))

    gf = cfg["growth_factors"]
    for var, zmap in gf["multipliers"].items():
        for zone, factor in zmap.items():
            m = fut["zone"] == zone
            if var == "transit_access":
                fut.loc[m, var] = np.minimum(fut.loc[m, var] * factor, 1.0)
            else:
                fut.loc[m, var] = fut.loc[m, var] * factor
    for zone, target in gf.get("lucc_targets", {}).items():
        m = fut["zone"] == zone
        fut.loc[m, "lucc_urban_pct"] = np.maximum(fut.loc[m, "lucc_urban_pct"], target)
    log("Growth factors applied by zone")
    return fut


# =============================================================================
# STAGE 7 — predict on-site demand change per category
# =============================================================================
def predict_cat(store, future, x_cols):
    Xf = future[x_cols].values.astype(float)
    Xfs = (Xf - store["xm"]) / store["xs"]
    if store["mode"] == "gwr":
        tree = cKDTree(store["coords"])
        fc = np.column_stack([future.geometry.centroid.x,
                              future.geometry.centroid.y])
        _, nn = tree.query(fc)
        lp = store["params"][nn]
        if store["n_params"] == len(x_cols) + 1:
            Xm = np.column_stack([np.ones(len(Xfs)), Xfs])
        else:
            Xm = Xfs
        pred = (Xm * lp).sum(axis=1)
    else:
        Xm = np.column_stack([np.ones(len(Xfs)), Xfs])
        pred = Xm @ store["params"]
    return np.asarray(pred).flatten().clip(min=0)


def stage_predict(cfg, grid, future, stores, site_geom):
    banner("STAGE 7: PREDICT")
    on_mask = future.geometry.centroid.within(site_geom.buffer(0)).values
    summary = []
    for c in CATEGORIES:
        s = stores[c]
        if s is None:
            future[f"pred_{c}"] = future[f"poi_{c}"]
        else:
            future[f"pred_{c}"] = predict_cat(s, future, X_COLS)
        future[f"change_{c}"] = future[f"pred_{c}"] - future[f"poi_{c}"]
        cur = float(future.loc[on_mask, f"poi_{c}"].sum())
        pred = float(future.loc[on_mask, f"pred_{c}"].sum())
        summary.append({"category": c, "on_site_current": round(cur, 1),
                        "on_site_predicted": round(pred, 1),
                        "change": round(pred - cur, 1),
                        "mode": s["mode"] if s else "none"})
        log(f"{c:12s}: current={cur:.1f}  predicted={pred:.1f}  "
            f"change=+{pred-cur:.1f}")
    return future, pd.DataFrame(summary)


# =============================================================================
# STAGE 8 — export
# =============================================================================
def stage_export(cfg, grid, future, summary):
    banner("STAGE 8: EXPORT")
    out = Path(cfg["output_dir"]); out.mkdir(parents=True, exist_ok=True)
    gpkg = out / "GWR_reproduction.gpkg"
    grid.to_file(gpkg, layer="grid_indicators", driver="GPKG")
    future.to_file(gpkg, layer="grid_future", driver="GPKG")
    summary.to_csv(out / "prediction_summary.csv", index=False)
    log(f"GPKG: {gpkg}")
    log(f"CSV : {out/'prediction_summary.csv'}")
    try:
        make_figure(future, summary, out / "prediction_3x3.png")
        log(f"FIG : {out/'prediction_3x3.png'}")
    except Exception as e:
        log(f"figure skipped: {e}")


def make_figure(future, summary, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    BG, FG = "#1a1a2e", "#E2E8F0"
    fig, axes = plt.subplots(3, 3, figsize=(13, 12), facecolor=BG)
    cols = ["poi_{}", "pred_{}", "change_{}"]
    titles = ["Current", "Predicted (2033)", "Change"]
    cmaps = ["YlOrRd", "YlOrRd", "RdBu_r"]
    for i, c in enumerate(CATEGORIES):
        for j, col in enumerate(cols):
            ax = axes[i, j]; ax.set_facecolor(BG)
            future.plot(column=col.format(c), ax=ax, cmap=cmaps[j],
                        legend=True, markersize=1)
            ax.set_title(f"{c} — {titles[j]}", color=FG, fontsize=10)
            ax.tick_params(colors=FG, labelsize=6)
            for sp in ax.spines.values():
                sp.set_color(FG)
    fig.tight_layout()
    fig.savefig(path, dpi=300, facecolor=BG)
    plt.close(fig)


# =============================================================================
# driver
# =============================================================================
def parse_stages(spec, n=8):
    if not spec:
        return set(range(1, n + 1))
    out = set()
    for part in spec.split(","):
        if "-" in part:
            a, b = part.split("-"); out |= set(range(int(a), int(b) + 1))
        else:
            out.add(int(part))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("config")
    ap.add_argument("--stages", default=None,
                    help="e.g. '1-5' or '3,4,5' (default: all)")
    args = ap.parse_args()
    cfg = json.loads(Path(args.config).read_text(encoding="utf-8"))
    stages = parse_stages(args.stages)

    banner("GWR REPRODUCTION — Tung Chung TOD")
    log(f"mgwr available: {HAVE_MGWR}")

    site, site_geom, study_gdf, land_gdf = stage_land(cfg)
    poi = stage_poi(cfg, study_gdf)
    grid = stage_grid(cfg, land_gdf)

    g = cfg["data"]
    pop_gdf = read_layer(g["pop_fc"])
    roads = read_layer(g["roads_fc"])
    lucc = read_layer(g["lucc_fc"]) if g.get("lucc_fc") else None
    bus = read_layer(g["bus_fc"]) if g.get("bus_fc") else None

    grid = stage_indicators(cfg, grid, poi, pop_gdf, roads, lucc, bus)
    stores = stage_gwr(cfg, grid)
    future = stage_future(cfg, grid, site_geom)
    future, summary = stage_predict(cfg, grid, future, stores, site_geom)
    stage_export(cfg, grid, future, summary)

    banner("DONE")
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
