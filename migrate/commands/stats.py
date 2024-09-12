import click
import pandas as pd

import os
import base64
from functools import lru_cache
from githubkit import GitHub
from ..version import *
from loguru import logger

from migrate.workbook import get_orgs_for_wave

from datetime import timedelta
from githubkit.retry import RetryOption
from githubkit.exception import PrimaryRateLimitExceeded, SecondaryRateLimitExceeded


def auto_retry_handler(exc, retry_count=10):

    if isinstance(exc, PrimaryRateLimitExceeded) and retry_count == 0:
        # Wait for the time specified by the rate limit before retrying
        logger.error(
            f"Primary rate limit exceeded. Waiting {exc.retry_after} seconds (retry_count={retry_count})"
        )
        return RetryOption(True, exc.retry_after)

    if isinstance(exc, SecondaryRateLimitExceeded) and retry_count == 0:
        # Wait for the time specified by the rate limit before retrying
        logger.error(
            f"Secondary rate limit exceeded. Waiting {exc.retry_after} seconds (retry_count={retry_count})"
        )
        return RetryOption(True, exc.retry_after)

    # In other cases, don't retry
    logger.error(f"Error (auto_retry_handler): {exc}")
    return RetryOption(False)


@click.command()
@click.option("--org", "orgs", multiple=True)
@click.option("--pat", "pat")
@click.option("--before", is_flag=True, help="Run before migration")
@click.option("--after", is_flag=True, help="Run after migration")
@click.option("--source", is_flag=True, help="Source organization(s)")
@click.option("--target", is_flag=True, help="Target organization(s)")
@click.option("--dry-run", is_flag=True, help="Is this a dry-run?")
@click.option("--wave", type=int, help="Wave number", required=True)
@click.option(
    "--resume", is_flag=True, help="Resume an aborted stats run?", required=False
)
@click.option(
    "-w",
    "--workbook",
    "workbook_path",
    required=False,
    default="./report/InfoMagnus - Migration Workbook.xlsx",
)
@click.argument("output_dir", required=False, default="logs")
# @snapshot_before_after()
def stats(
    orgs,
    pat,
    before,
    after,
    source,
    target,
    dry_run,
    wave,
    resume,
    workbook_path,
    output_dir,
):
    ##########################################
    # Check command line fslags
    ##########################################
    if not (before ^ after):
        raise click.UsageError("You must supply either --before or --after")
    if not (source ^ target):
        raise click.UsageError("You must supply either --source or --target")

    ##########################################
    # Build output file name
    ##########################################
    if before and source:
        output_file = f"before-source-wave-{wave}.csv"
    elif before and target:
        output_file = f"before-target-wave-{wave}.csv"
    elif after and source:
        output_file = f"after-source-wave-{wave}.csv"
    elif after and target:
        output_file = f"after-target-wave-{wave}.csv"

    if dry_run:
        output_dir = os.path.join(output_dir, "dry-run")

    ##########################################
    # Get included source orgs from workbook
    ##########################################
    if orgs == ():
        if source:
            orgs = get_orgs_for_wave("source_name", wave, workbook_path)
        elif target:
            if dry_run:
                orgs = get_orgs_for_wave("dry_run_target_name", wave, workbook_path)
            else:
                orgs = get_orgs_for_wave("target_name", wave, workbook_path)

    ##########################################
    # Housekeeping
    ##########################################
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    output_path = os.path.join("./", output_dir, output_file)

    # checkpoint_file(output_path, f"STATS: Saving old {output_path}")

    if not resume and os.path.exists(output_path):
        os.remove(output_path)

    ##########################################
    # The main event
    ##########################################
    logger.info(f"Beginning inventory for {orgs}")

    if orgs is not None:
        for org in orgs:
            logger.info(f"* Processing org {org}")
            github = GitHub(pat, auto_retry=auto_retry_handler)
            if source:
                process_org(github, "source", org, output_path, resume)
            elif target:
                process_org(github, "target", org, output_path, resume)

                # if dry_run:
                # Get mannequins
                # mannequins = get_mannequins(github, org)
            else:
                raise ValueError("Invalid source/target")

    # checkpoint_file(output_path, f"STATS: Saving new {output_path}")


