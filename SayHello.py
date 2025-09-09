# app.py — Taiwan bus nearby checker (Streamlit)
#
# Requirements (install locally):
#   pip install streamlit requests streamlit-geolocation pydeck
#
# How to run:
#   1) Get a TDX (MOTC) Client ID and Client Secret from https://tdx.transportdata.tw/
#   2) Set env vars (recommended):
#        export TDX_CLIENT_ID="your_id"
#        export TDX_CLIENT_SECRET="your_secret"
#      or enter them in the sidebar fields when launching the app.
#   3) streamlit run app.py
#
# What it does:
#   • Gets your browser location (with permission)
#   • Queries nearby bus stops from TDX
#   • Shows real‑time ETAs for those stops
#   • (Optional) Shows live bus vehicles within a radius
#
# Notes:
#   • Your location is only used inside your browser session.
#   • If you’re on a corporate/VPN network, geolocation might be blocked.

from __future__ import annotations
import os
import time
import math
import urllib.parse
from typing import Dict, List, Any, Optional

import requests
import pandas as pd
import streamlit as st
import pydeck as pdk
from streamlit_geolocation import streamlit_geolocation

# ---------------------------
# Helpers
# ---------------------------

def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return distance in meters between (lat1, lon1) and (lat2, lon2)."""
    R = 6371000.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda/2) ** 2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))

# Basic mapping of TDX City IDs commonly used for city buses
TDX_CITY_IDS = [
    "Keelung", "Taipei", "NewTaipei", "Taoyuan", "Hsinchu", "HsinchuCounty",
    "MiaoliCounty", "Taichung", "ChanghuaCounty", "NantouCounty", "YunlinCounty",
    "Chiayi", "ChiayiCounty", "Tainan", "Kaohsiung", "PingtungCounty",
    "YilanCounty", "HualienCounty", "TaitungCounty", "PenghuCounty", "KinmenCounty"
]

TOKEN_URL = "https://tdx.transportdata.tw/auth/realms/TDXConnect/protocol/openid-connect/token"
API_BASE = "https://tdx.transportdata.tw/api/basic/v2"

@st.cache_data(show_spinner=False)
def get_access_token(client_id: str, client_secret: str) -> str:
    """Fetch OAuth2 access token from TDX using client_credentials."""
    data = {
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret,
    }
    headers = {"content-type": "application/x-www-form-urlencoded"}
    r = requests.post(TOKEN_URL, data=data, headers=headers, timeout=20)
    r.raise_for_status()
    return r.json()["access_token"]

class TDX:
    def __init__(self, token: str):
        self.token = token
        self.session = requests.Session()
        self.session.headers.update({"Authorization": f"Bearer {token}", "Accept": "application/json"})

    def get(self, url: str, **kwargs) -> Any:
        r = self.session.get(url, timeout=20, **kwargs)
        r.raise_for_status()
        return r.json()

    # Nearby stops using $spatialFilter
    def nearby_stops(self, city: str, lat: float, lon: float, radius_m: int = 300) -> List[Dict[str, Any]]:
        spatial = f"$spatialFilter=nearby(StopPosition,{lat},{lon},{radius_m})"
        url = f"{API_BASE}/Bus/Stop/City/{urllib.parse.quote(city)}?{spatial}&$format=JSON"
        return self.get(url)

    # ETA for a set of StopUIDs
    def eta_for_stops(self, city: str, stop_uids: List[str]) -> List[Dict[str, Any]]:
        if not stop_uids:
            return []
        # Build OData filter: StopUID eq 'A' or StopUID eq 'B' ...
        ors = " or ".join([f"StopUID eq '{uid}'" for uid in stop_uids])
        filt = f"$filter={urllib.parse.quote(ors)}"
        url = f"{API_BASE}/Bus/EstimatedTimeOfArrival/City/{urllib.parse.quote(city)}?{filt}&$orderby=StopUID,StopSequence&$format=JSON"
        return self.get(url)

    # Live vehicle positions (can be large). We filter by bounding circle client-side.
    def realtime_by_city(self, city: str) -> List[Dict[str, Any]]:
        url = f"{API_BASE}/Bus/RealTimeByFrequency/City/{urllib.parse.quote(city)}?$format=JSON"
        return self.get(url)

# ---------------------------
# UI
# ---------------------------

st.set_page_config(page_title="Taiwan Bus Nearby (TDX)", page_icon="🚌", layout="wide")

st.title("🚌 Taiwan Bus Nearby")
st.caption("Find buses near you in Taiwan using TDX real‑time data.")

with st.sidebar:
    st.header("Settings")
    default_id = os.environ.get("TDX_CLIENT_ID", "")
    default_secret = os.environ.get("TDX_CLIENT_SECRET", "")
    cid = st.text_input("TDX Client ID", value=default_id, type="default")
    csecret = st.text_input("TDX Client Secret", value=default_secret, type="password")
    city = st.selectbox("City (TDX ID)", options=TDX_CITY_IDS, index=TDX_CITY_IDS.index("Taipei"))
    radius_m = st.slider("Search radius (meters)", min_value=50, max_value=1500, value=300, step=50)
    eta_soon_min = st.slider("Consider 'near' if arriving within (minutes)", min_value=1, max_value=20, value=6)
    refresh_sec = st.slider("Auto-refresh (seconds)", min_value=0, max_value=60, value=15, help="0 = no auto refresh")
    show_live = st.checkbox("Show live vehicles layer (experimental)", value=False)

if not cid or not csecret:
    st.info("Enter your TDX Client ID/Secret in the sidebar to start.")
    st.stop()

# Ask for geolocation (user clicks the button)
loc = streamlit_geolocation()
if not isinstance(loc, dict) or "latitude" not in loc or loc.get("latitude") is None:
    st.warning("Click the geolocation button above to share your location.")
    st.stop()

user_lat = float(loc["latitude"])  # type: ignore
user_lon = float(loc["longitude"])  # type: ignore
st.success(f"Your location: lat {user_lat:.5f}, lon {user_lon:.5f}")

# Token and client
try:
    token = get_access_token(cid, csecret)
except Exception as e:
    st.error(f"Failed to get TDX access token: {e}")
    st.stop()

tdx = TDX(token)

# Fetch nearby stops
with st.spinner("Finding nearby stops…"):
    stops = tdx.nearby_stops(city, user_lat, user_lon, radius_m)

if not stops:
    st.info("No stops found within the selected radius. Try a larger radius or switch city.")
    st.stop()

stops_df_rows = []
for s in stops:
    pos = s.get("StopPosition", {})
    lat, lon = pos.get("PositionLat"), pos.get("PositionLon")
    stops_df_rows.append({
        "StopUID": s.get("StopUID"),
        "StopID": s.get("StopID"),
        "StopName": s.get("StopName", {}).get("Zh_tw") or s.get("StopName", {}).get("En"),
        "Lat": lat,
        "Lon": lon,
        "Distance_m": round(haversine(user_lat, user_lon, lat, lon), 1) if lat and lon else None,
    })

stops_df = pd.DataFrame(stops_df_rows).sort_values("Distance_m")

# Get ETAs for these stops
etas = tdx.eta_for_stops(city, stops_df["StopUID"].dropna().astype(str).tolist())

eta_rows = []
for e in etas:
    # EstimateTime: seconds to arrival (may be missing)
    est_sec = e.get("EstimateTime")
    stop_uid = e.get("StopUID")
    route = e.get("RouteName", {}).get("Zh_tw") or e.get("RouteName", {}).get("En")
    direction = e.get("Direction")  # 0=去程, 1=返程
    stop_seq = e.get("StopSequence")
    is_last = e.get("IsLastBus")
    status = e.get("StopStatus")  # 0=正常, others per spec
    eta_rows.append({
        "StopUID": stop_uid,
        "Route": route,
        "Direction": direction,
        "StopSequence": stop_seq,
        "ETA_min": None if est_sec is None else round(est_sec/60, 1),
        "IsLastBus": is_last,
        "StopStatus": status,
    })

eta_df = pd.DataFrame(eta_rows)

# Merge ETA with stops for display
merged = stops_df.merge(eta_df, on="StopUID", how="left")
merged = merged.sort_values(["Distance_m", "Route", "StopSequence"])  # nearest first

# Determine "any bus near me" based on ETA threshold
near_mask = (merged["ETA_min"].notna()) & (merged["ETA_min"] <= eta_soon_min)
any_near = bool(near_mask.any())

st.subheader("Result")
if any_near:
    st.success(f"✅ Yes — at least one bus is arriving within {eta_soon_min} minutes.")
else:
    st.info(f"ℹ️ No bus ETA within {eta_soon_min} minutes at the nearby stops.")

# Table
st.subheader("Nearby stops & ETAs")
st.dataframe(
    merged[["StopName", "Distance_m", "Route", "Direction", "StopSequence", "ETA_min", "IsLastBus", "StopStatus"]]
)

# Map visualization with pydeck
st.subheader("Map")
stop_layer = pdk.Layer(
    "ScatterplotLayer",
    data=stops_df,
    get_position='[Lon, Lat]',
    get_radius=20,
    pickable=True,
)
user_layer = pdk.Layer(
    "ScatterplotLayer",
    data=pd.DataFrame({"Lat": [user_lat], "Lon": [user_lon]}),
    get_position='[Lon, Lat]',
    get_radius=60,
    pickable=False,
)

layers = [stop_layer, user_layer]

# Optional: live vehicles around user (rough filter by distance)
if show_live:
    with st.spinner("Loading live vehicle positions…"):
        try:
            vehicles = tdx.realtime_by_city(city)
        except Exception as e:
            st.error(f"Failed to get live vehicle positions: {e}")
            vehicles = []
    v_rows = []
    for v in vehicles:
        bus_pos = v.get("BusPosition") or {}
        lat = bus_pos.get("PositionLat")
        lon = bus_pos.get("PositionLon")
        if lat is None or lon is None:
            continue
        dist = haversine(user_lat, user_lon, lat, lon)
        if dist <= max(1000, radius_m):  # show within 1km or chosen radius
            v_rows.append({
                "Lat": lat,
                "Lon": lon,
                "Distance_m": round(dist, 1),
                "Route": (v.get("RouteName") or {}).get("Zh_tw") or (v.get("RouteName") or {}).get("En"),
                "Plate": v.get("PlateNumb"),
            })
    if v_rows:
        v_df = pd.DataFrame(v_rows)
        st.caption(f"Live vehicles within ~{max(1000, radius_m)} m: {len(v_df)}")
        vehicle_layer = pdk.Layer(
            "ScatterplotLayer",
            data=v_df,
            get_position='[Lon, Lat]',
            get_radius=40,
            pickable=True,
        )
        layers.append(vehicle_layer)
        with st.expander("See live vehicle list"):
            st.dataframe(v_df.sort_values("Distance_m"))
    else:
        st.caption("No live vehicles within the radius right now.")

view_state = pdk.ViewState(latitude=user_lat, longitude=user_lon, zoom=15)
st.pydeck_chart(pdk.Deck(map_style=None, initial_view_state=view_state, layers=layers, tooltip={"text": "{Route}\n{Plate}\n{Distance_m} m"}))

# Auto-refresh
if refresh_sec > 0:
    st.caption(f"Auto‑refreshing every {refresh_sec}s… (disable in sidebar)")
    time.sleep(refresh_sec)
    st.rerun()
