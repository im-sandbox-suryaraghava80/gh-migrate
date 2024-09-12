import click
from loguru import logger

from migrate.workbook import *
from migrate.version import snapshot_before_after


@click.command()
# @snapshot_before_after()
def start():

    logger.info(f"*** Initializing migration workbook")
    initialize_workbook()
