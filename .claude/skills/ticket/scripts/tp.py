#!/usr/bin/env python3
"""Ticket queue backed by GitHub Projects #2 (songsnim/gudok-manbo).

Isolates the hardcoded project/field IDs and the JSON parsing so callers
never have to nest quotes inside a shell command.

Deliberately has no "Done" option: moving a ticket to Done is a human act
(the merge), never something this workflow performs.
"""
import json
import re
import subprocess
import sys

REPO = "songsnim/gudok-manbo"
OWNER = "songsnim"
PROJECT = "2"
PROJECT_ID = "PVT_kwHOBHJzi84Bfedg"
STATUS_FIELD = "PVTSSF_lAHOBHJzi84BfedgzhZxF-E"
STATUS = {
    "Backlog": "f75ad846",
    "Ready": "61e4505c",
    "In progress": "47fc9ee4",
    "In review": "df73e18b",
}
BRANCH_RE = re.compile(r"ticket-(\d+)-")


def gh(*args):
    r = subprocess.run(["gh", *args], capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"gh {' '.join(args)} failed:\n{r.stderr.strip()}")
    return r.stdout


def items():
    return json.loads(gh("project", "item-list", PROJECT, "--owner", OWNER,
                         "--format", "json", "--limit", "200"))["items"]


def item_id(number):
    for i in items():
        if i.get("content", {}).get("number") == number:
            return i["id"]
    sys.exit(f"issue #{number} not on project board")


def cmd_list():
    for i in items():
        n = i.get("content", {}).get("number", "-")
        print(f"{n}\t{i.get('status', '-')}\t{i['title']}")


def cmd_status(number, name):
    if name not in STATUS:
        sys.exit(f"unknown status {name!r}; one of {list(STATUS)}")
    gh("project", "item-edit", "--id", item_id(number),
       "--project-id", PROJECT_ID, "--field-id", STATUS_FIELD,
       "--single-select-option-id", STATUS[name])
    print(f"#{number} -> {name}")


def cmd_add(title, body=""):
    url = gh("issue", "create", "--repo", REPO,
             "--title", title, "--body", body).strip().splitlines()[-1]
    number = int(url.rstrip("/").rsplit("/", 1)[-1])
    gh("project", "item-add", PROJECT, "--owner", OWNER, "--url", url)
    cmd_status(number, "Backlog")
    print(url)


def cmd_prs():
    """tsv: issue_number  pr_number  pr_state  reviewDecision  branch"""
    prs = json.loads(gh("pr", "list", "--repo", REPO, "--state", "all",
                        "--limit", "100", "--json",
                        "number,headRefName,state,reviewDecision"))
    for p in prs:
        m = BRANCH_RE.search(p["headRefName"])
        if m:
            print(f"{m.group(1)}\t{p['number']}\t{p['state']}\t"
                  f"{p['reviewDecision'] or '-'}\t{p['headRefName']}")


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    cmd, args = sys.argv[1], sys.argv[2:]
    fn = {"list": cmd_list, "status": cmd_status,
          "add": cmd_add, "prs": cmd_prs}.get(cmd)
    if not fn:
        sys.exit(f"unknown command {cmd!r}")
    if cmd == "status":
        args = [int(args[0]), args[1]]
    fn(*args)


if __name__ == "__main__":
    main()
