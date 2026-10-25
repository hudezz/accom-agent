"""Plain Python tools: web search, filtering, geocoding and saving."""

import csv
import logging
import math
import os
from functools import cache
from pathlib import Path

from geopy.exc import GeopyError
from geopy.extra.rate_limiter import RateLimiter
from geopy.geocoders import GoogleV3, Nominatim

from schemas import Listing, ScoredListing

log = logging.getLogger(__name__)

LRT_STATIONS_PATH = Path(__file__).resolve().parent / "data" / "lrt_stations.csv"
EARTH_RADIUS_KM = 6371.0


# --- Search ---------------------------------------------------------------


def web_search(query: str) -> list[dict]:
    """Search the web for accommodation listings.

    Args:
        query: Free-text search query, e.g. "room for rent near Universiti Malaya".

    Returns:
        A list of results, each a dict with keys "title", "url" and "snippet".
    """
    max_results = int(os.getenv("MAX_SEARCH_RESULTS", "10"))
    log.info("Searching: %r", query)

    # Tavily when a key is configured, otherwise free DuckDuckGo search.
    if api_key := os.getenv("TAVILY_API_KEY"):
        from langchain_tavily import TavilySearch

        response = TavilySearch(max_results=max_results, tavily_api_key=api_key).invoke({"query": query})
        # Tavily returns an error string instead of raising in some cases.
        raw = response.get("results", []) if isinstance(response, dict) else []
        results = [{"title": r.get("title", ""), "url": r.get("url", ""), "snippet": r.get("content", "")} for r in raw]
    else:
        from ddgs import DDGS
        from ddgs.exceptions import DDGSException

        try:
            raw = DDGS().text(query, region="my-en", max_results=max_results)
        except DDGSException:
            # No results or rate limited: let the agent try another query.
            raw = []
        results = [{"title": r.get("title", ""), "url": r.get("href", ""), "snippet": r.get("body", "")} for r in raw]

    log.info("Got %d results", len(results))
    return results


# --- Filtering ------------------------------------------------------------


def within_budget(listings: list[Listing], budget_rm: int) -> list[Listing]:
    """Keep listings priced at or below budget_rm.

    Listings with an unknown price are kept: many ads say "PM for price",
    so the agency team can follow up on them instead of losing them.
    """
    return [l for l in listings if l.price_rm is None or l.price_rm <= budget_rm]


def matches_gender(listings: list[Listing], gender: str) -> list[Listing]:
    """Drop listings whose gender rule excludes the client ("male" or "female")."""
    excluded = "female_only" if gender == "male" else "male_only"
    return [l for l in listings if l.gender_rule != excluded]


def dedupe(listings: list[Listing]) -> list[Listing]:
    """Remove duplicates, keeping the first occurrence.

    Two listings are duplicates if they share a link, or if they have the same
    building name, price and room type (the same ad reposted on another site).
    """
    seen_links: set[str] = set()
    seen_keys: set[tuple] = set()
    unique: list[Listing] = []

    for listing in listings:
        # Normalise so "https://x.com/a/" and "http://x.com/a" match.
        link = listing.link.strip().lower().rstrip("/").removeprefix("https://").removeprefix("http://")
        key = (listing.building_name.strip().lower(), listing.price_rm, (listing.room_type or "").strip().lower())
        if link in seen_links or key in seen_keys:
            continue
        seen_links.add(link)
        seen_keys.add(key)
        unique.append(listing)

    return unique


# --- Geo ------------------------------------------------------------------


@cache
def _geocoder() -> RateLimiter:
    """Google Maps when a key is set, otherwise free OpenStreetMap (max 1 request/second)."""
    if api_key := os.getenv("GOOGLE_MAPS_API_KEY"):
        return RateLimiter(GoogleV3(api_key=api_key).geocode, min_delay_seconds=0)
    return RateLimiter(Nominatim(user_agent="accom-agent").geocode, min_delay_seconds=1)


def geocode(address: str) -> tuple[float, float] | None:
    """Convert a Malaysian address or building name to (lat, lng), or None if not found."""
    query = address if "malaysia" in address.lower() else f"{address}, Malaysia"
    try:
        location = _geocoder()(query, timeout=10)
    except GeopyError:
        # Network errors, rate limits, bad keys: treat as "not found".
        location = None
    if location is None:
        log.info("Could not geocode %r", address)
        return None
    return location.latitude, location.longitude


@cache
def _load_stations() -> list[tuple[str, float, float]]:
    """Read the station CSV once as (name, lat, lng) tuples."""
    with open(LRT_STATIONS_PATH, newline="", encoding="utf-8") as f:
        return [(row["station_name"], float(row["lat"]), float(row["lng"])) for row in csv.DictReader(f)]


def nearest_station(lat: float, lng: float) -> tuple[str, float]:
    """Return (station_name, distance_km) of the closest LRT station."""
    name, s_lat, s_lng = min(_load_stations(), key=lambda s: haversine_km(lat, lng, s[1], s[2]))
    return name, haversine_km(lat, lng, s_lat, s_lng)


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance between two points, in kilometres."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lng2 - lng1)

    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


# --- Saving ---------------------------------------------------------------


def save_results(listings: list[ScoredListing], path: str) -> str:
    """Write listings to a CSV (one column per field), creating the folder if needed."""
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)

    with out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(ScoredListing.model_fields))
        writer.writeheader()
        writer.writerows(l.model_dump() for l in listings)

    log.info("Saved %d listings to %s", len(listings), out)
    return str(out)
