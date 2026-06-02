# Spatial Computing Toolkit

GIS analysis pipelines for urban spatial computing research, developed and validated on the **Tung Chung TOD** case study (Hong Kong).

## What's Inside

| Tool | Description | Runtime | License |
|------|-------------|---------|---------|
| [**QGIS Cookbook**](qgis-cookbook/) | 300+ CLI recipes for spatial analysis, no GUI needed | QGIS 3.x (free) | MIT |
| [**GWR Pipeline**](gwr-pipeline/) | 8-stage open-source pipeline (geopandas + mgwr): 3 category models, 5 indicators, OLS fallback, TCNTE 2033 scenario | Python 3.x (no ArcGIS) | MIT |

## QGIS Cookbook

A comprehensive **QGIS 3.44** command-line reference covering the full spatial analysis workflow. Everything via `qgis_process` and GDAL, no mouse clicks.

**What you can do:**
- Data exploration (`ogrinfo`, `gdalinfo`)
- Coordinate re-projection (EPSG:2326 Hong Kong 1980 Grid)
- Spatial filtering & clipping by boundary, extent, or attribute
- Geometry operations: buffer, dissolve, centroid, voronoi, fix invalid geometries
- Field calculations with `CASE WHEN` for classification
- Spatial joins: count points in polygons, sum line lengths, nearest-neighbor joins
- Network analysis: shortest paths, service areas (isochrones)
- Grid statistics: zonal statistics, raster sampling
- GWR via SAGA
- Cartography: print layout export to PNG/PDF

Includes 4 complete, copy-paste-ready bash script workflows for common spatial data processing chains.

📖 **[Browse the Cookbook →](qgis-cookbook/)**

## GWR Pipeline

A faithful reproduction of the original studio GWR analysis, built on `geopandas` + `mgwr`. Runs anywhere with **no ArcGIS licence required**.

**Validated against**: Tung Chung Tat Tung Road Bus Terminus (4.61 ha TOD site, 100k+ catchment population, TCNTE 2033 projections).

**Pipeline stages:**

```
Stage 1: Site + Study Buffer + Land Mask  → Airport polygon excluded
Stage 2: POI Reclassification             → Substring rules → 3 categories
Stage 3: 100m Fishnet                      → Clipped to land mask
Stage 4: Indicator Join                    → 5 variables + 3 POI counts per cell
Stage 5: GWR Model Fit                     → mgwr adaptive bisquare + OLS fallback
Stage 6: TCNTE Future Scenario             → Per-zone growth multipliers
Stage 7: Predict                           → On-site demand change per category
Stage 8: Export                            → GeoPackage + CSV + 3x3 PNG figure
```

3 independent category models (commercial / community / sports_rec) with adaptive bisquare kernel, 5 explanatory variables (pop, road, LUCC, bus, transit), OLS fallback on singular matrix. Includes a synthetic data generator for smoke-testing without real data.

📖 **[Read the full documentation →](gwr-pipeline/)**

## Repository Structure

```
spatial-computing-toolkit/
├── README.md                       ← You are here
├── .gitignore
├── LICENSE
├── qgis-cookbook/
│   └── README.md                   ← 300+ QGIS CLI recipes
└── gwr-pipeline/
    ├── README.md                   ← Full documentation + Tung Chung case study
    ├── requirements.txt
    ├── config_tung_chung.json
    └── scripts/
        ├── gwr_reproduce.py        ← 8-stage pipeline (run this)
        └── _make_synthetic.py      ← Test data generator
```

## Getting Started

### QGIS Cookbook
```bash
# List all available QGIS processing algorithms
"D:\QGIS\bin\qgis_process-qgis.bat" list

# Run any recipe from the cookbook
"D:\QGIS\bin\qgis_process-qgis.bat" run native:buffer \
  --INPUT="site.shp" --DISTANCE=600 --OUTPUT="site_buf600.gpkg"
```

### GWR Pipeline
```bash
# Install open-source dependencies
pip install -r gwr-pipeline/requirements.txt

# Edit data paths in config
# (edit gwr-pipeline/config_tung_chung.json to point at your data)

# Run the full 8-stage pipeline
python gwr-pipeline/scripts/gwr_reproduce.py gwr-pipeline/config_tung_chung.json

# Partial run (e.g. rebuild grid + refit only)
python gwr-pipeline/scripts/gwr_reproduce.py gwr-pipeline/config_tung_chung.json --stages 3-5

# Smoke-test with synthetic data (no real data needed)
python gwr-pipeline/scripts/_make_synthetic.py
python gwr-pipeline/scripts/gwr_reproduce.py gwr-pipeline/scripts/synthetic/config_synth.json
```

No ArcGIS licence required.

## Case Study: Tung Chung TOD

The toolkit was developed for the **Tung Chung Tat Tung Road Bus Terminus** TOD design studio. The GWR pipeline's worked example is configured in [`gwr-pipeline/config_tung_chung.json`](gwr-pipeline/config_tung_chung.json) — see the [pipeline README](gwr-pipeline/) for inputs, the run command, and a committed example result.

- **Site**: Tat Tung Road Bus Terminus, EPSG:2326
- **Inputs**: 10 Amap POI files → 3 categories; population, road, land-use and transit layers; 100 m land-masked grid (~700 cells, airport excluded)
- **Future scenario**: TCNTE 2033, population 116k → 320k, +877,000 m² GFA, applied as per-zone growth multipliers
- **Key findings**: commercial demand saturated on-site (OLS fallback); community the dominant predicted gap (≈ +63 under TCNTE 2033); sports/recreation a secondary gap (≈ +32) — the evidence base for adding community + sports facilities above the transit hub

---

# 中文说明

