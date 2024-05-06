from typing import Any, Dict


class KeyFormatter:
    def __call__(self, key: str) -> str:
        raise NotImplementedError
    
    def _get_params(self) -> Dict[str, Any]:
        raise NotImplementedError
    
    def to_config(self) -> dict:
        base_config = {
            "type": self.__class__.__name__
        }
        base_config.update(self._get_params())
        return base_config


class StackOverflowKeyFormatter(KeyFormatter):
    def __init__(self, pattern: str = "stackoverflow_question") -> None:
        self._pattern = pattern

    def __call__(self, link: str) -> str:
        question_id = link.split("/")[-2]
        return f"{self._pattern}_{question_id}"
    
    def _get_params(self) -> Dict:
        return {"pattern": self._pattern}


def from_config(config: dict) -> KeyFormatter:
    formatter_type = config.pop("type")
    if formatter_type == "StackOverflowKeyFormatter":
        return StackOverflowKeyFormatter(**config)
    raise ValueError(f"Unknown KeyFormatter type: {formatter_type}")
