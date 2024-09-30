from typing import Callable
import re

from core.parsers.discourse import parse_discourse_page
from core.parsers.github_discussions import parse_github_discussion_page
from core.parsers.github_issues import parse_github_issue_page
from core.parsers.stackexchange import parse_stackexchange_page


def _discourse_test(url: str):
    """
        The discourse page is of format 
        https://{discuss or forum}.{site name}/t/{post title}/{post id}
    """
    return re.match(r"^https://(discuss|forum)\..+?/t/.+?/.+?$", url) is not None


def _github_issue_test(url: str):
    """
        The github issue page is of format
        https://github.com/{user}/{repo}/issues/{issue number}
    """
    return re.match(r"^https://github\.com/.+?/.+?/issues/.+?$", url) is not None


def _github_discussion_test(url: str):
    """
        The github discussion page is of format
        https://github.com/{user}/{repo}/discussions/{discussion number}
    """
    return re.match(r"^https://github\.com/.+?/.+?/discussions/.+?$", url) is not None


def _stackexchange_test(url: str):
    """
        The stackexchange page is either of format
        https://{site name}.stackexchange.com/questions/{question id}/{question title}
        or
        https://stackoverflow.com/questions/{question id}
    """
    return re.match(r"^https://.+?\.stackexchange\.com/questions/.+?/.+?$", url) is not None or \
           re.match(r"^https://stackoverflow\.com/questions/.+?$", url) is not None


_parser_mapping = (
    (_stackexchange_test, parse_stackexchange_page),
    (_github_issue_test, parse_github_issue_page),
    (_github_discussion_test, parse_github_discussion_page),
    (_discourse_test, parse_discourse_page),
)

def get_parser(url: str) -> Callable:
    for test, parser in _parser_mapping:
        if test(url):
            return parser
    return 
