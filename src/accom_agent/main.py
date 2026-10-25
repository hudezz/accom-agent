"""Entry point: collect client details and run the accommodation agent."""

import logging
from pathlib import Path

from dotenv import load_dotenv

from agents import run
from schemas import ClientRequest


def collect_request() -> ClientRequest:
    """Ask for the client's details on the command line."""
    return ClientRequest(
        university=input("University: ").strip(),
        budget_rm=int(input("Budget (RM/month): ").strip()),
        gender=input("Gender (male/female): ").strip().lower(),
        age=int(input("Age: ").strip()),
        room_type=input("Room type (single/middle/master/studio/shared): ").strip().lower(),
        nationality=input("Nationality (optional): ").strip() or None,
    )


def main() -> None:
    load_dotenv(Path(__file__).resolve().parent / ".env")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s: %(message)s", datefmt="%H:%M:%S")
    # Keep the log readable: hide per-request noise from HTTP libraries.
    for noisy in ("httpx", "httpcore", "primp", "urllib3"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    print(run(collect_request()))


if __name__ == "__main__":
    main()
