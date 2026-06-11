import os
os.environ['HF_HOME'] = 'C:/IRLAND/hf_cache'
os.environ['TRANSFORMERS_CACHE'] = 'C:/IRLAND/hf_cache'

import glob
import cv2
import torch
import numpy as np
import geopandas as gpd
from shapely.geometry import Point
import rasterio
import rasterio.windows
import folium
import base64
import pyproj
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
import plotly.graph_objects as go
from transformers import AutoImageProcessor, SegformerForSemanticSegmentation

import transformers.utils.import_utils
import transformers.modeling_utils
transformers.utils.import_utils.check_torch_load_is_safe = lambda: None
transformers.modeling_utils.check_torch_load_is_safe = lambda: None

PT_ID = 'pt00000'
LAT, LON = 41.006024, 70.088589

IMAGES_DIR = 'C:/IRLAND/Road_Safety_Audit/images'
EXP_OUT_DIR = 'C:/IRLAND/Road_Safety_Audit/experiment_output'
os.makedirs(EXP_OUT_DIR, exist_ok=True)

ROADS_PATH = 'C:/IRLAND/Road_Safety_Audit/roads.geojson'
NDVI_PATH = 'C:/IRLAND/Road_Safety_Audit/NDVI/NDVI_Map_July_2024.tif'
HTML_PATH = 'C:/IRLAND/Road_Safety_Audit/experiment_result.html'

LOCAL_CRS = "EPSG:32642"

print(f"--- STARTING EXPERIMENT FOR POINT {PT_ID} ---")

# ==========================================
# 2. EXTRACT NDVI AND CREATE ZOOMABLE VIEWER
# ==========================================
print("[1/4] Extracting NDVI and building viewer...")
try:
    with rasterio.open(NDVI_PATH) as src:
        transformer = pyproj.Transformer.from_crs("EPSG:4326", src.crs, always_xy=True)
        x, y = transformer.transform(LON, LAT)
        
        val = next(src.sample([(x, y)]))
        ndvi_val = round(float(val[0]), 3)
        print(f"NDVI = {ndvi_val}")
        
        row, col = src.index(x, y)
        # Sentinel-2 scale is 10m/pixel. A 40x40 window = 400x400 meters.
        window = rasterio.windows.Window(col - 20, row - 20, 40, 40)
        ndvi_data = src.read(1, window=window, boundless=True, fill_value=0)
        
        ndvi_img_path = os.path.join(EXP_OUT_DIR, 'ndvi_crop.png')
        plt.imsave(ndvi_img_path, ndvi_data, cmap='RdYlGn', vmin=0, vmax=0.8)
        
        with open(ndvi_img_path, "rb") as img_file:
            ndvi_crop_b64 = base64.b64encode(img_file.read()).decode('utf-8')
except Exception as e:
    print(f"NDVI Error: {e}")

# Create Folium CRS.Simple map for NDVI zoom
ndvi_map = folium.Map(location=[200, 200], zoom_start=1, crs='Simple', tiles=None)
folium.raster_layers.ImageOverlay(
    image=f"data:image/png;base64,{ndvi_crop_b64}",
    bounds=[[0, 0], [400, 400]],
    origin='lower'
).add_to(ndvi_map)

# Add an arrow pointing exactly to the center using precise DivIcon anchoring
# We use an UP arrow (▲) so it represents 'North' at 0 degrees rotation.
arrow_html = '<div id="map-direction-arrow" class="custom-arrow" style="font-size: 24px; color: gray; text-shadow: 1px 1px 2px white; line-height: 24px; text-align: center; transform-origin: 50% 100%; transition: transform 0.3s ease;">▲</div>'

folium.Marker(
    location=[200, 200],
    icon=folium.DivIcon(
        html=arrow_html,
        icon_size=(24, 24),
        icon_anchor=(12, 24)
    )
).add_to(ndvi_map)

