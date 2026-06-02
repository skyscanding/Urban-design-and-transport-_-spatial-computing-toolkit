"""Generate synthetic Tung-Chung-shaped data and run the full pipeline."""
import json, numpy as np, geopandas as gpd
from pathlib import Path
from shapely.geometry import Polygon, Point, LineString, box

rng = np.random.default_rng(7)
# Default output directory: ./synthetic/ relative to script location
SCRIPT_DIR = Path(__file__).resolve().parent
D = SCRIPT_DIR / "synthetic"; D.mkdir(exist_ok=True)
CRS = "EPSG:2326"

# centre near the real Tung Chung site centroid (E811711 N816894)
cx, cy = 811711, 816894

def gsave(geoms, attrs, name):
    gdf = gpd.GeoDataFrame(attrs, geometry=geoms, crs=CRS)
    gdf.to_file(D / name)
    return gdf

# site (~ 200 x 150 m)
site = box(cx-100, cy-75, cx+100, cy+75)
gsave([site], {"id":[1]}, "site.shp")

# land mask = big square; airport = a chunk to exclude on the west
land = box(cx-1700, cy-1700, cx+1700, cy+1700)
gsave([land], {"id":[1]}, "land.shp")
airport = box(cx-1700, cy-1700, cx-1100, cy+1700)
gsave([airport], {"id":[1]}, "airport.shp")

# population polygons (grid of blocks) with Averag_pop counts
polys, pops = [], []
step = 400
for x in range(cx-1600, cx+1600, step):
    for y in range(cy-1600, cy+1600, step):
        polys.append(box(x, y, x+step, y+step))
        # higher pop to the east (town centre direction)
        pops.append(float(rng.integers(200, 6000) * (1 + (x-cx)/3000.0)))
gsave(polys, {"Averag_pop": pops}, "pop.shp")

# roads: random network of line segments
lines = []
for _ in range(400):
    x0 = rng.uniform(cx-1600, cx+1600); y0 = rng.uniform(cy-1600, cy+1600)
    ang = rng.uniform(0, 2*np.pi); L = rng.uniform(80, 400)
    lines.append(LineString([(x0, y0), (x0+L*np.cos(ang), y0+L*np.sin(ang))]))
gsave(lines, {"Shape_Leng":[ln.length for ln in lines]}, "roads.shp")

# LUCC polygons with type_code (1-54 urban, 61+ non-urban)
lpolys, codes = [], []
for x in range(cx-1700, cx+1700, 300):
    for y in range(cy-1700, cy+1700, 300):
        lpolys.append(box(x, y, x+300, y+300))
        codes.append(int(rng.choice([1,2,11,31,41,61,71,73], p=[.25,.2,.1,.1,.1,.1,.1,.05])))
gsave(lpolys, {"type_code": codes}, "lucc.shp")

# bus stations (points), denser near site
bpts = [Point(cx+rng.normal(0,500), cy+rng.normal(0,500)) for _ in range(120)]
gsave(bpts, {"id":list(range(len(bpts)))}, "bus.shp")

# TCNTE zone bboxes
gsave([box(cx-200, cy+200, cx+1600, cy+1600)], {"z":["E"]}, "tcnte_east.shp")
gsave([box(cx-1100, cy-1600, cx+200, cy-200)], {"z":["W"]}, "tcnte_west.shp")

# POI source files with midType strings matching the rules.
# commercial: many points (dense -> likely to need OLS fallback)
# community: moderate ; sports_rec: few (-> forces OLS fallback via min_active)
def poi_file(name, midtypes, n, spread=1500):
    pts, mts = [], []
    for _ in range(n):
        pts.append(Point(cx+rng.uniform(-spread,spread), cy+rng.uniform(-spread,spread)))
        mts.append(str(rng.choice(midtypes)))
    gsave(pts, {"midType": mts}, name)

poi_file("购物服务.shp", ["购物相关场所","商场","便利店"], 700)
poi_file("餐饮服务.shp", ["中餐厅","快餐厅","休闲餐饮场所"], 500)
poi_file("公司企业.shp", ["公司","知名企业","工厂"], 400)      # 工厂 should be excluded
poi_file("金融保险服务.shp", ["银行","金融保险服务机构"], 120)
poi_file("住宿服务.shp", ["宾馆酒店","旅馆招待所"], 80)
poi_file("生活服务.shp", ["生活服务场所","美容美发店"], 200)
poi_file("科教文化服务.shp", ["学校","培训机构","科研机构","图书馆","文化宫"], 90)
poi_file("医疗保健服务.shp", ["综合医院","诊所","动物医疗"], 60)  # 动物医疗 excluded
poi_file("商务住宅.shp", ["社区中心","住宅区"], 40)             # only 社区中心 kept
poi_file("体育休闲服务.shp", ["运动场馆","休闲场所","酒吧"], 30) # 酒吧 excluded

# build a config pointing at synthetic files
cfg = json.loads((SCRIPT_DIR.parent / "config_tung_chung.json").read_text())
cfg["output_dir"] = str(D / "out")
d = cfg["data"]
d.update(
    site_fc=str(D/"site.shp"), land_fc=str(D/"land.shp"), airport_fc=str(D/"airport.shp"),
    pop_fc=str(D/"pop.shp"), roads_fc=str(D/"roads.shp"), lucc_fc=str(D/"lucc.shp"),
    bus_fc=str(D/"bus.shp"), tcnte_east_bbox=str(D/"tcnte_east.shp"),
    tcnte_west_bbox=str(D/"tcnte_west.shp"), town_center_bbox=None,
    poi_sources=[str(D/f) for f in [
        "购物服务.shp","餐饮服务.shp","公司企业.shp","金融保险服务.shp","住宿服务.shp",
        "生活服务.shp","科教文化服务.shp","医疗保健服务.shp","商务住宅.shp","体育休闲服务.shp"]],
)
Path(D/"config_synth.json").write_text(json.dumps(cfg, ensure_ascii=False, indent=2))
print("synthetic data + config_synth.json written to", D)
