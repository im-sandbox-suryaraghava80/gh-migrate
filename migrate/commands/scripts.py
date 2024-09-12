import glob
import os
import click
from jinja2 import Environment, FileSystemLoader
import pandas as pd
from loguru import logger

from migrate.workbook import *
from migrate.version import checkpoint_file


@click.group()
def scripts():
    pass


def render_template(template_name, output_name, **kwargs):
    """
    Render a jinja2 template and write it to a file.
    """
    env = Environment(loader=FileSystemLoader("."))

    # TODO: Figure out why the first line doesn't work
    # template = env.get_template(os.path.join("scripts", "templates", template_name))
    template = env.get_template(f"./scripts/templates/{template_name}")

    # Render the template with the data
    output = template.render(source_pat="source_pat", target_pat="target_pat", **kwargs)

    # Remove .j2 from the template name
    # script_name = template_name.replace(".j2", "")

    # Write the rendered migration script to the file
    with open(os.path.join("scripts", output_name), "w") as f:
        f.write(output)


###############################
# Unarchive repos script
###############################
@scripts.command()
@click.option(
    "-w",
    "--workbook",
    "workbook_path",
    required=False,
    default="./report/InfoMagnus - Migration Workbook.xlsx",
)
@click.option("--dry-run", is_flag=True, help="Is this a dry-run?")
@click.option("--wave", type=int, help="Wave number", required=True)
def unarchive(workbook_path, dry_run, wave):
    """
    Generate the migration script.
    """

    if dry_run:
        logger.info(f"\n* Generating dry-run unarchive script for wave: {wave}")
        prefix = "DRY-RUN"
    else:
        logger.info(f"\n* Generating production unarchive script for wave: {wave}")
        prefix = "PRODUCTION"

    ###############################
    # Unarchive repos in orgs
    ###############################
    before_source_stats = pd.read_csv(f"./logs/before-source-wave-{int(wave)}.csv")
    before_source_stats = before_source_stats[["name", "owner.login", "isArchived"]]

    # Workaround for issue where CSV has blank lines
    before_source_stats = before_source_stats.dropna()

    render_template(
        "unarchive-repos-for-org.sh.j2",
        f"{prefix}-wave-{wave}-unarchive-repos.sh",
        repos=before_source_stats.to_dict(orient="records"),
    )


###############################
# Migration script
###############################
@scripts.command()
@click.option(
    "-w",
    "--workbook",
    "workbook_path",
    required=False,
    default="./report/InfoMagnus - Migration Workbook.xlsx",
)
@click.option(
    "--final",
    is_flag=True,
    help="Is this after the post-migration activities have completed?",
)
@click.option("--dry-run", is_flag=True, help="Is this a dry-run?")
@click.option("--wave", type=int, help="Wave number", required=True)
def migration(workbook_path, final, dry_run, wave):
    """
    Generate the migration script.
    """

    if dry_run:
        logger.info(f"\n* Generating dry-run migration script for wave: {wave}")
        orgs = get_orgs_for_wave_df(wave, workbook_path)
        prefix = "DRY-RUN"
    else:
        logger.info(f"\n* Generating production migration script for wave: {wave}")
        orgs = get_orgs_for_wave_df(wave, workbook_path)
        prefix = "PRODUCTION"

    if final:
        prefix = f"FINAL-{prefix}"

    # Get the orgs for this wave
    wave_orgs = orgs[orgs["wave"] == wave].to_dict(orient="records")

    ###############################
    # Final migration script
    ###############################
    if final:
        render_template(
            "final-migration.sh.j2",
            f"{prefix}-wave-{wave}-migration.sh",
            target_slug="target_slug",
            orgs=wave_orgs,
            dry_run=dry_run,
            wave=wave,
        )
        return

    ###############################
    # Add migration banner to orgs
    ###############################
    render_template(
        "add-announcement-banner-to-orgs.sh.j2",
        f"{prefix}-wave-{wave}-add-announcement-banner.sh",
        orgs=wave_orgs,
    )

    ###############################
    # Archive repos in orgs
    ###############################
    if not dry_run:
        # We assume that a dry-run was completed
        before_source_stats = pd.read_csv(
            f"./logs/dry-run/before-source-wave-{int(wave)}.csv"
        )
        before_source_stats = before_source_stats[["name", "owner.login"]]

        render_template(
            "archive-repos-for-org.sh.j2",
            f"{prefix}-wave-{wave}-archive-repos.sh",
            repos=before_source_stats.to_dict(orient="records"),
        )

    ###############################
    # The actual migration script
    ###############################
    render_template(
        "migration.sh.j2",
        f"{prefix}-wave-{wave}-migration.sh",
        target_slug="target_slug",
        orgs=wave_orgs,
        dry_run=dry_run,
        wave=wave,
    )


