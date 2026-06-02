# Spatial Computing Toolkit

GIS analysis pipelines for urban spatial computing research, developed and validated on the **Tung Chung TOD** case study (Hong Kong).

## What's Inside

| Tool | Description | Runtime | License |
|------|-------------|---------|---------|
| [**QGIS Cookbook**](qgis-cookbook/) | 300+ CLI recipes for spatial analysis, no GUI needed | QGIS 3.x (free) | MIT |
| [**GWR Pipeline**](gwr-pipeline/) | 6-step arcpy pipeline: POI classification → dasymetric population → indicator grid → GWR fit → future prediction → network flow assignment | ArcGIS Pro 3.x | MIT |
| [**GWR Reproduction**](gwr-reproduction/) | 8-stage open-source reproduction (geopandas + mgwr): 3 category models, 5 indicators, OLS fallback, TCNTE 2033 scenario | Python 3.x (no ArcGIS) | MIT |

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

An automated arcpy pipeline that uses **Geographically Weighted Regression** to model how facility distribution relates to built-environment indicators, then predicts future distribution under population and infrastructure growth scenarios.

**Validated against**: Tung Chung Tat Tung Road Bus Terminus (4.61 ha TOD site, 100k+ catchment population, TCNTE 2033 projections).

**Pipeline steps:**

```
Step 1: POI Time Classification     → Classify facilities as day/night/all-day
Step 2: Dasymetric Population        → Census blocks → building-level (by height)
Step 3: Indicator Grid               → 50m fishnet + spatial joins
Step 4: GWR Model Fit                → Spatially-varying regression (arcpy.stats.GWR)
Step 5: Future Prediction            → Apply model to TCNTE 2033 scenario
Step 5b: Network Flow Assignment     → Pedestrian LOS + gap detection (networkx)
```

Fully configurable via JSON. Robust field-name resolution, set your column names once, scripts auto-detect or fail with clear messages.

📖 **[Read the full documentation →](gwr-pipeline/)**

## GWR Reproduction

An **open-source, licence-free** reproduction of the original studio GWR pipeline. Built on `geopandas` + `mgwr` — runs anywhere with **no ArcGIS required**. Faithfully replicates the analytically load-bearing choices that the arcpy toolkit did not reproduce.

**What this adds over the arcpy pipeline:**
- 3 independent category models (commercial / community / sports_rec) vs. 1 generic `poi_count`
- 5 explanatory variables (pop, road, LUCC, bus, transit) vs. 2
- Adaptive bisquare kernel via `mgwr` matching the original `GWR_Prediction_v3`
- OLS fallback on singular matrix (the commercial model historically fell back)
- Per-zone TCNTE 2033 growth factors applied in code
- Synthetic data generator for smoke-testing without real data

**Pipeline stages:**

```
Stage 1: Site + Study Buffer + Land Mask  → Airport polygon excluded
Stage 2: POI Reclassification             → substring rules → 3 categories
Stage 3: 100m Fishnet                      → Clipped to land mask
Stage 4: Indicator Join                    → 5 variables + 3 POI counts per cell
Stage 5: GWR Model Fit                     → mgwr adaptive bisquare + OLS fallback
Stage 6: TCNTE Future Scenario             → Per-zone growth multipliers
Stage 7: Predict                           → On-site demand change per category
Stage 8: Export                            → GeoPackage + CSV + 3x3 PNG figure
```

📖 **[Read the full documentation →](gwr-reproduction/)**

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
    ├── config_template.json
    └── scripts/
        ├── _utils.py
        ├── master_pipeline.py
        ├── step1_classify_poi.py
        ├── step2_pop_allocate.py
        ├── step3_build_grid.py
        ├── step4_gwr_model.py
        └── step5_net_assign.py
└── gwr-reproduction/
    ├── README.md                   ← Open-source reproduction (geopandas + mgwr)
    ├── requirements.txt
    ├── config_tung_chung.json
    └── scripts/
        ├── gwr_reproduce.py        ← 8-stage pipeline
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
# Install dependencies
pip install -r gwr-pipeline/requirements.txt

# Edit config
cp gwr-pipeline/config_template.json my_project.json

# Run
python gwr-pipeline/scripts/master_pipeline.py my_project.json
```

Requires ArcGIS Pro 3.x with arcpy.

### GWR Reproduction
```bash
# Install open-source dependencies
pip install -r gwr-reproduction/requirements.txt

# Edit data paths in config
# (edit gwr-reproduction/config_tung_chung.json to point at your data)

# Run the full 8-stage pipeline
python gwr-reproduction/scripts/gwr_reproduce.py gwr-reproduction/config_tung_chung.json

# Partial run (e.g. rebuild grid + refit only)
python gwr-reproduction/scripts/gwr_reproduce.py gwr-reproduction/config_tung_chung.json --stages 3-5

