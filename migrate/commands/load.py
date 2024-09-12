import os
import click
import pandas as pd
from loguru import logger

from migrate.version import checkpoint_file, snapshot_before_after

from migrate.workbook import *


@click.group()
def load():
    pass


@load.command()
@click.argument(
    "before-source", required=False, default="./logs/before-source-wave-0.csv"
)
@click.argument(
    "before-target", required=False, default="./logs/before-target-wave-0.csv"
)
@click.option(
    "-w",
    "--workbook",
    "workbook_path",
    required=False,
    default="./report/InfoMagnus - Migration Workbook.xlsx",
)
# @snapshot_before_after()
def inventory(before_source, before_target, workbook_path):
    "" ""

    workbook = get_workbook(workbook_path)

    source_stats = pd.read_csv(
        before_source,
        parse_dates=["updatedAt", "pushedAt"],
    )
    logger.info(f"*** Loading inventory")
    add_inventory_worksheet(workbook, "Inventory - Source Repos", source_stats)

    # If before_file exists
    if os.path.exists(before_target):
        target_stats = pd.read_csv(
            before_target,
            parse_dates=["updatedAt", "pushedAt"],
        )

        add_inventory_worksheet(workbook, "Inventory - Target Repos", target_stats)

    logger.info(f"*** Generating pre-migration report")
    add_pre_migration_report(workbook, "Pre-migration Report", source_stats)
    logger.info(f"*** Adding org mapping")
    add_org_mapping(workbook, "Mapping - Org", source_stats)
    logger.info(f"*** Adding user mapping")
    add_user_mapping(workbook, "Mapping - User", source_stats)

    logger.info(f"*** Migration workbook updated")
