# Accom Agent

An AI agent that finds student accommodation near Malaysian universities.

Give it a client's details (university, budget, gender, age, room type) and it searches the web for room listings, keeps the ones that suit the client, and saves them to a CSV, sorted by distance to the nearest LRT station.

## How it works

1. **Search**: an LLM agent runs several web searches (Tavily, or free DuckDuckGo if no Tavily key is set) and pulls out listings: building, price, room type, gender rule, address, link.
2. **Filter**: listings that exclude the client's gender are dropped in code, then the LLM removes ones that don't fit (wrong room type, "no students", not a real listing, too far away).
3. **Budget and duplicates**: listings over budget are dropped (those with no stated price are kept so the team can ask), and duplicates are removed.
4. **LRT distance**: each listing is geocoded and matched to its nearest Kelana Jaya, Ampang or Sri Petaling line station.
5. **Save**: results are written to `src/accom_agent/output/results.csv`.

## Setup

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/hudezz/accom-agent.git
cd accom-agent
uv sync
cp src/accom_agent/.env.example src/accom_agent/.env
```

Then fill in `src/accom_agent/.env`:

| Variable | Required | Description |
| --- | --- | --- |
| `MODEL_NAME` | No | LLM as `provider:model`. Default `openai:gpt-5-mini`. |
| `OPENAI_API_KEY` | For OpenAI models | Your OpenAI API key. |
| `TAVILY_API_KEY` | No | Uses Tavily for search; DuckDuckGo is used if empty. |
| `GOOGLE_MAPS_API_KEY` | No | Uses Google Maps for geocoding; OpenStreetMap is used if empty. |
| `MAX_SEARCH_RESULTS` | No | Results per search. Default `10`. |

### Running with a local model (Ollama)

Install [Ollama](https://ollama.com), pull a model and point `MODEL_NAME` at it:

```bash
ollama pull qwen3:8b
```

```
MODEL_NAME=ollama:qwen3:8b
```

No API keys are needed in this setup. Very small models (under ~4B parameters) work but give poor results.

## Usage

```bash
cd src/accom_agent
uv run python main.py
```

You'll be asked for the client's details:

```
University: Universiti Malaya
Budget (RM/month): 800
Gender (male/female): male
Age: 20
Room type (single/middle/master/studio/shared): single
Nationality (optional): Malaysian
```

Progress is logged as it runs, and the final line shows where the CSV was saved.

## Project structure

```
src/accom_agent/
├── main.py          # Entry point: loads .env, sets up logging, asks for client details
├── agents.py        # Search agent, filter step and the pipeline (run)
├── tools.py         # Web search, filtering, geocoding and CSV saving
├── prompts.py       # Prompts for the search agent and filter step
├── schemas.py       # Pydantic models: ClientRequest, Listing, ScoredListing
└── data/
    └── lrt_stations.csv  # LRT station names and coordinates
```

## Notes

- Station coordinates in `data/lrt_stations.csv` are approximate.
- Results depend heavily on the model and search provider; always check listings before sending them to a client.