# Smoke-test with synthetic data (no real data needed)
python gwr-reproduction/scripts/_make_synthetic.py
python gwr-reproduction/scripts/gwr_reproduce.py gwr-reproduction/scripts/synthetic/config_synth.json
```

No ArcGIS licence required.

## Case Study: Tung Chung TOD

All three tools were developed for the **Tung Chung Tat Tung Road Bus Terminus** design studio:

- **Site**: 4.61 ha, Sports Centre programme
- **Data**: 1,184 POIs, 598 buildings, 2,408 road segments, 100,531 catchment population
- **Future scenario**: TCNTE 2033, population 116k → 320k, +877,000 m² GFA
- **Key findings**: 50 pedestrian segments at LOS E (capacity exceeded), 1 critical connectivity gap across highway, evening economy gap identified via POI time classification

---

# 中文说明

城市空间计算研究的 GIS 分析工具包，基于 **香港东涌 TOD** 案例开发与验证。

## 包含工具

| 工具 | 说明 | 运行环境 | 协议 |
|------|------|---------|------|
| [**QGIS 操作手册**](qgis-cookbook/) | 300+ 条命令行空间分析配方，无需 GUI | QGIS 3.x（免费） | MIT |
| [**GWR 分析管道**](gwr-pipeline/) | 6 步 arcpy 自动化管道：POI 时段分类 → 人口分配 → 指标网格 → GWR 拟合 → 未来预测 → 网络流量分配 | ArcGIS Pro 3.x | MIT |
| [**GWR 复现**](gwr-reproduction/) | 8 阶段开源复现（geopandas + mgwr）：3 类模型、5 项指标、OLS 回退、TCNTE 2033 情景 | Python 3.x（无需 ArcGIS） | MIT |

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

基于 arcpy 的自动化管道，使用**地理加权回归**建模设施分布与建成环境指标的关系，并在人口和基础设施增长情景下预测未来的设施分布。

**验证案例：** 东涌达东路巴士总站地块（4.61 公顷 TOD 项目，10 万+ 覆盖人口，TCNTE 2033 规划预测）。

**管道步骤：**

```
Step 1: POI 时段分类     → 将设施分为日间/夜间/全天运营
Step 2: 人口分配            → 从普查区块分配到建筑楼层（按高度加权）
Step 3: 指标网格构建        → 50m 渔网网格 + 空间连接
Step 4: GWR 模型拟合        → 空间变系数回归（arcpy.stats.GWR）
Step 5: 未来情景预测        → 将模型应用于 TCNTE 2033 情景
Step 5b: 网络流量分配      → 行人服务水平 + 断连区域检测（networkx）
```

通过 JSON 配置文件全参数化控制。字段名分辨率设计：在配置中声明数据集的列名，脚本自动匹配或报清晰错误。

📖 **[阅读完整文档 →](gwr-pipeline/)**

## GWR 复现

基于 `geopandas` + `mgwr` 的**开源、无需许可**版本，完整复现原始工作室 GWR 管道。无需 ArcGIS，随处运行。忠实还原了 arcpy 工具包未曾复制的关键分析决策。

**相较 arcpy 管道的增强：**
- 3 个独立类别模型（商业 / 社区 / 体育休闲）vs. 1 个通用 `poi_count`
- 5 个解释变量（人口、道路、土地利用、公交、交通可达）vs. 2 个
- 通过 `mgwr` 实现自适应 bisquare 核，与原始 `GWR_Prediction_v3` 一致
- 奇异矩阵自动回退至 OLS（商业模型历史上曾触发回退）
- 按区域应用 TCNTE 2033 增长因子
- 提供合成数据生成器，无需真实数据即可验证流程

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

📖 **[阅读完整文档 →](gwr-reproduction/)**

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
    ├── config_template.json
    └── scripts/
        ├── _utils.py               ← 共享字段解析工具
        ├── master_pipeline.py      ← 管道总控脚本
        ├── step1_classify_poi.py   ← POI 时段分类
        ├── step2_pop_allocate.py   ← 人口分配
        ├── step3_build_grid.py     ← 网格 + 指标
        ├── step4_gwr_model.py      ← GWR 拟合 + 预测
        └── step5_net_assign.py     ← 行人网络流量分配
└── gwr-reproduction/
    ├── README.md                   ← 开源复现 (geopandas + mgwr)
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
# 安装依赖
pip install -r gwr-pipeline/requirements.txt

# 编辑配置文件
cp gwr-pipeline/config_template.json my_project.json

# 运行
python gwr-pipeline/scripts/master_pipeline.py my_project.json
```

需要 ArcGIS Pro 3.x 及 arcpy 许可。

### GWR 复现
```bash
# 安装开源依赖
pip install -r gwr-reproduction/requirements.txt

# 编辑配置文件中的数据路径
# （修改 gwr-reproduction/config_tung_chung.json 指向你的数据）

# 运行完整 8 阶段管道
python gwr-reproduction/scripts/gwr_reproduce.py gwr-reproduction/config_tung_chung.json

# 部分运行（例如仅重建网格 + 重新拟合）
python gwr-reproduction/scripts/gwr_reproduce.py gwr-reproduction/config_tung_chung.json --stages 3-5

# 使用合成数据快速验证（无需真实数据）
python gwr-reproduction/scripts/_make_synthetic.py
python gwr-reproduction/scripts/gwr_reproduce.py gwr-reproduction/scripts/synthetic/config_synth.json
```

无需 ArcGIS 许可。

## 案例研究：东涌 TOD

本工具包的全部三种工具均为 **东涌达东路巴士总站** 设计课题开发：

- **地块**：4.61 公顷，Sports Centre 功能定位
- **数据**：1,184 个 POI、598 栋建筑、2,408 条道路分段、覆盖 100,531 人口
- **未来情景**：TCNTE 2033 规划, 人口从 11.6 万增至 32 万，新增 877,000 m² 建筑面积
- **关键发现**：50 段人行道 LOS E（容量不足），1 处穿越主干道的严重断连，POI 时段分类揭示了夜间经济缺口

## License

MIT
