from loguru import logger

logger.add("file_{time}.log")
logger.info("That's it, beautiful and simple logging!")
