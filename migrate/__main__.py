import os
import sys
import click
from .commands.start import start
from .commands.report import report
from .commands.stats import stats
from .commands.load import load
from .commands.scripts import scripts
from .commands.get import get
from .commands.snapshots import snapshots
from .commands.manns import manns

from loguru import logger


@click.group()
def cli():
    pass


# Create logs directory if it doesn't exist
if not os.path.exists("logs/debug"):
    os.makedirs("logs/debug")

# Remove default handlers
logger.remove()

# Handler for INFO messages
logger.add(
    sys.stderr,
    level="INFO",
    format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | {message}",
)
logger.add(
    "logs/debug/gh-migrate.log",
    level="INFO",
    format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | {message}",
)

logger.add("logs/debug/error.log", format="{time} {level} {message}", level="ERROR")

cli.add_command(start)
cli.add_command(report)
cli.add_command(stats)
cli.add_command(load)
cli.add_command(scripts)
cli.add_command(get)
cli.add_command(snapshots)
cli.add_command(manns)

if __name__ == "__main__":
    cli()
