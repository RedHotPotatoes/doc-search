import shutil
from pathlib import Path
from typing import Dict, List

import requests
from bs4 import BeautifulSoup, Tag

from core.data_structures import (GithubDiscussionComment,
                                  GithubDiscussionDocument,
                                  GithubDiscussionMessage)
from core.utils_md import ignore_images_converter as md


def parse_title(soup: BeautifulSoup) -> str:
    title_tag = soup.find("span", class_="js-issue-title")
    return title_tag.text.strip() if title_tag else "Unknown"


def parse_author(div: Tag) -> str:
    author_tag = div.find("a", {"class": "author"})
    return author_tag.text.strip() if author_tag else "Unknown Author"


def parse_timestamp(div: Tag) -> str:
    timestamp_tag = div.find_all("relative-time")
    if not timestamp_tag:
        return "Unknown Time"
    return timestamp_tag[-1]["datetime"]


def parse_reactions(div: Tag) -> Dict[str, int]:
    reactions_div = div.find("div", {"class": "js-comment-reactions-options"})
    if reactions_div is None:
        return {}

    reactions = {}
    reaction_buttons = reactions_div.find_all("button", {"class": "btn-link"})
    for button in reaction_buttons:
        reaction_type = button["value"].split()[0]
        reaction_count = int(button.find("span").text.strip())
        reactions[reaction_type] = reaction_count
    return reactions


def parse_comment_body(comment_div: Tag) -> str:
    comment_body_div = comment_div.find("td", class_="comment-body")
    if comment_body_div is None:
        return ""

    result = []
    for paragraph in comment_body_div.children:
        paragraph_str = str(paragraph)
        if not paragraph_str.isspace():
            paragraph_md = md(paragraph_str, heading_style="ATX")
            result.append(paragraph_md)
    return "".join(result)


def parse_marked_as_answer(div: Tag) -> bool:
    return bool(div.find("section", {"aria-label": "Marked as Answer"})) 


def parse_question(question_div: Tag) -> GithubDiscussionMessage:
    text = parse_comment_body(question_div)

    header = question_div.find("h2", class_="timeline-comment-header-text")
    author = header.find("span", class_="Truncate-text").text.strip()
    timestamp = parse_timestamp(header)
    text = parse_comment_body(question_div)
    reactions = parse_reactions(question_div)

    return GithubDiscussionMessage(
        text=text,
        author=author,
        timestamp=timestamp,
        reactions=reactions,
    )


def parse_replies(replies_div: Tag) -> List[GithubDiscussionMessage]:
    replies = []
    reply_tags = replies_div.find_all("div", {"class": "js-comment-container"})
    for reply_tag in reply_tags:
        reply = GithubDiscussionMessage(
            text=parse_comment_body(reply_tag),
            author=parse_author(reply_tag),
            timestamp=parse_timestamp(reply_tag),
            reactions=parse_reactions(reply_tag),
            marked_as_answer=parse_marked_as_answer(reply_tag) 
        )
        replies.append(reply)
    return replies


def parse_comments(comment_divs: list[Tag]) -> List[GithubDiscussionComment]:
    comments = []
    for comment_div in comment_divs:
        header = comment_div.find("h3", class_="timeline-comment-header-text")
        author = header.find("span", class_="Truncate-text").text.strip()
        timestamp = parse_timestamp(header)
        text = parse_comment_body(comment_div)
        reactions = parse_reactions(comment_div)

        replies_div = comment_div.find("div", {"data-child-comments": True})
        if replies_div:
            replies = parse_replies(replies_div)
        else:
            replies = []

        marked_as_answer = False
        if not any(reply.marked_as_answer for reply in replies):
            marked_as_answer = parse_marked_as_answer(comment_div)

        comments.append(
            GithubDiscussionComment(
                message=GithubDiscussionMessage(
                    text=text,
                    author=author,
                    timestamp=timestamp,
                    reactions=reactions,
                    marked_as_answer=marked_as_answer
                ),
                replies=replies,
            )
        )
    return comments


def parse_github_discussion_page(html_file: str) -> GithubDiscussionDocument:
    soup = BeautifulSoup(html_file, "html.parser")
    title = parse_title(soup)

    discussion = soup.find("div", {"class": "js-discussion"})
    comment_tags = discussion.find_all("div", {"class": "discussion-timeline-item"})

    question = parse_question(comment_tags[0])
    comments = parse_comments(comment_tags[1:])
    return GithubDiscussionDocument(title=title, question=question, comments=comments)


if __name__ == "__main__":
    urls = [
        "https://github.com/remarkablemark/html-react-parser/discussions/1094",
        "https://github.com/spring-projects/spring-kafka/discussions/2915"
    ]
    force_remove = True

    output_dir = Path("parsers_output") / "github_discussions"
    if output_dir.exists(): 
        if not force_remove:
            raise FileExistsError("Output directory already exists")
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)
    
    for url in urls:
        response = requests.get(url)
        if response.status_code != 200:
            raise ValueError(f"Failed to fetch {url}")

        document = parse_github_discussion_page(response.text)
        document_md = document.to_markdown()
        document_name = url.replace("https://github.com/", "").replace("/", "_")
        document_name = f"{document_name}.md"

        with open(output_dir / document_name, "w") as f:
            f.write(document_md)
