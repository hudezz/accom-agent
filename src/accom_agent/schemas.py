"""Pydantic data models shared by the agents and tools."""

from typing import Literal, Optional

from pydantic import BaseModel, Field


class ClientRequest(BaseModel):
    """What a client of the agency is looking for."""

    university: str = Field(description="University the student will attend, e.g. 'Universiti Malaya'.")
    budget_rm: int = Field(description="Maximum monthly rent in Malaysian Ringgit.")
    gender: Literal["male", "female"]
    age: int
    room_type: Literal["single", "middle", "master", "studio", "shared"]
    nationality: Optional[str] = None


class Listing(BaseModel):
    """A single accommodation listing found online."""

    building_name: str = Field(description="Name of the building, condo or residence.")
    price_rm: Optional[int] = Field(default=None, description="Monthly rent in RM, if stated.")
    room_type: Optional[str] = Field(default=None, description="Room type as advertised.")
    gender_rule: Literal["male_only", "female_only", "mixed", "unknown"] = "unknown"
    address: Optional[str] = None
    link: str = Field(description="URL of the listing.")
    source_site: Optional[str] = Field(default=None, description="Website the listing came from.")
    date_posted: Optional[str] = Field(default=None, description="Posting date as shown on the site.")


class ScoredListing(Listing):
    """A listing enriched with proximity to public transport."""

    nearest_station: Optional[str] = None
    distance_km: Optional[float] = None


class ListingList(BaseModel):
    """Wrapper used as the structured output format of the subagents."""

    listings: list[Listing] = Field(default_factory=list)
