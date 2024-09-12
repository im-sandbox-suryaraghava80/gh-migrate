import click
import pandas as pd

import os
from functools import lru_cache
from githubkit import GitHub
from migrate.version import *
from migrate.workbook import *
from loguru import logger


@click.command()
@click.option("--org", "orgs", multiple=True)
@click.option("--pat", "pat")
@click.option("--dry-run", is_flag=True, help="Is this a dry-run?")
@click.option("--wave", type=int, help="Wave number", required=True)
@click.option(
    "-w",
    "--workbook",
    "workbook_path",
    required=False,
    default="./report/InfoMagnus - Migration Workbook.xlsx",
)
@click.argument("output_dir", required=False, default="logs")
# @snapshot_before_after()
def manns(orgs, pat, dry_run, wave, workbook_path, output_dir):
    github = GitHub(pat)

    if dry_run:
        output_dir = os.path.join(output_dir, "dry-run")

    ##########################################
    # Get included source orgs from workbook
    ##########################################
    if orgs == ():
        if dry_run:
            orgs = get_orgs_for_wave("dry_run_target_name", wave, workbook_path)
        else:
            orgs = get_orgs_for_wave("target_name", wave, workbook_path)

    ##########################################
    # Housekeeping
    ##########################################
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    ##########################################
    # The main event
    ##########################################
    logger.info(f"* Inventorying {orgs}")

    users = []

    if orgs is not None:
        for org in orgs:
            logger.info(f"\n* Processing org {org}")
            github = GitHub(pat)

            output_file = f"manns-wave-{org}.csv"
            output_path = os.path.join("./", output_dir, output_file)

            if os.path.exists(output_path):
                os.remove(output_path)

            if dry_run:
                mannequins = pd.DataFrame(
                    [mann for mann in get_mannequins(github, org)]
                )

                mannequins.drop(columns=["claimant", "email"], inplace=True)
                mannequins.rename(columns={"login": "mannequin-user"}, inplace=True)
                mannequins.rename(columns={"id": "mannequin-id"}, inplace=True)
                mannequins["target-user"] = ""
                mannequins["target_org"] = org

                for _, mann in mannequins.iterrows():
                    response = github.rest.users.get_by_username(mann["mannequin-user"])
                    # Convert response to dataframe
                    response = pd.DataFrame([response.json()])

                    # Merge mann with response
                    mann_df = pd.DataFrame([mann])
                    merged_df = pd.merge(
                        mann_df, response, left_on="mannequin-user", right_on="login"
                    )

                    # Remove columns ending with _url
                    url_cols = [col for col in merged_df.columns if col.endswith("url")]
                    merged_df.drop(columns=url_cols, inplace=True)

                    ignore_cols = [
                        "login",
                        "id",
                        "createdAt",
                        "node_id",
                        "gravatar_id",
                        "type",
                        "site_admin",
                        "hireable",
                        "public_repos",
                        "public_gists",
                        "followers",
                        "following",
                    ]
                    merged_df.drop(columns=ignore_cols, inplace=True)

                    # Add merged_df to users
                    users.append(merged_df)

            else:
                raise ValueError("Invalid source/target")

    wb = get_workbook(workbook_path)
    update_manns_worksheet(wb, "Mapping - User", users)


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