##############################################################################
# Post-migration scripts
##############################################################################
@scripts.command()
@click.option(
    "-w",
    "--workbook",
    "workbook_path",
    required=False,
    default="./report/InfoMagnus - Migration Workbook.xlsx",
)
@click.option("--dry-run", is_flag=True, help="Is this a dry-run?")
@click.option("--wave", type=int, help="Wave number", required=True)
def post_migration(workbook_path, dry_run, wave):
    logger.info("*** Generating post-migration scripts")

    if dry_run:
        logger.info(f"* Generating dry-run post-migration script for wave: {wave}")
        orgs = get_orgs_for_wave_df(wave, workbook_path)
        prefix = "DRY-RUN"
        snapshots_dir = os.path.join("snapshots", "dry-run")
    else:
        logger.info(f"* Generating production post-migration script for wave: {wave}")
        orgs = get_orgs_for_wave_df(wave, workbook_path)
        prefix = "PRODUCTION"
        snapshots_dir = "snapshots"

    ###############################
    # Create post-migration scripts
    ###############################

    # Get the orgs for this wave
    wave_orgs = orgs[orgs["wave"] == wave].to_dict(orient="records")

    for org in wave_orgs:
        source_org = org["source_name"]
        target_org = org["target_name"]

        ###############################
        # Create teams
        ###############################
        teams_dir = os.path.join(snapshots_dir, f"before-source-{source_org}-teams.csv")

        teams_df = pd.read_csv(teams_dir)

        output_file = f"{prefix}-wave-{int(wave)}-create-teams-{target_org}.sh"

        render_template(
            "create-teams-for-org.sh.j2",
            output_file,
            teams=teams_df.to_dict(orient="records"),
            target_org=target_org,
        )

        ###############################
        # Update team permissions
        ###############################
        team_repos_dir = os.path.join(
            snapshots_dir, f"before-source-{source_org}-team-repos.csv"
        )

        team_repos_df = pd.read_csv(team_repos_dir)

        output_file = f"{prefix}-wave-{int(wave)}-update-team-perms-{target_org}.sh"

        render_template(
            "update-team-perms.sh.j2",
            output_file,
            repos=team_repos_df.to_dict(orient="records"),
            target_org=target_org,
        )

        ###############################
        # Update repo visibility
        ###############################
        repos_dir = os.path.join(snapshots_dir, f"before-source-{source_org}-repos.csv")

        repos_df = pd.read_csv(repos_dir)

        output_file = (
            f"{prefix}-wave-{int(wave)}-update-repo-visibility-{target_org}.sh"
        )

        # We only need the name and visibility columns
        repos_df = repos_df[["name", "visibility"]]

        render_template(
            "update-repo-visibility.sh.j2",
            output_file,
            repos=repos_df.to_dict(orient="records"),
            target_org=target_org,
        )

        ###############################
        # Add users to teams
        ###############################
        team_users_file = os.path.join(
            snapshots_dir, f"before-source-{source_org}-team-users.csv"
        )

        team_users_df = pd.read_csv(team_users_file)

        # The mannequins file contains the mapping of mannequin-user to target-user
        mannequins_df = get_mannequin_df(workbook_path)

        # Map the user from the source org to target org using mannequins.csv
        mapped_users = team_users_df.merge(
            # We use a left join so we can identify unmapped users
            # (they will be NaN in the "target-user" column)
            mannequins_df,
            how="left",
            left_on=["login", "org"],
            right_on=["mannequin-user", "source_org"],
        )

        # Identify unmapped users
        unmapped_users = mapped_users[mapped_users["target-user"].isna()]
        if not unmapped_users.empty:
            logger.info(f"*** Couldn't map these users for {target_org}:")
            logger.info(
                unmapped_users[["team_slug", "login", "mannequin-user", "target-user"]]
            )

        output_file = f"{prefix}-wave-{int(wave)}-add-users-to-teams-{target_org}.sh"

        mapped_users = mapped_users[mapped_users["target-user"].notna()]
        render_template(
            "add-users-to-teams.sh.j2",
            output_file,
            users=mapped_users.to_dict(orient="records"),
            target_org=target_org,
        )

    # repos = get_repos_by_exclude("exclude")
    # teams = get_teams_by_exclude("exclude")


# ###############################
# # Create teams
# ###############################
# @scripts.command()
# def create_teams(teams):
#     """
#     Generate the "create teams" script.
#     """
#     render_template("step5-create-teams.sh.j2", teams=teams)


# ###############################
# # Get migration logs
# ###############################
# @scripts.command()
# def get_migration_logs(repos):
#     """
#     Generate the "get migration logs" script.
#     """
#     render_template("step5-get-migration-logs.sh.j2", repos=repos)


# ###############################
# # Rollback migration
# ###############################
# @scripts.command()
# def rollback_migration(repos):
#     """
#     Generate the "rollback migration" script.
#     """
#     render_template("step5-rollback-migration.sh.j2", repos=repos)