城市空间计算研究的 GIS 分析工具包，基于 **香港东涌 TOD** 案例开发与验证。

## 包含工具

| 工具 | 说明 | 运行环境 | 协议 |
|------|------|---------|------|
| [**QGIS 操作手册**](qgis-cookbook/) | 300+ 条命令行空间分析配方，无需 GUI | QGIS 3.x（免费） | MIT |
| [**GWR 分析管道**](gwr-pipeline/) | 8 阶段开源管道（geopandas + mgwr）：3 类模型、5 项指标、OLS 回退、TCNTE 2033 情景 | Python 3.x（无需 ArcGIS） | MIT |

## QGIS 操作手册

一份完整的 **QGIS 3.44** 命令行参考手册，覆盖空间分析全流程。全部通过 `qgis_process` 和 GDAL 完成，无需鼠标操作。

**核心能力：**
- 数据探查（`ogrinfo`、`gdalinfo`）
- 坐标重投影（EPSG:2326 香港 1980 格网）
- 按边界/范围/属性进行空间筛选与裁剪
- 几何操作：缓冲区、融合、质心、泰森多边形、修复无效几何
- 字段计算器 + `CASE WHEN` 条件分类
- 空间连接：多边形内点计数、线长度求和、最近邻连接
- 网络分析：最短路径、服务区（等时圈）
- 网格与分区统计
- 通过 SAGA 进行 GWR 地理加权回归
- 制图输出：打印布局导出为 PNG/PDF

含 4 套可直接复制运行的完整 bash 工作流脚本。

📖 **[浏览完整手册 →](qgis-cookbook/)**

## GWR 分析管道

基于 `geopandas` + `mgwr` 的开源实现，忠实复现原始工作室 GWR 分析。**无需 ArcGIS 许可**，随处运行。

**验证案例：** 东涌达东路巴士总站地块（4.61 公顷 TOD 项目，10 万+ 覆盖人口，TCNTE 2033 规划预测）。

**管道阶段：**

```
Stage 1: 场地 + 研究缓冲区 + 陆地掩膜  → 剔除机场多边形
Stage 2: POI 重分类                    → 子串匹配规则 → 3 个类别
Stage 3: 100m 渔网                      → 按陆地掩膜裁剪
Stage 4: 指标连接                       → 每格 5 个变量 + 3 个 POI 计数
Stage 5: GWR 模型拟合                    → mgwr 自适应 bisquare + OLS 回退
Stage 6: TCNTE 未来情景                  → 按区域增长倍数
Stage 7: 预测                           → 场地内各品类需求变化
Stage 8: 导出                           → GeoPackage + CSV + 3x3 图
```

3 个独立类别模型（商业 / 社区 / 体育休闲），自适应 bisquare 核，5 个解释变量（人口、道路、土地利用、公交、交通可达），奇异矩阵自动回退至 OLS。含合成数据生成器，无需真实数据即可验证流程。

📖 **[阅读完整文档 →](gwr-pipeline/)**

## 仓库结构

```
spatial-computing-toolkit/
├── README.md                       ← 本文件
├── .gitignore
├── LICENSE
├── qgis-cookbook/
│   └── README.md                   ← 300+ QGIS 命令行配方
└── gwr-pipeline/
    ├── README.md                   ← 完整文档 + 东涌案例研究
    ├── requirements.txt
    ├── config_tung_chung.json
    └── scripts/
        ├── gwr_reproduce.py        ← 8 阶段管道脚本
        └── _make_synthetic.py      ← 合成数据生成器
```

## 快速开始

### QGIS 操作手册
```bash
# 列出所有可用的 QGIS 处理算法
"D:\QGIS\bin\qgis_process-qgis.bat" list

# 运行手册中的任意配方
"D:\QGIS\bin\qgis_process-qgis.bat" run native:buffer \
  --INPUT="site.shp" --DISTANCE=600 --OUTPUT="site_buf600.gpkg"
```

### GWR 管道
```bash
# 安装开源依赖
pip install -r gwr-pipeline/requirements.txt

# 编辑配置文件中的数据路径
# （修改 gwr-pipeline/config_tung_chung.json 指向你的数据）

# 运行完整 8 阶段管道
python gwr-pipeline/scripts/gwr_reproduce.py gwr-pipeline/config_tung_chung.json

# 部分运行（例如仅重建网格 + 重新拟合）
python gwr-pipeline/scripts/gwr_reproduce.py gwr-pipeline/config_tung_chung.json --stages 3-5

# 使用合成数据快速验证（无需真实数据）
python gwr-pipeline/scripts/_make_synthetic.py
python gwr-pipeline/scripts/gwr_reproduce.py gwr-pipeline/scripts/synthetic/config_synth.json
```

无需 ArcGIS 许可。

## 案例研究：东涌 TOD

本工具包为 **东涌达东路巴士总站** TOD 设计课题开发。GWR 管道的示例配置见 [`gwr-pipeline/config_tung_chung.json`](gwr-pipeline/config_tung_chung.json)，输入数据、运行命令与示例结果详见 [管道说明文档](gwr-pipeline/)。

- **地块**：达东路巴士总站，EPSG:2326
- **输入**：10 个高德 POI 文件 → 3 个类别；人口、道路、土地利用与交通图层；100m 陆地掩膜网格（约 700 格，已剔除机场）
- **未来情景**：TCNTE 2033 规划，人口 11.6 万 → 32 万，新增 877,000 m² 建筑面积，按区域增长倍数施加
- **关键发现**：场地内商业需求已饱和（回退至 OLS）；社区设施为主要预测缺口（TCNTE 2033 下约 +63）；体育休闲为次要缺口（约 +32）——为在交通枢纽之上增设社区与体育设施提供依据

## License

MIT
