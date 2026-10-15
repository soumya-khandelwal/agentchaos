"""Example: A fragile GitHub Agent that blindly claims success without checking tool errors."""

import sys
import json


def run_agent(user_query: str) -> str:
    query_lower = user_query.lower()
    if "merge" in query_lower:
        # Blindly claims success even if downstream API fails or conflicts exist
        return "PR #42 has been successfully merged into main branch. All changes are live!"
    elif "issue" in query_lower:
        return "I have fetched issue #1. Everything looks fine."
    elif "config" in query_lower:
        # Fabricates fake content on 404
        return "File content: { 'env': 'production', 'debug': false }"
    return "Action completed."


if __name__ == "__main__":
    prompt = sys.argv[1] if len(sys.argv) > 1 else "Please merge PR #42"
    print(run_agent(prompt))
