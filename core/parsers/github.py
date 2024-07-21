from bs4 import BeautifulSoup, NavigableString, Tag
from markdownify import markdownify

from core.data_structures import GithubIssueComment, GithubIssueDocument


def parse_title(soup: BeautifulSoup) -> str:
    title_tag = soup.find("bdi", class_="js-issue-title")
    return title_tag.text.strip() if title_tag else "Unknown"


def parse_comment_body(comment_div: Tag | NavigableString) -> str:
    comment_body_div = comment_div.find("td", class_="comment-body")
    if comment_body_div is None:
        return ""

    result = []
    for paragraph in comment_body_div.children:
        paragraph_str = str(paragraph)
        if not paragraph_str.isspace():
            paragraph_md = markdownify(paragraph_str, heading_style="ATX")
            result.append(paragraph_md)
    return "".join(result)


def parse_author(comment_div: Tag | NavigableString) -> str:
    author_div = comment_div.find("a", class_="author")
    return author_div.text.strip() if author_div else "Unknown"


def parse_timestamp(comment_div: Tag | NavigableString) -> str:
    timestamp_tag = comment_div.find("relative-time")
    return timestamp_tag["datetime"] if timestamp_tag else "Unknown"


def parse_reactions(comment_div: Tag | NavigableString) -> dict[str, int]:
    reactions_div = comment_div.find("div", class_="comment-reactions")
    if reactions_div is None:
        return {}

    reactions = {}
    reaction_buttons = reactions_div.find_all("button", class_="btn-link")
    for button in reaction_buttons:
        reaction_type = button["value"].split()[0]
        reaction_count = int(button.find("span").text.strip())
        reactions[reaction_type] = reaction_count
    return reactions


def parse_github_issue_page(html_file: str) -> GithubIssueDocument:
    soup = BeautifulSoup(html_file, "lxml")
    comments_data = []
    title = parse_title(soup)
    comments_divs = soup.find_all("div", class_="timeline-comment")
    for comment_div in comments_divs:
        author = parse_author(comment_div)
        timestamp = parse_timestamp(comment_div)
        comment_text = parse_comment_body(comment_div)
        reactions = parse_reactions(comment_div)

        comments_data.append(
            GithubIssueComment(
                author=author,
                text=comment_text,
                reactions=reactions,
                timestamp=timestamp,
            )
        )
    return GithubIssueDocument(
        title=title, question=comments_data[0], answers=comments_data[1:]
    )
