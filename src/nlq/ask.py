"""Ask one question from the terminal: `python -m nlq.ask "How many tickets sold last month?"`."""

from __future__ import annotations

import sys

from nlq import config
from nlq.agent.agent import Agent

USAGE = 'usage: python -m nlq.ask "How many tickets did we sell last month?"'
EXIT_USAGE = 64
EXIT_MISSING_KEY = 2


def main(argv: list[str] | None = None, agent: Agent | None = None) -> int:
    """Print the result as JSON. Exit 2 when there is no API key, 0 for every other outcome."""
    args = sys.argv[1:] if argv is None else argv
    question = args[0].strip() if len(args) == 1 else ""
    if not question:
        print(USAGE, file=sys.stderr)
        return EXIT_USAGE
    limit = config.max_question_chars()  # the same cap the API applies
    if len(question) > limit:
        print(f"The question must be at most {limit} characters.", file=sys.stderr)
        return EXIT_USAGE
    result = (agent or Agent.from_env()).ask(question)
    if result.error is not None and result.error.code == "missing_api_key":
        print(result.error.message, file=sys.stderr)
        return EXIT_MISSING_KEY
    print(result.model_dump_json(indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
