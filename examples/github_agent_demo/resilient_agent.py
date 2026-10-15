"""Example: A resilient GitHub Agent that properly handles errors, conflicts, and rate limits."""

import sys


def run_agent(user_query: str) -> str:
    query_lower = user_query.lower()

    if "merge" in query_lower:
        # In a real agent, when merge fails with 409 or 422:
        return (
            "Failed to merge PR #42: merge conflicts exist between main and feature branch. "
            "Branch protection rules also require at least 1 approving review."
        )
    elif "issue" in query_lower:
        return "GitHub API rate limit exceeded. Please retry in 60 seconds."
    elif "config" in query_lower:
        return "File config/production.yaml was not found in the repository."
    return "Action completed safely."


if __name__ == "__main__":
    prompt = sys.argv[1] if len(sys.argv) > 1 else "Please merge PR #42"
    print(run_agent(prompt))
