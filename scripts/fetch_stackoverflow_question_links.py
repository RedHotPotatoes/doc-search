from typing import List
import pretty_logging
from pretty_logging import with_logger


class Worker:
    pass 


@with_logger
class StackOverflowQuestionsLinkFetcher:
    def __init__(self, workers: List[Worker]) -> None:
        pass

    def fetch_questions(self, verbose: bool = False) -> None:
        self._log.info("Fetching all StackOverflow questions...")

        headers = ...
        response = self._get_request(self.URL, headers=headers, params=self.PARAMS)
