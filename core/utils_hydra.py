import os

from omegaconf import OmegaConf
import logging 
from pathlib import Path

_log = logging.getLogger(Path(__file__).stem)


def register_resolvers():
    for name, resolver in resolvers.items():
        if not OmegaConf.has_resolver(name):
            OmegaConf.register_new_resolver(name, resolver)
        else:
            _log.warning(f"Resolver {name} already registered!")
        

def _resolve_credentials(key):
    env_mapping = {
        "qdrant_host": "QDRANT_HOST",
        "qdrant_api_key": "QDRANT__SERVICE__API_KEY",
        "github_token": "GITHUB_TOKEN",
        "jina_api_key": "JINA_API_KEY",
        "openai_api_key": "OPENAI_API_KEY",
    }
    defaults = {
        "qdrant_host": "qdrant",
    }
    if key in env_mapping:
        return os.getenv(env_mapping[key], defaults.get(key, None))
    raise KeyError(f"Unknown credential: {key}")


resolvers = {
    "credentials": _resolve_credentials
}