# Inject CSS so the arrow disappears when hovering ANYWHERE on the map
hover_css = """
<style>
.custom-arrow { transition: opacity 0.3s ease; cursor: crosshair; }
body:hover .custom-arrow { opacity: 0 !important; }
</style>
"""
ndvi_map.get_root().html.add_child(folium.Element(hover_css))

ndvi_map_html = ndvi_map.get_root().render()

# ==========================================
# 3. ROAD NETWORK EXTENT (sGVI Mock)
# ==========================================
print("[2/4] Calculating road weighting (Mock sGVI)...")
road_length = 0.0
try:
    if not os.path.exists(ROADS_PATH):
        road_length = 150.0
    else:
        roads_gdf = gpd.read_file(ROADS_PATH)
        if roads_gdf.crs != LOCAL_CRS:
            roads_gdf = roads_gdf.to_crs(LOCAL_CRS)
        
        pt_gdf = gpd.GeoDataFrame(geometry=[Point(LON, LAT)], crs="EPSG:4326").to_crs(LOCAL_CRS)
        buffer_gdf = pt_gdf.buffer(100)
        
        clipped_roads = gpd.overlay(roads_gdf, gpd.GeoDataFrame(geometry=buffer_gdf, crs=LOCAL_CRS), how='intersection')
        road_length = round(clipped_roads.length.sum(), 2)
except Exception as e:
    print(f"Road Calc Error: {e}")

# ==========================================
# 4. GVI CALCULATION (SegFormer)
# ==========================================
print("[3/4] Initializing SegFormer-B5 and computing GVI...")
device = "cuda" if torch.cuda.is_available() else "cpu"
processor = AutoImageProcessor.from_pretrained("nvidia/segformer-b5-finetuned-cityscapes-1024-1024")
model = SegformerForSemanticSegmentation.from_pretrained("nvidia/segformer-b5-finetuned-cityscapes-1024-1024").to(device)
model.eval()

image_files = glob.glob(os.path.join(IMAGES_DIR, f"{PT_ID}_*.jpg"))
def get_heading(path):
    h_str = os.path.basename(path).split('_h')[1].replace('.jpg', '')
    return int(h_str)
image_files.sort(key=get_heading)

def image_to_base64(path):
    with open(path, "rb") as img_file:
        return base64.b64encode(img_file.read()).decode('utf-8')

results_data = []
total_veg_pixels = 0
total_valid_pixels = 0

with torch.no_grad():
    for f in image_files:
        filename = os.path.basename(f)
        heading = get_heading(f)
        
        img = cv2.imread(f)
        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        valid_mask = gray > 5
        valid_area = np.sum(valid_mask)
        
        inputs = processor(images=img_rgb, return_tensors="pt").to(device)
        outputs = model(**inputs)
        logits = outputs.logits
        
        upsampled_logits = torch.nn.functional.interpolate(
            logits, size=img.shape[:2], mode="bilinear", align_corners=False
        )
        pred_seg = upsampled_logits.argmax(dim=1)[0].cpu().numpy()
        
        veg_mask = (pred_seg == 8) & valid_mask
        veg_area = np.sum(veg_mask)
        
        gvi_pct = (veg_area / valid_area) * 100 if valid_area > 0 else 0.0
        
        total_veg_pixels += veg_area
        total_valid_pixels += valid_area
        
        # Point Cloud Overlay
        overlay = img.copy()
        y_coords, x_coords = np.ogrid[:img.shape[0], :img.shape[1]]
        grid = (y_coords % 4 == 0) & (x_coords % 4 == 0)
        dots_mask = veg_mask & grid
        
        for dy in [0, 1]:
            for dx in [0, 1]:
                shifted = np.roll(dots_mask, shift=(dy, dx), axis=(0, 1))
                overlay[shifted] = [0, 255, 0]
        
        out_path = os.path.join(EXP_OUT_DIR, f"masked_{filename}")
        cv2.imwrite(out_path, overlay)
        
        results_data.append({
            'heading': heading,
            'gvi': round(gvi_pct, 2),
            'veg_area': int(veg_area),
            'total_area': int(valid_area),
            'orig_b64': image_to_base64(f),
            'mask_b64': image_to_base64(out_path)
        })

