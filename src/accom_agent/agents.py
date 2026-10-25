"""The search agent, the filter step and the pipeline that runs them."""

import json
import logging
import os
from pathlib import Path

from langchain.agents import create_agent
from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import ToolMessage

from prompts import FILTER_PROMPT, SEARCH_PROMPT
from schemas import ClientRequest, Listing, ListingList, ScoredListing
from tools import dedupe, geocode, matches_gender, nearest_station, save_results, web_search, within_budget

log = logging.getLogger(__name__)

OUTPUT_CSV_PATH = Path(__file__).resolve().parent / "output" / "results.csv"


def build_model() -> BaseChatModel:
    """Create the chat model named by MODEL_NAME in .env ("provider:model").

    Local Ollama models get thinking turned off (small models otherwise spend
    their whole reply reasoning) and a larger context window so the search
    results fit.
    """
    model_name = os.getenv("MODEL_NAME", "openai:gpt-5-mini")
    if model_name.startswith("ollama:"):
        return init_chat_model(model_name, reasoning=False, num_ctx=16384)
    return init_chat_model(model_name)


def ask_for_listings(system_prompt: str, content: str) -> list[Listing]:
    """One direct model call that must answer with a ListingList (no tools)."""
    model = build_model().with_structured_output(ListingList)
    response = model.invoke([{"role": "system", "content": system_prompt}, {"role": "user", "content": content}])
    return response.listings


def search(request: ClientRequest) -> list[Listing]:
    """Let the search agent run web searches, then return the listings it found."""
    system_prompt = SEARCH_PROMPT.format(**request.model_dump())
    agent = create_agent(build_model(), tools=[web_search], system_prompt=system_prompt, response_format=ListingList)
    task = (
        f"Find {request.room_type} rooms for rent near {request.university} "
        f"for a {request.gender} student with a budget of RM{request.budget_rm}/month."
    )
    result = agent.invoke({"messages": [{"role": "user", "content": task}]})

    if response := result.get("structured_response"):
        return response.listings

    # Small models often stop without a structured answer: extract the listings
    # from the raw search results the agent collected instead.
    log.info("Search agent gave no structured answer, extracting from its search results")
    results = "\n".join(str(m.content) for m in result["messages"] if isinstance(m, ToolMessage))
    if not results.replace("[]", "").strip():
        return []
    return ask_for_listings(system_prompt, f"Extract the listings from these search results:\n{results}")


def filter_for_client(listings: list[Listing], request: ClientRequest) -> list[Listing]:
    """Ask the model which listings suit the client (gender rule, room type, etc.)."""
    # Hard rules first in code; the model only judges what's left.
    listings = matches_gender(listings, request.gender)
    if not listings:
        return []
    payload = json.dumps([l.model_dump() for l in listings], indent=2)
    return ask_for_listings(FILTER_PROMPT.format(**request.model_dump()), f"Review these listings:\n{payload}")


def score(listings: list[Listing]) -> list[ScoredListing]:
    """Attach the nearest LRT station to each listing, closest first."""
    scored = []
    for listing in listings:
        # Fall back to the building name when the ad has no address.
        coords = geocode(listing.address or listing.building_name)
        station, distance = nearest_station(*coords) if coords else (None, None)
        scored.append(
            ScoredListing(
                **listing.model_dump(),
                nearest_station=station,
                distance_km=round(distance, 2) if distance is not None else None,
            )
        )
    # Listings we couldn't locate go last.
    return sorted(scored, key=lambda s: (s.distance_km is None, s.distance_km or 0))


def run(request: ClientRequest) -> str:
    """Run the full pipeline for one client and return a short summary."""
    log.info("Step 1/4: searching for listings near %s", request.university)
    found = search(request)
    log.info("Found %d listings", len(found))
    for listing in found:
        log.info("  %s | RM%s | %s | %s", listing.building_name, listing.price_rm, listing.gender_rule, listing.link)

    log.info("Step 2/4: filtering for the client")
    kept = filter_for_client(found, request)
    log.info("Kept %d of %d listings", len(kept), len(found))

    log.info("Step 3/4: checking budget and removing duplicates")
    affordable = dedupe(within_budget(kept, request.budget_rm))
    log.info("%d listings left", len(affordable))

    log.info("Step 4/4: finding nearest LRT stations and saving")
    path = save_results(score(affordable), str(OUTPUT_CSV_PATH))

    return f"Found {len(found)} listings, kept {len(affordable)}. Saved to {path}"
