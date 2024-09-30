import re
import shutil
from pathlib import Path

import requests
from bs4 import BeautifulSoup, Tag

from core.data_structures import (DiscourseComment, DiscourseDocument,
                                  DiscourseMessage)
from core.utils_md import ignore_images_converter as md


def parse_discourse_page(html_content: str) -> DiscourseDocument:
    soup = BeautifulSoup(html_content, "html.parser")

    title = soup.find("title").text.split(" - ")[0].strip()

    comment_divs = soup.find_all("div", class_="topic-body crawler-post")
    question = parse_message(comment_divs[0])

    comments = []
    for comment_div in comment_divs[1:]:
        comment = parse_comment(comment_div)
        comments.append(comment)
    return DiscourseDocument(title=title, question=question, comments=comments)


def parse_message(message_div: Tag) -> DiscourseMessage:
    author = (
        message_div.find("span", class_="creator")
        .find("span", itemprop="name")
        .text.strip()
    )
    text = md(message_div.find("div", class_="post").decode_contents())
    timestamp = message_div.find("time")["datetime"]
    return DiscourseMessage(
        author=author, text=text, timestamp=timestamp,
    )


def parse_comment(comment_div: Tag) -> DiscourseComment:
    message = parse_message(comment_div)
    return DiscourseComment(message=message)


if __name__ == "__main__":
    urls = [
        "https://discuss.pytorch.org/t/implementation-of-swish-a-self-gated-activation-function/8813",
        "https://discuss.ai.google.dev/t/tensorflow-2-17-saving-custom-model-does-not-work-for-me/37971",
        "https://discuss.huggingface.co/t/the-effect-of-padding-side/67188",
        "https://discuss.kubernetes.io/t/microk8s-v1-23-released/18357",
        "https://forums.docker.com/t/expose-specific-interfcae-to-container/143659/",
        "https://forum.djangoproject.com/t/handling-multiple-forms-on-a-single-page-without-full-page-reload/33440",
        "https://discuss.ray.io/t/about-the-ray-libraries-data-train-tune-serve-category/7098"
    ]
    force_remove = True

    output_dir = Path("parsers_output") / "discourse"
    if output_dir.exists():
        if not force_remove:
            raise FileExistsError("Output directory already exists")
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)

    for url in urls:
        response = requests.get(url)
        if response.status_code != 200:
            raise ValueError(f"Failed to fetch {url}")

        document = parse_discourse_page(response.text)
        document_md = document.to_markdown()

        document_name = re.sub(r'^https://.*?/t/', '', url).replace("/", "_")
        document_name = f"{document_name}.md"

        with open(output_dir / document_name, "w") as f:
            f.write(document_md)