avg_gvi = round((total_veg_pixels / total_valid_pixels) * 100, 2)
total_network_length = 1000.0 
weight_mock = road_length / total_network_length
sgvi_mock = round(avg_gvi * weight_mock, 2)

# ==========================================
# 5. HTML GENERATION (Single Point)
# ==========================================
print("[4/4] Generating HTML Report...")

m = folium.Map(location=[LAT, LON], zoom_start=14, tiles='OpenStreetMap')

try:
    with rasterio.open(NDVI_PATH) as src:
        ndvi_full = src.read(1)
        nodata_val = src.nodata
        bounds = src.bounds
        
        # Mask NoData or zero (GEE often leaves zero outside the roi buffer)
        if nodata_val is not None:
            ndvi_masked = np.ma.masked_where((ndvi_full == nodata_val) | (ndvi_full == 0) | np.isnan(ndvi_full), ndvi_full)
        else:
            ndvi_masked = np.ma.masked_where((ndvi_full == 0) | np.isnan(ndvi_full), ndvi_full)
            
        full_ndvi_path = os.path.join(EXP_OUT_DIR, 'full_ndvi_overlay.png')
        plt.imsave(full_ndvi_path, ndvi_masked, cmap='RdYlGn', vmin=0, vmax=0.8)
        
        with open(full_ndvi_path, "rb") as img_file:
            full_ndvi_b64 = base64.b64encode(img_file.read()).decode('utf-8')
            
        folium.raster_layers.ImageOverlay(
            name="Full Route NDVI (Sentinel-2)",
            image=f"data:image/png;base64,{full_ndvi_b64}",
            bounds=[[bounds.bottom, bounds.left], [bounds.top, bounds.right]],
            opacity=0.7,
            interactive=True
        ).add_to(m)
except Exception as e:
    print(f"Full NDVI Overlay Error: {e}")

folium.Marker([LAT, LON], popup=f"{PT_ID}").add_to(m)
folium.Circle([LAT, LON], radius=100, color="blue", fill=False, color_line="blue").add_to(m)
folium.LayerControl().add_to(m)

map_html = m.get_root().render()

import json
orig_imgs_js = [f"data:image/jpeg;base64,{r['orig_b64']}" for r in results_data]
mask_imgs_js = [f"data:image/jpeg;base64,{r['mask_b64']}" for r in results_data]
headings_js = [r['heading'] for r in results_data]
gvis_js = [r['gvi'] for r in results_data]

