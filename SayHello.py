# app.py — Streamlit app to show a map and moving cars on roads (simulated with OpenStreetMap)
#
# Why simulated? Live per-car tracking data is generally private/unavailable. This app pulls nearby
# road geometry from OpenStreetMap (via Overpass API) and animates virtual “cars” moving along those roads.
#
# Requirements:
#   pip install streamlit requests pydeck streamlit-geolocation numpy
#
# Run:
#   streamlit run app.py
#
# Tips:
#   • Click the geolocation button to center the map.
#   • Use the sidebar to choose radius, number of cars, and refresh rate.
#   • (Optional) If you have a Mapbox token, set MAPBOX_API_KEY env var for nicer basemaps.

from __future__ import annotations
import math
import time
import random
from typing import List, Dict, Any, Tuple

import requests
import numpy as np
import pandas as pd
import streamlit as st
import pydeck as pdk
from streamlit_geolocation import streamlit_geolocation

# ---------------------------
# Geometry helpers
# ---------------------------

def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371000.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda/2) ** 2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))

def polyline_length_m(coords: List[Tuple[float, float]]) -> float:
    return sum(haversine(coords[i][1], coords[i][0], coords[i+1][1], coords[i+1][0]) for i in range(len(coords)-1))

def cumulative_distances(coords: List[Tuple[float, float]]) -> List[float]:
    dists = [0.0]
    for i in range(len(coords)-1):
        dists.append(dists[-1] + haversine(coords[i][1], coords[i][0], coords[i+1][1], coords[i+1][0]))
    return dists

def interpolate_along(coords: List[Tuple[float, float]], cumd: List[float], s: float) -> Tuple[float, float]:
    """Given polyline coords [(lon,lat)...], cumulative distances 'cumd', return point at distance s."""
    if s <= 0:
        return coords[0][0], coords[0][1]
    if s >= cumd[-1]:
        return coords[-1][0], coords[-1][1]
    # find segment
    for i in range(len(cumd)-1):
        if cumd[i] <= s <= cumd[i+1]:
            t = (s - cumd[i]) / (cumd[i+1] - cumd[i] + 1e-9)
            lon = coords[i][0] + t * (coords[i+1][0] - coords[i][0])
            lat = coords[i][1] + t * (coords[i+1][1] - coords[i][1])
            return lon, lat
    return coords[-1][0], coords[-1][1]

# ---------------------------
# Overpass (OSM) fetch
# ---------------------------

def fetch_roads(lat: float, lon: float, radius_m: int = 1000) -> List[Dict[str, Any]]:
    """Fetch road polylines around a point using Overpass API."""
    # Highways to include (exclude footways/paths by default)
    hw = ["motorway","trunk","primary","secondary","tertiary","unclassified","residential","service"]
    hw_q = "|".join(hw)
    query = f"""
    [out:json][timeout:25];
    way["highway"~"{hw_q}"](around:{radius_m},{lat},{lon});
    (._;>;); out geom;
    """
    r = requests.post("https://overpass-api.de/api/interpreter", data=query, timeout=30)
    r.raise_for_status()
    data = r.json()
    # Build ways with geometry
    roads = []
    for el in data.get("elements", []):
        if el.get("type") == "way" and "geometry" in el:
            coords = [(pt["lon"], pt["lat"]) for pt in el["geometry"]]
            if len(coords) >= 2:
                L = polyline_length_m(coords)
                if L >= 60:  # ignore tiny service stubs
                    roads.append({
                        "id": el.get("id"),
                        "name": (el.get("tags") or {}).get("name", "(unnamed)"),
                        "highway": (el.get("tags") or {}).get("highway", ""),
                        "coords": coords,
                        "length_m": L,
                    })
    return roads

# ---------------------------
# Simulation model
# ---------------------------

def seed_cars(roads: List[Dict[str, Any]], n: int, speed_kmh_range=(20, 70)) -> List[Dict[str, Any]]:
    """Create n cars assigned to random roads with random speeds and start offsets."""
    if not roads:
        return []
    cars = []
    for i in range(n):
        road = random.choice(roads)
        # Precompute cumulative distances for the chosen road
        cumd = cumulative_distances(road["coords"])  # meters
        total = cumd[-1]
        speed = random.uniform(*speed_kmh_range) * 1000/3600  # m/s
        start_offset = random.uniform(0, total)  # position along the road at t=0
        direction = random.choice([1, -1])
        cars.append({
            "car_id": f"car_{i+1}",
            "road_id": road["id"],
            "road_name": road["name"],
            "coords": road["coords"],
            "cumd": cumd,
            "total": total,
            "speed_mps": speed,
            "pos0": start_offset,
            "dir": direction,
        })
    return cars

