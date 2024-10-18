import json
import shutil
from pathlib import Path

import requests
from bs4 import BeautifulSoup, NavigableString, Tag

from core.data_structures import GithubIssueComment, GithubIssueDocument
from core.utils_md import ignore_images_converter as md


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
            paragraph_md = md(paragraph_str, heading_style="ATX")
            result.append(paragraph_md)
    return "".join(result)


def parse_author(comment_div: Tag | NavigableString) -> str:
    author_div = comment_div.find("a", class_="author")
    return author_div.text.strip() if author_div else "Unknown"


def parse_timestamp(comment_div: Tag | NavigableString) -> str:
    timestamp_tag = comment_div.find_all("relative-time")
    if not timestamp_tag:
        return "Unknown Time"
    return timestamp_tag[-1]["datetime"]


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


def parse_comment(comment_div: Tag) -> GithubIssueComment:
    author = parse_author(comment_div)
    timestamp = parse_timestamp(comment_div)
    comment_text = parse_comment_body(comment_div)
    reactions = parse_reactions(comment_div)
    return GithubIssueComment(
        author=author,
        text=comment_text,
        reactions=reactions,
        timestamp=timestamp,
    )


def parse_github_issue_from_react_script(soup: BeautifulSoup) -> GithubIssueDocument:
    def get_issue(data: dict):
        if "preloadedQueries" not in data:
            return
        preloaded_queries = data["preloadedQueries"]
        if len(preloaded_queries) == 0:
            return
        query = preloaded_queries[0]
        if not (
            (result := query.get("result", None))
            and (res_data := result.get("data", None))
            and (repository := res_data.get("repository", None))
            and (issue := repository.get("issue", None))
        ):
            return
        return issue

    def get_reactions(issue: dict) -> dict[str, int]:
        reactions = {}
        for group in issue["reactionGroups"]:
            count = group["reactors"]["totalCount"]
            if count > 0:
                reactions[group["content"]] = count
        return reactions

    react_div = soup.find("react-app")
    if react_div is None:
        raise ValueError("React div not found")

    script_div = react_div.find("script")
    if script_div is None:
        raise ValueError("Script div not found")

    data = json.loads(script_div.text)
    if "payload" not in data:
        raise ValueError("Payload not found in script data")

    issue = get_issue(data["payload"])
    if issue is None:
        raise ValueError("Issue not found in payload data")

    title = issue["title"]
    question = GithubIssueComment(
        author=issue["author"]["login"],
        text=md(issue["bodyHTML"]),
        reactions=get_reactions(issue),
        timestamp=issue["createdAt"],
    )
    comments = issue.get("frontTimeline", {}).get("edges", None)
    if comments is None:
        raise ValueError("Comments not found in issue data")
    comments = [
        comment["node"]
        for comment in comments
        if comment["node"]["__typename"] == "IssueComment"
    ]

    answers = [
        GithubIssueComment(
            author=comment["author"]["login"],
            text=md(comment["bodyHTML"]),
            reactions=get_reactions(comment),
            timestamp=comment["createdAt"],
        )
        for comment in comments
    ]
    return GithubIssueDocument(title=title, question=question, answers=answers)


def parse_github_issue_page(html_file: str) -> GithubIssueDocument:
    soup = BeautifulSoup(html_file, "lxml")

    # The issue pages from the Microsoft repository (and possibly others) 
    # have a different structure than the ones from other repositories. 
    # For the MS pages, the data is parsed from react-app div.
    # The data from MS pages is usually incomplete for issues with many comments :(
    comments_divs = soup.find_all("div", class_="timeline-comment")
    if not comments_divs:
        return parse_github_issue_from_react_script(soup)

    title = parse_title(soup)
    comments_data = [parse_comment(comment_div) for comment_div in comments_divs]
    return GithubIssueDocument(
        title=title, question=comments_data[0], answers=comments_data[1:]
    )


if __name__ == "__main__":
    urls = [
        "https://github.com/mcfletch/pyopengl/issues/10",
        "https://github.com/microsoft/vscode/issues/231399",
        "https://github.com/microsoft/TypeScript/issues/50009"
    ]
    force_remove = True

    output_dir = Path("parsers_output") / "github_issues"
    if output_dir.exists():
        if not force_remove:
            raise FileExistsError("Output directory already exists")
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)

    for url in urls:
        response = requests.get(url)
        if response.status_code != 200:
            raise ValueError(f"Failed to fetch {url}")

        document = parse_github_issue_page(response.text)
        document_md = document.to_markdown()
        document_name = url.replace("https://github.com/", "").replace("/", "_")
        document_name = f"{document_name}.md"

        with open(output_dir / document_name, "w") as f:
            f.write(document_md)