def process_org(github, source, org, output_dir, resume):
    """Process all repos in an org"""

    ############################################################
    # Recursively cleanup all pageInfos and nodes from repo dict
    ############################################################
    def cleanup_repo(d):
        if isinstance(d, dict):
            if "pageInfo" in d:
                del d["pageInfo"]
            if "nodes" in d:
                del d["nodes"]
            for k, v in d.items():
                cleanup_repo(v)
        elif isinstance(d, list):
            for i in d:
                cleanup_repo(i)

    # If resume is true, open the csv in output_dir, read in all of the values in the name column
    if resume:
        df = pd.read_csv(output_dir)
        processed_repos = df["name"].tolist()

    ############################################################
    # Get repos
    ############################################################
    repos = get_repos(github, org)

    for repo in repos:
        if resume:
            if repo["name"] in processed_repos:
                logger.info(f'** Skipping repo "{repo["name"]}"')
                continue

        logger.info(f'** Processing repo "{repo["name"]}"')

        ############################################################
        # Get issues
        ############################################################
        issues = pd.DataFrame([issue for issue in get_issues(github, repo)])

        if len(issues) == 0:
            repo["issues"]["comments"] = {"totalCount": 0}
            repo["issues"]["timelineItems"] = {"totalCount": 0}
        else:
            # Sum comments
            repo["issues"]["comments"] = {
                "totalCount": sum([i["totalCount"] for i in issues["comments"]])
            }
            # Sum timelineItems
            repo["issues"]["timelineItems"] = {
                "totalCount": sum([i["totalCount"] for i in issues["timelineItems"]])
            }

        ############################################################
        # Get PRs
        ############################################################
        pulls = pd.DataFrame([pull for pull in get_pulls(github, repo)])

        if len(pulls) == 0:
            repo["pullRequests"]["comments"] = {"totalCount": 0}
            repo["pullRequests"]["commits"] = {"totalCount": 0}
            repo["pullRequests"]["timelineItems"] = {"totalCount": 0}
        else:
            # Sum comments
            repo["pullRequests"]["comments"] = {
                "totalCount": sum([i["totalCount"] for i in pulls["comments"]])
            }
            # Sum commits
            repo["pullRequests"]["commits"] = {
                "totalCount": sum([i["totalCount"] for i in pulls["commits"]])
            }
            # Sum timelineItems
            repo["pullRequests"]["timelineItems"] = {
                "totalCount": sum([i["totalCount"] for i in pulls["timelineItems"]])
            }

        # Add in the REST API stats
        get_rest_api_stats(github, repo)

        # Remove pageInfos and nodes
        cleanup_repo(repo)

        # Add source
        repo["Source"] = source

        # Add date and time
        repo["Inventoried"] = pd.Timestamp.now()

        # Normalize column headings
        repo = pd.json_normalize(repo)

        # Write to file
        with open(output_dir, "a") as f:
            repo.to_csv(f, header=f.tell() == 0, index=False)


def get_pat(type):
    if type == "source":
        return os.environ["GH_SOURCE_PAT"]
    elif type == "target":
        return os.environ["GH_TARGET_PAT"]
    else:
        raise ValueError('Type must be "source" or "target"')


def get_issues(github, repo):
    yield from get_nodes(
        github,
        "issues",
        {
            "owner": repo["owner"]["login"],
            "name": repo["name"],
            "pageSize": 100,
            "endCursor": None,
        },
        ["repository", "issues"],
    )


def get_pulls(github, repo):
    yield from get_nodes(
        github,
        "pulls",
        {
            "owner": repo["owner"]["login"],
            "name": repo["name"],
            "pageSize": 100,
            "endCursor": None,
        },
        ["repository", "pullRequests"],
    )


def get_repos(github, org):
    yield from get_nodes(
        github,
        "org-repos",
        {"login": org, "pageSize": 10, "endCursor": None},
        ["organization", "repositories"],
    )


def get_mannequins(github, org):
    yield from get_nodes(
        github,
        "org-mannequins",
        {"login": org, "pageSize": 10, "endCursor": None},
        ["organization", "mannequins"],
    )


