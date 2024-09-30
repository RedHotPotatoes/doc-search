import re
import shutil
from pathlib import Path

import requests
from bs4 import BeautifulSoup, Tag

from core.data_structures import (StackExchangeComment, StackExchangeDocument,
                                  StackExchangePost)
from core.utils_md import ignore_images_converter as md


def parse_author_from_signature(signature_div: Tag) -> str:
    author_div = signature_div.find("div", class_="user-details", itemprop="author")
    if author_div is None:
        return "Unknown"
    return author_div.find("span", itemprop="name").text


def parse_creation_date_from_signature(signature_div: Tag) -> str:
    creation_date_span = signature_div.find("span", class_="relativetime")
    return creation_date_span["title"] if creation_date_span else "Unknown"


def parse_comment(comment_div: Tag) -> StackExchangeComment:
    author = (
        comment_div.find("a", class_="comment-user")
        or comment_div.find("span", class_="comment-user")
    ).text
    text = comment_div.find("span", class_="comment-copy").text
    creation_date = comment_div.find("span", class_="relativetime-clean")["title"]
    creation_date = creation_date.split(", ")[0]
    return StackExchangeComment(author=author, text=text, creation_date=creation_date)


def parse_stackexchange_post(
    post_div: Tag, post_type: str = "postcell"
) -> StackExchangePost:
    vote_count = int(post_div.find("div", itemprop="upvoteCount").text)

    post_cell_div = post_div.find("div", class_=post_type)
    text = md(post_cell_div.find("div", itemprop="text").decode_contents())
    tags = [tag.text for tag in post_cell_div.find_all("a", class_="post-tag")]

    signatures = post_cell_div.find_all("div", class_="post-signature")
    if len(signatures) == 2:
        edit_signature, author_signature = signatures
        last_edit_date = edit_signature.find("span", class_="relativetime")["title"]
    elif len(signatures) == 1:
        author_signature = signatures[0]
        last_edit_date = None
    else:
        raise ValueError("Invalid number of signatures. Expected either 1 or 2")

    creation_date = parse_creation_date_from_signature(author_signature)
    author = parse_author_from_signature(author_signature)
    comments = [
        parse_comment(comment) for comment in post_div.find_all("li", class_="comment")
    ]
    return StackExchangePost(
        author=author,
        text=text,
        comments=comments,
        tags=tags,
        vote_count=vote_count,
        creation_date=creation_date,
        last_edit_date=last_edit_date or creation_date,
    )


def parse_stackexchange_page(html_content: str) -> StackExchangeDocument:
    soup = BeautifulSoup(html_content, "html.parser")

    question_title = soup.find("a", class_="question-hyperlink").text
    question_div = soup.find("div", class_="question")
    question_post = parse_stackexchange_post(question_div)

    answers = []
    for answer in soup.find_all("div", class_="answer"):
        answer_post = parse_stackexchange_post(answer, post_type="answercell")
        answers.append(answer_post)
    return StackExchangeDocument(
        title=question_title,
        question=question_post,
        answers=answers,
    )


if __name__ == "__main__":
    urls = [
        "https://stackoverflow.com/questions/11227809/why-is-processing-a-sorted-array-faster-than-an-unsorted-arrays",
        "https://datascience.stackexchange.com/questions/103888/classification-when-the-classification-of-the-previous-itens-matter"
    ]
    force_remove = True

    output_dir = Path("parsers_output") / "stackexchange"
    if output_dir.exists():
        if not force_remove:
            raise FileExistsError("Output directory already exists")
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)

    for url in urls:
        response = requests.get(url)
        if response.status_code != 200:
            raise ValueError(f"Failed to fetch {url}")

        document = parse_stackexchange_page(response.text)
        document_md = document.to_markdown()

        document_name = re.sub(r"^https://.*?/questions/", "", url).replace("/", "_")
        document_name = f"{document_name}.md"

        with open(output_dir / document_name, "w") as f:
            f.write(document_md)