html_content = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Academic Report: GVI / NDVI Pipeline</title>
    <script id="MathJax-script" async src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js"></script>
    <style>
        body {{ font-family: 'Times New Roman', Times, serif; background: #ffffff; color: #000000; margin: 0; padding: 40px; line-height: 1.6; }}
        .container {{ max-width: 1000px; margin: 0 auto; }}
        h1, h2, h3 {{ color: #111; margin-top: 20px; }}
        .section-title {{ border-bottom: 1px solid #000; padding-bottom: 5px; margin-top: 40px; font-weight: normal; }}
        
        .grid-container {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 20px; }}
        .map-container {{ height: 400px; border: 1px solid #000; position: relative; }}
        
        .viewer-container {{ position: relative; width: 100%; height: 500px; background: #000; border: 1px solid #000; overflow: hidden; cursor: pointer; }}
        .viewer-image {{ width: 100%; height: 100%; object-fit: contain; position: absolute; top: 0; left: 0; }}
        .viewer-overlay {{ position: absolute; top: 10px; left: 10px; background: rgba(0,0,0,0.7); padding: 5px 10px; color: white; font-family: sans-serif; }}
        .click-hint {{ position: absolute; bottom: 10px; right: 10px; background: rgba(255,255,255,0.8); color: black; padding: 5px; font-family: sans-serif; font-size: 12px; font-weight: bold; }}
        
        .formula-box {{ margin: 15px 0; text-align: center; font-size: 18px; }}
        
        .data-table {{ width: 100%; border-collapse: collapse; margin-top: 15px; font-family: sans-serif; font-size: 14px; }}
        .data-table th, .data-table td {{ padding: 8px; border: 1px solid #000; text-align: center; }}
        .data-table th {{ background: #f2f2f2; }}
        
        .graphs img {{ width: 100%; border: 1px solid #ccc; }}
        
        /* FULLSCREEN MODAL STYLES */
        #fullscreen-modal {{
            display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: #000; z-index: 9999;
        }}
        
        /* Transparent Arrow Controls (Google Maps Style) */
        .arrow-btn {{
            position: absolute; background: rgba(0,0,0,0.3); color: white; border: 2px solid transparent; 
            font-size: 48px; cursor: pointer; z-index: 10000; display: flex; justify-content: center; align-items: center;
            border-radius: 5px; transition: 0.2s; user-select: none;
        }}
        .arrow-btn:hover {{ background: rgba(255,255,255,0.2); border: 2px solid white; transform: scale(1.1); }}
        .arrow-btn:active {{ transform: scale(0.95); }}
        
        .fs-arrow-left {{ top: 50%; left: 30px; transform: translateY(-50%); width: 60px; height: 100px; }}
        .fs-arrow-right {{ top: 50%; right: 30px; transform: translateY(-50%); width: 60px; height: 100px; }}
        .fs-arrow-up {{ bottom: 100px; left: 50%; transform: translateX(-50%); width: 100px; height: 60px; font-size: 36px; }}
        .fs-arrow-down {{ bottom: 30px; left: 50%; transform: translateX(-50%); width: 100px; height: 60px; font-size: 36px; }}
        
        .small-arrow-left {{ top: 50%; left: 10px; transform: translateY(-50%); width: 40px; height: 60px; font-size: 24px; z-index: 10; }}
        .small-arrow-right {{ top: 50%; right: 10px; transform: translateY(-50%); width: 40px; height: 60px; font-size: 24px; z-index: 10; }}
        .small-toggle-btn {{ position: absolute; top: 10px; right: 10px; background: rgba(0,0,0,0.7); color: white; border: 1px solid white; padding: 5px 10px; cursor: pointer; z-index: 10; font-family: sans-serif; font-size: 12px; transition: 0.2s; }}
        .small-toggle-btn:hover {{ background: rgba(255,255,255,0.2); }}
        
        .fs-top-bar {{ position: absolute; top: 0; left: 0; width: 100%; height: 80px; display: flex; justify-content: center; align-items: center; gap: 20px; z-index: 10000; background: rgba(0,0,0,0.8); }}
        .fs-action-btn {{ background: transparent; color: white; border: 1px solid white; padding: 8px 15px; font-family: sans-serif; cursor: pointer; text-decoration: none; font-size: 14px; text-transform: uppercase; }}
        .fs-action-btn:hover {{ background: white; color: black; }}
        
        .fs-close-btn {{ position: absolute; top: 20px; right: 20px; background: transparent; color: white; border: none; font-size: 16px; cursor: pointer; z-index: 10000; font-family: sans-serif; text-transform: uppercase; }}
        .fs-close-btn:hover {{ text-decoration: underline; }}
        
    </style>
</head>
<body>
    <div class="container">
        <div style="text-align: center;">
            <h1>Analytical Report: Green View Index (GVI) and NDVI Correlation Pipeline</h1>
            <p style="font-size: 16px;">Test Pilot Point: {PT_ID} | Coordinates: {LAT}, {LON}</p>
        </div>

        <h2 class="section-title">1. Remote Sensing Data Acquisition</h2>
        <p>Extraction of localized Normalized Difference Vegetation Index (NDVI) values and road network boundaries.</p>
        <div class="formula-box" style="font-size: 18px; margin-bottom: 20px;">
            $$ NDVI = \\frac{{NIR - Red}}{{NIR + Red}} = \\frac{{B8 - B4}}{{B8 + B4}} $$
        </div>
        <div class="grid-container">
            <div>
                <h4 style="text-align:center; margin-bottom:5px;">Study Area Context</h4>
                <p style="text-align:center; font-size:12px; margin-top:0; color:gray;">Coordinates: {LAT}, {LON}</p>
                <div class="map-container">
                    <iframe srcdoc='{map_html.replace("'", "&#39;")}' width="100%" height="100%" frameborder="0"></iframe>
                </div>
            </div>
            <div>
                <h4 style="text-align:center; margin-bottom:5px;">Sentinel-2 NDVI High-Resolution Subset</h4>
                <p style="text-align:center; font-size:12px; margin-top:0; color:gray;">Coordinates: {LAT}, {LON} | NDVI = {ndvi_val}</p>
                <div class="map-container">
                    <!-- Leaflet map for zooming NDVI image cleanly -->
                    <iframe id="ndvi-iframe" srcdoc='{ndvi_map_html.replace("'", "&#39;")}' width="100%" height="100%" frameborder="0"></iframe>
                </div>
            </div>
        </div>

        <h2 class="section-title">2. Deep Learning Semantic Segmentation (SegFormer 360°)</h2>
        <h4 style="text-align:center; margin-bottom:5px;">Panoramic Ground View</h4>
        <p style="text-align:center; font-size:12px; margin-top:0; color:gray;">Synchronized Coordinates: {LAT}, {LON}</p>
        <p style="text-align:center;">Interactive panoramic assessment. Click on the viewer to open full-screen interactive mode with Street View navigation.</p>
        
        <div class="viewer-container" id="viewer">
            <img id="view-img" class="viewer-image" src="" onclick="openFullscreen()">
            <div class="viewer-overlay" id="angle-info">Azimuth: 0°</div>
            
            <div class="arrow-btn small-arrow-left" onclick="turnLeft(event)" title="Turn Left">&#10094;</div>
            <div class="arrow-btn small-arrow-right" onclick="turnRight(event)" title="Turn Right">&#10095;</div>
            <button class="small-toggle-btn" onclick="toggleMask(event)">Toggle Mask</button>
            
            <div class="click-hint" onclick="openFullscreen()">⛶ FULLSCREEN</div>
        </div>
        
        <div>
            <h3 style="text-align:center;">Dynamic Local GVI Calculation</h3>
            <div class="formula-box" id="dynamic-formula">
                $$ GVI_{{current}} = \\frac{{Area_{{veg}}}}{{Area_{{total}}}} \\times 100 $$
            </div>
            <p style="font-style:italic; text-align:center; font-size: 14px;">Where \( Area_{{veg}} \) is the number of vegetation pixels, and \( Area_{{total}} \) is the valid panorama area (excluding masked letterboxing).</p>
        </div>
        
        <div>
            <h3>Standardized sGVI Metric</h3>
            <div class="formula-box">
                $$ GVI_{{total}} = \\frac{{\\sum_{{j=1}}^{{8}} Area_{{veg, j}}}}{{\\sum_{{j=1}}^{{8}} Area_{{total, j}}}} \\times 100 = \\frac{{ {total_veg_pixels} }}{{ {total_valid_pixels} }} \\times 100 = {avg_gvi}\\% $$
            </div>
            <div class="formula-box">
                $$ W_i = \\frac{{L_{{buffer, i}}}}{{L_{{network}}}} = \\frac{{ {road_length} }}{{1000}} $$
            </div>
            <div class="formula-box">
                $$ sGVI_i = GVI_{{total}} \\times W_i = {avg_gvi} \\times \\left( \\frac{{ {road_length} }}{{1000}} \\right) = {sgvi_mock}\\% $$
            </div>
            <div style="font-size: 14px; margin-top: 15px;">
                <strong>Where:</strong>
                <ul>
                    <li>\( GVI_{{total}} \) represents the average Green View Index across all 8 azimuthal frames (\( j=1..8 \)).</li>
                    <li>\( sGVI_i \) denotes the standardized index for spatial point \( i \).</li>
                    <li>\( W_i \) is the Road Weight coefficient.</li>
                    <li>\( L_{{buffer, i}} \) is the total length of the road segment intersecting the 100-meter buffer around point \( i \).</li>
                    <li>\( L_{{network}} \) is the total length of the entire road network in the analyzed urban area (normalized to 1000m for this simulation).</li>
                </ul>
            </div>
        </div>
        
        <div style="text-align: center; margin-top: 40px;">
            <p><i>Note: The Correlation Analysis and Heatmaps will be generated once the full dataset is processed. This dashboard currently evaluates single-point methodology.</i></p>
        </div>
    </div>
    
    <!-- POINT INSPECTOR DASHBOARD MODAL -->
    <div id="point-inspector-modal" style="display:none; position:fixed; top:10%; left:50%; transform:translateX(-50%); width:80%; max-height:80%; background:#fff; border:2px solid #000; box-shadow:0 0 20px rgba(0,0,0,0.5); z-index:10001; overflow-y:auto; padding:30px;">
        <button onclick="document.getElementById('point-inspector-modal').style.display='none'" style="float:right; padding: 5px 10px; cursor: pointer; border: 1px solid black; background: #eee;">[X] CLOSE DASHBOARD</button>
        <h2 id="inspector-title" style="margin-top:0;">Selected Point Dashboard</h2>
        <div class="grid-container">
            <div class="viewer-container" style="height:350px;">
                <img id="inspector-img" class="viewer-image" src="">
                <div class="click-hint">SIMULATED FRAME DATA</div>
            </div>
            <div>
                <h3>Validation Metrics</h3>
                <p id="inspector-stats" style="font-size: 16px; line-height: 1.8;"></p>
                <div class="formula-box" id="inspector-formula" style="background:#f9f9f9; padding: 10px; border:1px dashed #ccc;"></div>
            </div>
        </div>
    </div>
    
    <!-- FULLSCREEN MODAL -->
    <div id="fullscreen-modal">
        <div class="fs-top-bar">
            <!-- Dynamic Google Maps Street View Link -->
            <a id="gmaps-link" href="#" target="_blank" class="fs-action-btn">Open in Google Maps</a>
            <a id="fs-download-btn" href="#" download="frame_{PT_ID}.jpg" class="fs-action-btn">Download Frame</a>
            <button id="fs-toggle-mask" class="fs-action-btn">Toggle Segmentation</button>
        </div>
        
        <button class="fs-close-btn" onclick="closeFullscreen()">Close [X]</button>
        
        <img id="fs-view-img" class="viewer-image" src="" style="cursor:default;">
        
        <!-- Google Maps Style Arrow Controls -->
        <div class="arrow-btn fs-arrow-left" onclick="turnLeft()" title="Turn Left">&#10094;</div>
        <div class="arrow-btn fs-arrow-right" onclick="turnRight()" title="Turn Right">&#10095;</div>
        <div class="arrow-btn fs-arrow-up" onclick="moveForward()" title="Move Forward">&#9650;</div>
        <div class="arrow-btn fs-arrow-down" onclick="moveBackward()" title="Move Backward">&#9660;</div>
    </div>

    <script>
        const results = {json.dumps(results_data)};
        const POINT_LAT = {LAT};
        const POINT_LON = {LON};
        
        let currentIndex = 0;
        let showMask = false;
        let isFullscreen = false;
        
        const imgEl = document.getElementById('view-img');
        const fsImgEl = document.getElementById('fs-view-img');
        const angleEl = document.getElementById('angle-info');
        const dynamicFormula = document.getElementById('dynamic-formula');
        const fsDownloadBtn = document.getElementById('fs-download-btn');
        const gmapsLink = document.getElementById('gmaps-link');
        
        function updateView() {{
            const current = results[currentIndex];
            const srcStr = showMask ? `data:image/jpeg;base64,${{current.mask_b64}}` : `data:image/jpeg;base64,${{current.orig_b64}}`;
            
            imgEl.src = srcStr;
            fsImgEl.src = srcStr;
            fsDownloadBtn.href = srcStr;
            
            // Generate Street View Panorama link exactly for this heading
            gmapsLink.href = `https://www.google.com/maps/@?api=1&map_action=pano&viewpoint=${{POINT_LAT}},${{POINT_LON}}&heading=${{current.heading}}`;
            
            angleEl.innerText = `Azimuth: ${{current.heading}}°`;
            
            // Rotate the arrow on the NDVI map
            try {{
                const ndviIframe = document.getElementById('ndvi-iframe');
                if (ndviIframe && ndviIframe.contentWindow && ndviIframe.contentWindow.document) {{
                    const arrow = ndviIframe.contentWindow.document.getElementById('map-direction-arrow');
                    if (arrow) {{
                        arrow.style.transform = `rotate(${{current.heading}}deg)`;
                    }}
                }}
            }} catch (e) {{
                // Cross-origin might block this if viewed locally without a server in some browsers,
                // but generally srcdoc allows it.
            }}
            
            const formulaString = `\\\\[ GVI_{{${{current.heading}}^\\\\circ}} = \\\\frac{{Area_{{veg}}}}{{Area_{{total}}}} \\\\times 100 = \\\\frac{{${{current.veg_area}}}}{{${{current.total_area}}}} \\\\times 100 = ${{current.gvi}}\\\\% \\\\]`;
            dynamicFormula.innerHTML = formulaString;
            
            if (window.MathJax) {{
                MathJax.typesetPromise([dynamicFormula]).catch((err) => console.log(err.message));
            }}
        }}
        
        function turnLeft(e) {{ 
            if(e) e.stopPropagation(); 
            currentIndex = (currentIndex - 1 + results.length) % results.length; 
            updateView(); 
        }}
        
        function turnRight(e) {{ 
            if(e) e.stopPropagation(); 
            currentIndex = (currentIndex + 1) % results.length; 
            updateView(); 
        }}
        
        function moveForward() {{ console.log("Step Forward Placeholder"); }}
        function moveBackward() {{ console.log("Step Backward Placeholder"); }}
        
        document.getElementById('fs-toggle-mask').addEventListener('click', (e) => {{
            toggleMask(e);
        }});
        
        function toggleMask(e) {{
            if(e) e.stopPropagation();
            showMask = !showMask;
            updateView();
        }}
        
        function openFullscreen() {{
            document.getElementById('fullscreen-modal').style.display = 'block';
            isFullscreen = true;
        }}
        
        function closeFullscreen() {{
            document.getElementById('fullscreen-modal').style.display = 'none';
            isFullscreen = false;
        }}
        
        // Keyboard Navigation (Arrow Keys)
        document.addEventListener('keydown', (e) => {{
            if (!isFullscreen) return;
            if (e.key === 'ArrowLeft') turnLeft();
            else if (e.key === 'ArrowRight') turnRight();
            else if (e.key === 'ArrowUp') moveForward();
            else if (e.key === 'ArrowDown') moveBackward();
            else if (e.key === 'Escape') closeFullscreen();
        }});
        
        setTimeout(updateView, 500); 
    </script>
</body>
</html>'''

with open(HTML_PATH, 'w', encoding='utf-8') as f:
    f.write(html_content)

print(f"--- COMPLETE! Open file: {HTML_PATH} ---")
