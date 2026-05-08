#!/usr/bin/env python3
"""Create a GitHub issue and link it as a sub-issue of a parent issue.

Workflow tooling for the sub-issue task-tracking convention introduced in
issue #17 (governance amendment). `gh` CLI 2.89.0 has no native
`gh sub-issue` subcommand; this wraps the two `gh api` calls required.

Usage:
    scripts/create_subissue.py <parent-issue-number> <title> <body-file>

Steps:
1. Resolve the repository (via `gh repo view`).
2. Look up the parent issue's internal `id`.
3. Create the child issue with `gh issue create` (using the supplied
   title and body file).
4. Look up the child issue's internal `id`.
5. POST to `/repos/{owner}/{repo}/issues/{parent}/sub_issues` to link
   the child as a sub-issue.

Prints the new issue's URL on success.
"""

import json
import subprocess
import sys


def gh(args, input_text=None):
    proc = subprocess.run(
        ["gh"] + args,
        capture_output=True,
        text=True,
        input=input_text,
    )
    if proc.returncode != 0:
        sys.stderr.write(f"gh {' '.join(args)} failed: {proc.stderr}\n")
        sys.exit(proc.returncode)
    return proc.stdout


def gh_api_get_id(repo: str, issue_number: str) -> int:
    info = json.loads(gh(["api", f"/repos/{repo}/issues/{issue_number}"]))
    return info["id"]


def main():
    if len(sys.argv) != 4:
        sys.stderr.write(
            "usage: create_subissue.py <parent-issue-number> <title> <body-file>\n"
        )
        sys.exit(2)

    parent_num, title, body_file = sys.argv[1], sys.argv[2], sys.argv[3]

    repo = gh(
        ["repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner"]
    ).strip()

    # Verify parent exists.
    parent_id = gh_api_get_id(repo, parent_num)

    # Create the child issue.
    new_url = gh(
        ["issue", "create", "--title", title, "--body-file", body_file]
    ).strip()
    new_num = new_url.rsplit("/", 1)[-1]

    # Get child's internal id.
    new_id = gh_api_get_id(repo, new_num)

    # Link as sub-issue. `-F` (uppercase) sends typed values — sub_issue_id
    # must be an integer per the API; `-f` would send it as a string and the
    # API rejects with HTTP 422.
    gh(
        [
            "api",
            "-X",
            "POST",
            f"/repos/{repo}/issues/{parent_num}/sub_issues",
            "-F",
            f"sub_issue_id={new_id}",
        ]
    )

    print(f"#{new_num} created and linked as sub-issue of #{parent_num}: {new_url}")


if __name__ == "__main__":
    main()
