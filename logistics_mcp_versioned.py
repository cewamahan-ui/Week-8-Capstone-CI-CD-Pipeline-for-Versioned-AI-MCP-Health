"""AfyaPlus logistics MCP server - VERSIONED for Week 8 (Deliverable 1).

Same tools and honest docstrings as the Week 6/7 MCP server; the
Week 8 additions are the version banner and a manifest the health
probe reads before any deploy:

  - MCP_SERVER_VERSION must match config/triage.yaml mcp.server_version
    and versions.MCP_SERVER_VERSION.
  - RELEASE_TAG must match the git tag and the image tag, proving the
    "one tag across git, image, prompt bundle and MCP" alignment.

Tools (unchanged from Week 6/7):
  - find_clinic_by_county(county, require_service=None)
  - plan_delivery_route(origin, destination_county, vehicle="van")
Resource:
  - clinics://catalog

Run:  python logistics_mcp_versioned.py   # streamable-http on :8765
"""

from __future__ import annotations

import json
import logging
import math
import os
from pathlib import Path
from typing import Optional

import versions

MCP_SERVER_VERSION = versions.MCP_SERVER_VERSION
RELEASE_TAG = versions.RELEASE_TAG
PROMPT_BUNDLE_VERSION = versions.DEFAULT_PROMPT_VERSION

DATA_PATH = Path(__file__).resolve().parent / "clinics.json"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("afyaplus.mcp.versioned")


def _load_clinics() -> list[dict]:
    with DATA_PATH.open("r", encoding="utf-8") as fh:
        return json.load(fh)


_KNOWN_COUNTIES: set[str] = {c["county"].lower() for c in _load_clinics()}

_KNOWN_ORIGINS: dict[str, tuple[float, float]] = {
    "nairobi": (-1.2921, 36.8219),
    "nairobi depot": (-1.2921, 36.8219),
    "mombasa": (-4.0435, 39.6682),
    "kisumu": (-0.0917, 34.7680),
}

_SPEED_KMH = {"van": 60, "ambulance": 80, "truck": 50}


def manifest() -> dict:
    """Machine-readable identity the CI health probe asserts on."""
    return {
        "server": "afyaplus-logistics-mcp",
        "server_version": MCP_SERVER_VERSION,
        "release_tag": RELEASE_TAG,
        "prompt_bundle_version": PROMPT_BUNDLE_VERSION,
        "tools": sorted(["find_clinic_by_county", "plan_delivery_route"]),
        "resources": ["clinics://catalog"],
        "transport": os.getenv("MCP_TRANSPORT", "streamable-http"),
    }


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    rlat1, rlat2 = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(rlat1) * math.cos(rlat2) * math.sin(dlon / 2) ** 2
    c = 2 * math.asin(math.sqrt(a))
    return R * c


def find_clinic_by_county(
    county: str,
    require_service: Optional[str] = None,
    trace_id: str = "-",
) -> dict:
    """Find clinics in a county, optionally filtered by service.

    county is case-insensitive. require_service is optional (e.g.
    "obstetric"). Returns {count, clinics} on success or {error,
    known_counties} on bad input - errors as data, not raises.
    """
    if not county or not str(county).strip():
        return {"error": "county is required", "known_counties": sorted(_KNOWN_COUNTIES)}
    county_key = str(county).strip().lower()
    if county_key not in _KNOWN_COUNTIES:
        return {
            "error": f"unknown county '{county}'",
            "known_counties": sorted(_KNOWN_COUNTIES),
        }
    matches = [c for c in _load_clinics() if c["county"].lower() == county_key]
    if require_service:
        service_key = str(require_service).strip().lower()
        matches = [c for c in matches if service_key in {s.lower() for s in c["services"]}]
    log.info("find_clinic_by_county ok trace_id=%s county=%s", trace_id, county_key)
    return {"county": county_key, "count": len(matches), "clinics": matches}