def advance_car(car: Dict[str, Any], dt: float) -> Tuple[float, float]:
    """Compute current lon,lat after dt seconds since t0 (looping at ends)."""
    s = (car["pos0"] + car["dir"] * car["speed_mps"] * dt) % car["total"]
    lon, lat = interpolate_along(car["coords"], car["cumd"], s)
    return lon, lat

# ---------------------------
# UI
# ---------------------------

st.set_page_config(page_title="Road Car Movement (OSM simulated)", page_icon="🚗", layout="wide")

st.title("🚗 Live-looking Car Movement on Roads (Simulated)")
st.caption("Animates virtual cars along nearby OpenStreetMap roads. Great for demos and dashboards.")

with st.sidebar:
    st.header("Controls")
    radius_m = st.slider("Road search radius (m)", 200, 3000, 1200, step=100)
    n_cars = st.slider("Number of cars", 5, 200, 50, step=5)
    speed_min = st.slider("Min speed (km/h)", 5, 80, 20)
    speed_max = st.slider("Max speed (km/h)", 10, 120, 70)
    refresh_sec = st.slider("Refresh interval (s)", 0, 5, 1)
    show_roads = st.checkbox("Show road paths", True)

loc = streamlit_geolocation()
if not isinstance(loc, dict) or loc.get("latitude") is None:
    st.info("Click the geolocation button above to share your location.")
    st.stop()

lat0 = float(loc["latitude"])  # type: ignore
lon0 = float(loc["longitude"])  # type: ignore
st.success(f"Map centered at lat {lat0:.5f}, lon {lon0:.5f}")

# Cache roads by center+radius to avoid hammering Overpass
@st.cache_data(show_spinner=False)
def load_roads_cached(lat: float, lon: float, radius: int):
    roads = fetch_roads(lat, lon, radius)
    # Build DataFrame for PathLayer
    df_roads = pd.DataFrame({
        "id": [r["id"] for r in roads],
        "name": [r["name"] for r in roads],
        "highway": [r["highway"] for r in roads],
        "path": [r["coords"] for r in roads],
        "length_m": [r["length_m"] for r in roads],
    })
    return roads, df_roads

with st.spinner("Loading nearby roads from OpenStreetMap…"):
    roads, df_roads = load_roads_cached(lat0, lon0, radius_m)

if not roads:
    st.warning("No roads found. Try increasing radius.")
    st.stop()

# Initialize cars once per parameter set
if "cars" not in st.session_state or st.session_state.get("cars_params") != (len(roads), n_cars, speed_min, speed_max):
    st.session_state["cars"] = seed_cars(roads, n_cars, (speed_min, speed_max))
    st.session_state["t0"] = time.time()
    st.session_state["cars_params"] = (len(roads), n_cars, speed_min, speed_max)

cars = st.session_state["cars"]
t0 = st.session_state["t0"]

# Compute car positions based on elapsed time
now = time.time()
DT = now - t0
car_positions = []
for c in cars:
    lon, lat = advance_car(c, DT)
    car_positions.append({
        "car_id": c["car_id"],
        "road": c["road_name"],
        "lon": lon,
        "lat": lat,
        "speed_kmh": round(c["speed_mps"] * 3.6, 1),
    })

cars_df = pd.DataFrame(car_positions)

# Layers
layers = []
if show_roads:
    layers.append(pdk.Layer(
        "PathLayer",
        data=df_roads,
        get_path="path",
        width_scale=1,
        width_min_pixels=1,
        get_width=2,
        pickable=True,
    ))

layers.append(pdk.Layer(
    "ScatterplotLayer",
    data=cars_df,
    get_position='[lon, lat]',
    get_radius=25,
    pickable=True,
))

view = pdk.ViewState(latitude=lat0, longitude=lon0, zoom=14)
st.pydeck_chart(pdk.Deck(map_style=None, initial_view_state=view, layers=layers, tooltip={"text": "{car_id}\n{road}\n{speed_kmh} km/h"}))

with st.expander("Car list"):
    st.dataframe(cars_df)

if refresh_sec > 0:
    time.sleep(refresh_sec)
    st.rerun()
