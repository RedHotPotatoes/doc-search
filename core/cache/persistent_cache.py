import hashlib
import json
import pickle
import zlib
from collections import deque
from pathlib import Path
from typing import Any, Callable, Tuple

from pretty_logging import with_logger

import core.cache.key_formatters as key_formatters


def compress_string(text: str) -> bytes:
    return zlib.compress(text.encode())


def decompress_string(compressed_text: bytes) -> str:
    return zlib.decompress(compressed_text).decode()


def json_loader(path: str | Path) -> Any:
    with open(path, "r") as file:
        return json.load(file)


def json_saver(path: str | Path, document: Any) -> None:
    with open(path, "w") as file:
        json.dump(document, file)


def pickle_loader(path: str | Path, decompress: bool = True) -> Any:
    with open(path, "rb") as file:
        data = pickle.load(file)
    if decompress:
        return decompress_string(data)
    return data


def pickle_saver(path: str | Path, document: Any, compress: bool = True) -> None:
    with open(path, "wb") as file:
        data = compress_string(document) if compress else document
        pickle.dump(data, file)


def hash_string(text: str, hasher: Callable) -> str:
    return hasher(text.encode()).hexdigest()


class _MaxLengthDict:
    def __init__(self, max_length: int):
        if not isinstance(max_length, int) or max_length < 1:
            raise ValueError("max_length should be integer >= 1")
        self._max_length = max_length
        self._queue = deque(maxlen=max_length)
        self._dict = {}

    @property
    def max_length(self):
        return self._max_length

    def clear(self):
        self._queue.clear()
        self._dict.clear()

    def keys(self):
        return self._dict.keys()

    def values(self):
        return self._dict.values()

    def items(self):
        return self._dict.items()

    def __contains__(self, key):
        return key in self._dict

    def __setitem__(self, key, value):
        if key in self._dict:
            self._dict[key] = value
            return
        if len(self._queue) == self._max_length:
            oldest_key = self._queue.popleft()
            del self._dict[oldest_key]
        self._queue.append(key)
        self._dict[key] = value

    def __getitem__(self, key):
        return self._dict[key]

    def __repr__(self):
        return repr(self._dict)


@with_logger
class DocumentsPersistentCache:
    _loaders = {
        ".json": json_loader,
        ".pickle": pickle_loader,
        ".pkl": pickle_loader,
    }
    _savers = {
        ".json": json_saver,
        ".pickle": pickle_saver,
        ".pkl": pickle_saver,
    }
    _hashes = {
        "md5": hashlib.md5,
        "sha1": hashlib.sha1,
        "sha256": hashlib.sha256,
        "sha384": hashlib.sha384,
        "sha512": hashlib.sha512,
    }

    def __init__(
        self,
        cache_dir: str | Path,
        max_documents_in_memory: int = None,
        archive_type: str = ".json",
        hash_type: str = "sha256",
        key_formatter: key_formatters.KeyFormatter = None,
    ):
        if max_documents_in_memory is not None:
            if (
                not isinstance(max_documents_in_memory, int)
                or max_documents_in_memory < 1
            ):
                raise ValueError(
                    "max_documents_in_memory should be integer >= 1 or None"
                )
        if archive_type not in self._loaders:
            raise KeyError(
                f"Unsupported archive type: {archive_type}. Supported types: {self._loaders.keys()}"
            )
        if hash_type not in self._hashes:
            raise KeyError(
                f"Unsupported hash type: {hash_type}. Supported types: {self._hashes.keys()}"
            )
        self._cache_dir = Path(cache_dir)
        if self._cache_dir.exists() and not self._cache_dir.is_dir():
            raise ValueError(f"{self._cache_dir} is not a directory")
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._archive_type = archive_type
        self._max_documents_in_memory = max_documents_in_memory
        self._key_formatter = key_formatter

        self._hash_type = hash_type
        self._hash_algorithm = self._hashes[hash_type]
        self._loader = self._loaders[archive_type]
        self._saver = self._savers[archive_type]

        self._documents = (
            _MaxLengthDict(max_documents_in_memory)
            if max_documents_in_memory is not None
            else dict()
        )
        self._doc_hashes = self._glob_cache_files()
        self._create_config_file()

    def _parse_key(self, key: str) -> Tuple[str, str]:
        if self._key_formatter is not None:
            key = self._key_formatter(key)
        return key, hash_string(key, self._hash_algorithm)

    def _glob_cache_files(self):
        return {
            filename.stem for filename in self.cache_dir.glob(f"*{self._archive_type}")
        }

    def _create_config_file(self):
        config_file = self.cache_dir / "config.json"
        if config_file.exists():
            self._log.warning(
                "Config file already exists. The file will be overwritten."
            )
        config = {
            "max_documents_in_memory": self._max_documents_in_memory,
            "archive_type": self._archive_type,
            "hash_type": self._hash_type,
            "key_formatter": (
                self._key_formatter.to_config()
                if self._key_formatter is not None
                else None
            ),
        }
        with open(config_file, "w") as file:
            json.dump(config, file)

    def _load_document(self, path: str | Path) -> Any:
        return self._loader(path)

    def _save_document(self, key: str, document: Any) -> None:
        self._saver(key, document)

    def query_document(self, key_raw: str) -> Any | None:
        key, key_hash = self._parse_key(key_raw)
        if key_hash in self._doc_hashes:
            if key not in self._documents:
                document_path = self.cache_dir / f"{key_hash}{self._archive_type}"
                document = self._load_document(document_path)
                self._documents[key] = document
                return document
            return self._documents[key]
        return None

    def insert_document(self, key_raw: str, document: Any):
        key, key_hash = self._parse_key(key_raw)
        if key_hash in self._doc_hashes:
            self._log.warning(f"Document with key {key} already exists in cache")
        document_path = self.cache_dir / f"{key_hash}{self._archive_type}"
        self._save_document(document_path, document)
        self._doc_hashes.add(key_hash)
        if key in self._documents:
            self._documents[key] = document

    @property
    def cache_dir(self):
        return self._cache_dir

    def clear(self):
        try:
            for file in self.cache_dir.glob(f"*{self._archive_type}"):
                file.unlink()
            self._documents.clear()
            self._doc_hashes.clear()
        except (FileNotFoundError, NotADirectoryError, PermissionError, OSError) as e:
            self._log.warning(f"Failed to clear cache: {e}")

    def __len__(self) -> int:
        return len(self._doc_hashes)

    def __contains__(self, key_raw: str) -> bool:
        _, key_hash = self._parse_key(key_raw)
        return key_hash in self._doc_hashes
    
    @classmethod
    def from_config(cls, config_dir: str | Path):
        config_file = Path(config_dir) / "config.json"
        with open(config_file, "r") as file:
            config = json.load(file)
        return cls(
            cache_dir=Path(config_file).parent,
            max_documents_in_memory=config["max_documents_in_memory"],
            archive_type=config["archive_type"],
            hash_type=config["hash_type"],
            key_formatter=key_formatters.from_config(config["key_formatter"]),
        )
