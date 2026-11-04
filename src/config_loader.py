"""
config_loader.py
----------------
Loads config.yaml and merges it with environment variables from .env.
"""

import os
import logging
from pathlib import Path

import yaml
from dotenv import load_dotenv

logger = logging.getLogger("spacebasic.config")

CONFIG_PATH = Path("config") / "config.yaml"
ENV_PATH = Path(".env")


def load_config(config_path: Path = CONFIG_PATH) -> dict:
    """
    Load YAML config and populate os.environ from .env file.

    Returns the config dict. Credentials remain in os.environ,
    never mixed into the config dict.
    """
    # Load .env first (sets os.environ, does not override existing vars)
    if ENV_PATH.exists():
        load_dotenv(ENV_PATH, override=False)
        logger.debug(".env loaded from %s", ENV_PATH)
    else:
        logger.warning(".env not found at %s — credentials must already be in environment", ENV_PATH)

    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    logger.debug("Config loaded from %s", config_path)
    return config

