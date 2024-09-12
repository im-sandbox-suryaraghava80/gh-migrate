import click
import pandas as pd

import os
from functools import lru_cache
from githubkit import GitHub

import subprocess
from datetime import datetime
from loguru import logger

from migrate.workbook import get_orgs_for_wave

###############################################################################
# We can grab the migration logs in the following ways:
#
# Within 1 day of migration, we can use the GH migration API to get the logs
#
# If the migration is older than 1 day:
# - If GEI 'migrate-org' was used
#   - we can get the logs from 'gei-migration-results' repo
# - If GEI 'migrate-repo' was used
#   - we can get the logs from the issue comment of the last issue in the repo
#
# The problem with retrieving logs from the issue comment is that if issues are
# not enabled in the repo, GEI will not be able to post the logs.
###############################################################################


@click.group()
def get():
    pass


@get.command()
@click.option("--org", "orgs", multiple=True, required=False)
@click.option("--pat", "pat", required=True)
@click.option("--wave", type=int, help="Wave number", required=True)
@click.option(
    "-w",
    "--workbook",
    "workbook_path",
    required=False,
    default="report/InfoMagnus - Migration Workbook.xlsx",
)
@click.option("--dry-run", is_flag=True, help="Is this a dry-run?")
@click.option("-o", "--output", "output", required=True, default="logs")
def logs(orgs, pat, wave, workbook_path, dry_run, output):
    logger.info(f"* Checking {orgs}")

    if dry_run:
        output = os.path.join(output, "dry-run")

    # Create output directory if it doesn't exist
    if not os.path.exists(output):
        os.makedirs(output)

    ##########################################
    # Get included source orgs from workbook
    ##########################################
    if orgs == ():
        if dry_run:
            orgs = get_orgs_for_wave("dry_run_target_name", wave, workbook_path)
        else:
            orgs = get_orgs_for_wave("target_name", wave, workbook_path)

    if orgs is not None:
        for org in orgs:
            logger.info(f"\n* Processing org {org}")
            get_org_log(pat, org, output)


def get_org_log(pat, org, output_dir):
    """Process all repos in an org"""

    output_dir = f"{output_dir}/{org}"

    env = os.environ.copy()
    env["GITHUB_TOKEN"] = pat

    # Define the command
    command = [
        "gh",
        "repo",
        "clone",
        f"https://github.com/{org}/gei-migration-results",
        output_dir,
    ]

    # Run the command
    result = subprocess.run(
        command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env
    )

    if result.returncode == 0:
        logger.info("Retrieved migration logs successfully!")
    else:
        logger.info(
            f'Failed to retrieve migration logs: {result.stderr.decode("utf-8")}'
        )
