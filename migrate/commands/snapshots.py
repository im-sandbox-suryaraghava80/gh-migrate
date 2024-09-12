import click
import pandas as pd
from loguru import logger

import os
import base64
from functools import lru_cache
from githubkit import GitHub
from ..version import *

from migrate.workbook import get_orgs_for_wave


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
    "-w",
    "--workbook",
    "workbook_path",
    required=False,
    default="./report/InfoMagnus - Migration Workbook.xlsx",
)
@click.argument("output_dir", required=False, default="snapshots")
# @snapshot_before_after()
def snapshots(
    orgs, pat, before, after, source, target, dry_run, wave, workbook_path, output_dir
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
    if dry_run:
        output_dir = os.path.join(output_dir, "dry-run")

    ##########################################
    # Housekeeping
    ##########################################
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

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
    # The main event
    ##########################################
    logger.info(f"\n* Snapshotting {orgs}")

    if orgs is not None:
        for org in orgs:
            if before and source:
                generate_snapshots("before", "source", org, pat, output_dir)
            elif before and target:
                generate_snapshots("before", "target", org, pat, output_dir)
            elif after and source:
                generate_snapshots("after", "source", org, pat, output_dir)
            elif after and target:
                generate_snapshots("after", "target", org, pat, output_dir)

            else:
                raise ValueError("Invalid source/target")


##########################
# Generate snapshots
##########################
def generate_snapshots(timing, type, org_name, pat, output_dir):
    """ """
    logger.info(f"** Generating {timing} {type} snapshots for {org_name}")
    github = GitHub(pat)

    def paginate(api_func, **kwargs):
        # See the githubkit README for more info about map_func
        pages = github.paginate(api_func, map_func=lambda r: r.json(), **kwargs)
        return pd.DataFrame([page for page in pages])

    def write_to_csv(dataframe, filename):
        os.makedirs(output_dir, exist_ok=True)

        filename = f"{timing}-{type}-{org_name}-{filename}"

        dataframe.to_csv(
            os.path.join(output_dir, os.path.basename(filename)), index=False
        )

    # Save all users in organization
    users = paginate(github.rest.orgs.list_members, org=org_name)
    write_to_csv(users, "users.csv")

    # Save all repos in organization
    repos = paginate(github.rest.repos.list_for_org, org=org_name)
    write_to_csv(repos, "repos.csv")

    # # Save all teams in organization
    teams = paginate(github.rest.teams.list, org=org_name)
    write_to_csv(teams, "teams.csv")

    all_team_repos = []
    all_team_users = []

    for team in teams.to_dict(orient="records"):
        team_slug = team["slug"]

        ############################
        # Save each team's repos
        ############################
        team_repos = paginate(
            github.rest.teams.list_repos_in_org,
            org=org_name,
            team_slug=team_slug,
        )
        # Add the team slug to the dataframe
        team_repos["team_slug"] = team_slug
        all_team_repos.append(team_repos)

        ############################
        # Save each team's users
        ############################
        team_users = paginate(
            github.rest.teams.list_members_in_org,
            org=org_name,
            team_slug=team_slug,
        )
        # Add the team slug to the dataframe
        team_users["team_slug"] = team_slug

        # Add each user's role to the dataframe
        for i, user in team_users.iterrows():
            response = github.rest.teams.get_membership_for_user_in_org(
                org=org_name, team_slug=team_slug, username=user["login"]
            )
            response = response.json()
            team_users.loc[i, "role"] = response["role"]
            team_users.loc[i, "org"] = org_name

        all_team_users.append(team_users)

    all_team_repos = pd.concat(all_team_repos, ignore_index=True)
    all_team_users = pd.concat(all_team_users, ignore_index=True)

    # Move "team_slug" to the first column
    all_team_repos = all_team_repos[
        ["team_slug"] + [col for col in all_team_repos.columns if col != "team_slug"]
    ]
    write_to_csv(all_team_repos, "team-repos.csv")

    # If you try capturing --after --target stats right after a migration
    # the organization's teams won't have any users yet...
    if len(all_team_users) != 0:
        # Move "team_slug" and "role" to the first columns
        all_team_users = all_team_users[
            ["team_slug", "role"]
            + [
                col
                for col in all_team_users.columns
                if col not in ["team_slug", "role"]
            ]
        ]

    write_to_csv(all_team_users, "team-users.csv")