def get_nodes(github, query_name, variables, page_path):
    """Retrieves all nodes from a paginated GraphQL query"""

    @lru_cache(maxsize=None)
    def get_query(name):
        with open(f"migrate/graphql/{name}.graphql") as f:
            return f.read()

    # https://stackoverflow.com/questions/71460721/best-way-to-get-nested-dictionary-items
    def get_nested_item(d, key):
        for level in key:
            d = d[level]
        return d

    query = get_query(query_name)

    while True:
        response = github.graphql(query, variables=variables)

        # Print errors and exit if any found
        if "errors" in response:
            for error in response["errors"]:
                logger.info(f"Error: {error['message']}")
            return

        items = get_nested_item(response, page_path)
        for item in items["nodes"]:
            yield item

        # Exit if no more pages
        if not items["pageInfo"]["hasNextPage"]:
            break

        # Otherwise, update the endCursor and continue
        variables["endCursor"] = items["pageInfo"]["endCursor"]


def get_rest_api_stats(github: GitHub, repo: dict):
    """Retrieves stats from the REST API for a repo, as
    the GraphQL API does not provide all stats"""

    repo_name = repo["name"]
    org_name = repo["owner"]["login"]

    ############################################################
    # Get webhooks count
    ############################################################
    response = github.rest.repos.list_webhooks(owner=org_name, repo=repo_name)
    repo["webhooks"] = {"totalCount": len(response.json())}

    ############################################################
    # Get workflows count
    ############################################################
    response = github.rest.actions.list_repo_workflows(org_name, repo_name)
    repo["workflows"] = {"totalCount": response.json()["total_count"]}

    ############################################################
    # Get last workflow run
    ############################################################
    response = github.rest.actions.list_workflow_runs_for_repo(org_name, repo_name)
    if response.json()["total_count"] == 0:
        repo["lastWorkflowRun"] = None
    else:
        repo["lastWorkflowRun"] = response.json()["workflow_runs"][0]["created_at"]

    ############################################################
    # Get branches
    ############################################################
    response = github.rest.repos.list_branches(org_name, repo_name)
    if len(response.json()) == 0:
        repo["branches"] = []
    else:
        repo["branches"] = [branch["name"] for branch in response.json()]
        repo["branches"].sort()

    ############################################################
    # Get teams
    ############################################################
    response = github.rest.repos.list_teams(org_name, repo_name)
    if len(response.json()) == 0:
        repo["teams"] = []
    else:
        repo["teams"] = [team["name"] for team in response.json()]
        repo["teams"].sort()

    ############################################################
    # Get environments
    ############################################################
    response = github.rest.repos.get_all_environments(org_name, repo_name)
    repo["environments"] = response.json()["total_count"]

    ############################################################
    # Get secrets
    ############################################################
    # TODO: Keeping these checks is causing GitHub to throw rate limit errors
    # response = github.rest.actions.list_repo_secrets(org_name, repo_name)
    # repo["secrets_actions_repo"] = response.json()["total_count"]

    # response = github.rest.actions.list_repo_organization_secrets(org_name, repo_name)
    # repo["secrets_actions_org"] = response.json()["total_count"]

    # response = github.rest.dependabot.list_repo_secrets(org_name, repo_name)
    # repo["secrets_dependabot"] = response.json()["total_count"]

    # try:
    #     response = github.rest.codespaces.list_repo_secrets(org_name, repo_name)
    #     repo["secrets_codespaces"] = response.json()["total_count"]
    # except Exception as e:
    #     repo["secrets_codespaces"] = 0
    # logger.exception(e)

    ############################################################
    # Get repository topics, perms, visibility, security
    ############################################################
    response = github.rest.repos.get(org_name, repo_name)
    repo["topics"] = response.json()["topics"].sort()
    repo["permissions"] = response.json()["permissions"]
    repo["visibility"] = response.json()["visibility"]
    # TODO: Fix this.  If customers don't have GHAS, then this throws an error
    # repo["security_and_analysis"] = response.json()["security_and_analysis"]

    ############################################################
    # Check if GitLFS being used by checking .gitattributes
    ############################################################
    # TODO: Keeping this check is causing GitHub to throw rate limit errors
    # try:
    #     response = github.rest.repos.get_content(org_name, repo_name, ".gitattributes")

    #     # If .gitattributes contains the string '=lfs', then git LFS is enabled
    #     repo["hasGitLFS"] = "=lfs" in base64.b64decode(response.json()["content"])
    # except Exception as e:
    #     repo["hasGitLFS"] = False