def plan_delivery_route(
    origin: str,
    destination_county: str,
    vehicle: str = "van",
    trace_id: str = "-",
) -> dict:
    """Plan a delivery route from a named origin to all clinics in a county.

    Nearest-neighbour greedy heuristic - decision support, NOT optimal
    routing. vehicle: van (default), ambulance, truck.
    """
    if not origin or not str(origin).strip():
        return {"error": "origin is required", "known_origins": sorted(_KNOWN_ORIGINS)}
    if not destination_county or not str(destination_county).strip():
        return {"error": "destination_county is required", "known_counties": sorted(_KNOWN_COUNTIES)}
    origin_key = str(origin).strip().lower()
    dest_key = str(destination_county).strip().lower()
    vehicle_key = (vehicle or "van").strip().lower()
    if origin_key not in _KNOWN_ORIGINS:
        return {"error": f"unknown origin '{origin}'", "known_origins": sorted(_KNOWN_ORIGINS)}
    if dest_key not in _KNOWN_COUNTIES:
        return {
            "error": f"unknown destination county '{destination_county}'",
            "known_counties": sorted(_KNOWN_COUNTIES),
        }
    if vehicle_key not in _SPEED_KMH:
        return {"error": f"unknown vehicle '{vehicle}'", "known_vehicles": sorted(_SPEED_KMH)}

    pool = [c for c in _load_clinics() if c["county"].lower() == dest_key]
    speed = _SPEED_KMH[vehicle_key]
    ox, oy = _KNOWN_ORIGINS[origin_key]
    stops: list[dict] = []
    cur_lat, cur_lon = ox, oy
    total_km = 0.0
    while pool:
        pool.sort(key=lambda c: _haversine_km(cur_lat, cur_lon, c["lat"], c["lon"]))
        nxt = pool.pop(0)
        leg = _haversine_km(cur_lat, cur_lon, nxt["lat"], nxt["lon"])
        total_km += leg
        stops.append({"clinic_id": nxt["id"], "name": nxt["name"], "leg_km": round(leg, 1)})
        cur_lat, cur_lon = nxt["lat"], nxt["lon"]
    return {
        "origin": origin_key,
        "destination_county": dest_key,
        "vehicle": vehicle_key,
        "heuristic": "nearest-neighbour greedy, not optimal",
        "stops": stops,
        "total_km": round(total_km, 1),
        "estimated_hours": round(total_km / speed, 2) if speed else 0.0,
    }


def clinics_catalog() -> str:
    """Full clinic list as JSON. Read-only context for the agent."""
    return json.dumps(_load_clinics(), indent=2)


def build_mcp_server():
    """Register tools/resources with FastMCP (network transport)."""
    from mcp.server.fastmcp import FastMCP

    mcp = FastMCP(
        name=f"afyaplus-logistics-mcp@{MCP_SERVER_VERSION}",
        instructions=(
            f"AfyaPlus logistics MCP v{MCP_SERVER_VERSION} (release {RELEASE_TAG}). "
            "find_clinic_by_county looks up clinics, plan_delivery_route computes a "
            "greedy non-optimal route, clinics://catalog lists everything."
        ),
    )

    @mcp.tool(
        name="find_clinic_by_county",
        description=(
            "Find clinics in a Kenyan county, optionally filtered by service. "
            "Returns {count, clinics} or {error, known_counties} on bad input."
        ),
    )
    def t1(county: str, require_service: Optional[str] = None) -> dict:
        return find_clinic_by_county(county, require_service, os.environ.get("TRACE_ID", "-"))

    @mcp.tool(
        name="plan_delivery_route",
        description=(
            "Route from a named origin to all clinics in a county. Greedy "
            "nearest-neighbour, NOT optimal. vehicle: van/ambulance/truck."
        ),
    )
    def t2(origin: str, destination_county: str, vehicle: str = "van") -> dict:
        return plan_delivery_route(
            origin, destination_county, vehicle, os.environ.get("TRACE_ID", "-")
        )

    @mcp.resource(
        uri="clinics://catalog",
        name="clinics_catalog",
        description="Full AfyaPlus clinic list as JSON (read-only).",
        mime_type="application/json",
    )
    def r1() -> str:
        return clinics_catalog()

    return mcp


def main() -> None:
    port = int(os.getenv("MCP_PORT", "8765"))
    log.info("starting afyaplus-logistics-mcp v%s (%s)", MCP_SERVER_VERSION, RELEASE_TAG)
    mcp = build_mcp_server()
    mcp.settings.port = port
    mcp.run(transport=os.getenv("MCP_TRANSPORT", "streamable-http"))


if __name__ == "__main__":
    main()
