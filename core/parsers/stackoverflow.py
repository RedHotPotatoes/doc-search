import logging
import pprint
from dataclasses import asdict
from pathlib import Path
from typing import List

import pretty_logging
import requests
from bs4 import BeautifulSoup, NavigableString, Tag

from core.data_structures import (CodeBlock, Comment, Data, Image, Lists,
                                PlainText, StackOverflowAnswer,
                                StackOverflowDocument, StackOverflowQuestion,
                                Table)
from core.status_codes import HttpStatusCode

_log = logging.getLogger(Path(__file__).stem)


def parse_stackoverflow_question_page(
    html: str,
) -> StackOverflowDocument:
    soup = BeautifulSoup(html, "html.parser")
    title = parse_title(soup)
    question = parse_question(soup)
    answers = parse_answers(soup)
    return StackOverflowDocument(title=title, question=question, answers=answers)


def parse_title(soup: BeautifulSoup) -> str:
    question_header_div = soup.find("div", id="question-header")
    title_div = question_header_div.find("h1", itemprop="name")
    title = title_div.get_text()
    return title


def parse_question(soup: BeautifulSoup) -> StackOverflowQuestion:
    username_div = soup.find("div", class_="user-details", itemprop="author")
    username = username_div.find("a") 
    if username is None:
        username = username_div.find("span")
    username = username.get_text()

    question_div = soup.find("div", class_="question")
    post_div = question_div.find("div", class_="s-prose js-post-body")

    paragraphs = parse_paragraphs(post_div)
    comments = parse_comments(question_div)
    tags = parse_tags(question_div)
    return StackOverflowQuestion(
        username=username, question=paragraphs, comments=comments, tags=tags
    )


def parse_tags(question_div: Tag | NavigableString) -> List[str]:
    return [tag.get_text() for tag in question_div.find_all("a", class_="post-tag")]


def parse_answers(soup: BeautifulSoup) -> List[StackOverflowAnswer]:
    answers_div = soup.find_all("div", class_="answer")
    return [parse_answer(answer) for answer in answers_div]


def parse_answer(answer_div: Tag | NavigableString) -> StackOverflowAnswer:
    username_div = answer_div.find("div", class_="user-details", itemprop="author")
    if username_div is None:
        username = "not specified"
    else:
        username = username_div.find("a")
        if username is None:
            username = username_div.find("span")
        username = username.get_text()

    post_div = answer_div.find("div", class_="s-prose js-post-body")
    paragraphs = parse_paragraphs(post_div)
    comments = parse_comments(answer_div)
    votes = parse_num_votes(answer_div)
    return StackOverflowAnswer(username=username, answer=paragraphs, votes=votes, comments=comments)


def _parse_subtree(root: Tag | NavigableString) -> str:
    if isinstance(root, NavigableString):
        return root.get_text()
    return "".join(_parse_subtree(child) for child in root.children)


def _code_block_handler(node: Tag) -> CodeBlock:
    code_node = node.find("code")
    language = None 
    if "class" in code_node.attrs:
        for value in code_node["class"]:
            if value.startswith("language-"):
                language = value[9:]
                break
    code = []
    for child in code_node.children:
        if not isinstance(child, NavigableString):
            code.append(_parse_subtree(child))
        else:
            code.append(child.get_text())
    code_text = "".join(code)
    return CodeBlock(code_text, language)


def _table_handler(node: Tag) -> Table:
    table_div = node.find("table")
    headers = [header.get_text() for header in table_div.find_all("th")]
    rows = [[cell.get_text() for cell in row.find_all("td")] for row in table_div.find_all("tr")]
    return Table(headers=headers, rows=rows)


def _plain_text_handler(node: Tag) -> PlainText:
    return PlainText(node.get_text())


def _lists_handler(node: Tag) -> Lists:
    items = [item.get_text() for item in node.find_all("li")]
    return Lists(items)


def _image_handler(node: Tag) -> Image:
    return Image(link=node.get("src"), alt_text=node.get("alt"))


def parse_paragraphs(post_div: Tag | NavigableString) -> List[Data]:
    handler_map = {
        ("pre", "code"): _code_block_handler,
        ("div", "table"): _table_handler,
        "p": _plain_text_handler,
        "img": _image_handler,
        "ul": _lists_handler,
    }
    def filter_fn(node: Tag | NavigableString) -> bool:
        result = node.name in handler_map
        if not result and not isinstance(node, NavigableString):
            for node_ch in node.children:
                if (node.name, node_ch.name) in handler_map:
                    return True 
        return result

    def apply_handler(node: Tag | NavigableString) -> Data | None:
        if node.name in handler_map:
            return handler_map[node.name](node)
        for node_ch in node.children:
            if (node.name, node_ch.name) in handler_map:
                return handler_map[(node.name, node_ch.name)](node)
        return 

    nodes = filter(filter_fn, post_div.children)
    return [apply_handler(node) for node in nodes]


def parse_comments(soup: Tag | NavigableString) -> List[str]:
    comments_div = soup.find_all("div", class_="comment-body")
    comments = []
    for comment in comments_div:
        username = comment.find("a", class_="comment-user")
        if username is None:
            username = comment.find("span", class_="comment-user")
        comment_text = comment.find("span", class_="comment-copy")
        comments.append(Comment(text=comment_text.get_text(), username=username.get_text()))
    return comments


def parse_num_votes(soup: Tag | NavigableString) -> int:
    return int(soup.find("div", class_="js-vote-count").get_text())


if __name__ == "__main__":
    """
        python -m core.parsers.stackoverflow
    """
    pretty_logging.setup(logging.INFO)

    url = "https://stackoverflow.com/questions/11227809/why-is-processing-a-sorted-array-faster-than-an-unsorted-arrays"
    response = requests.get(url)
    status_code = HttpStatusCode(response.status_code)
    if status_code != HttpStatusCode.OK:
        _log.warning(f"Failed to fetch data from {url}")
        _log.warning(f"Status code: {status_code}")
    else:
        doc = parse_stackoverflow_question_page(response.content)
        parsed_doc = pprint.pformat(asdict(doc))
        _log.info(f"\n{parsed_doc}")
