import datetime
from dataclasses import dataclass
from datetime import datetime


class MarkdownSerializable:
    def to_markdown(self) -> str:
        raise NotImplementedError


class JsonSerializable:
    def to_json(self) -> str:
        raise NotImplementedError


"""
    Stack Exchange Data Structures
"""


@dataclass
class StackExchangeComment:
    text: str
    creation_date: str
    author: str


@dataclass
class StackExchangePost:
    author: str
    text: str
    comments: list[StackExchangeComment]
    creation_date: str
    last_edit_date: str
    tags: list[str]
    vote_count: int


@dataclass
class StackExchangeDocument(MarkdownSerializable, JsonSerializable):
    title: str
    question: StackExchangePost
    answers: list[StackExchangePost]

    def to_json(self) -> str:
        return {
            "title": self.title,
            "question": {
                "author": self.question.author,
                "text": self.question.text,
                "creation_date": self.question.creation_date,
                "last_edit_date": self.question.last_edit_date,
                "tags": self.question.tags,
                "vote_count": self.question.vote_count,
                "comments": [
                    {
                        "text": comment.text,
                        "creation_date": comment.creation_date,
                        "author": comment.author,
                    }
                    for comment in self.question.comments
                ],
            },
            "answers": [
                {
                    "author": answer.author,
                    "text": answer.text,
                    "creation_date": answer.creation_date,
                    "last_edit_date": answer.last_edit_date,
                    "tags": answer.tags,
                    "vote_count": answer.vote_count,
                    "comments": [
                        {
                            "text": comment.text,
                            "creation_date": comment.creation_date,
                            "author": comment.author,
                        }
                        for comment in answer.comments
                    ],
                }
                for answer in self.answers
            ],
        }

    def to_markdown(self) -> str:
        def format_date(date: str) -> str:
            if date.endswith("Z"):
                return datetime.strptime(date, "%Y-%m-%d %H:%M:%SZ").strftime("%d %b %Y")
            return date

        def format_comment(comment: StackExchangeComment) -> str:
            return f"""#### {comment.author} - {format_date(comment.creation_date)}
{comment.text}
"""

        def format_post(post: StackExchangePost) -> str:
            comments = "\n".join([format_comment(comment) for comment in post.comments])
            return f"""### {post.author} - {format_date(post.creation_date)}. Number of votes: {post.vote_count}
{post.text}

**Comments:**
{comments}

**Tags:** {", ".join(post.tags) or "No tags"}
"""

        answers = "\n".join([format_post(answer) for answer in self.answers])
        return f"""# {self.title}

## Question
{format_post(self.question)}

## Answers
{answers}
"""


""" 
    Github Issues Data Structures
"""


@dataclass
class GithubIssueComment:
    author: str
    text: str
    reactions: dict[str, int]
    timestamp: str


@dataclass
class GithubIssueDocument(MarkdownSerializable, JsonSerializable):
    title: str
    question: GithubIssueComment
    answers: list[GithubIssueComment]

    def to_json(self) -> str:
        return {
            "title": self.title,
            "question": {
                "author": self.question.author,
                "text": self.question.text,
                "reactions": self.question.reactions,
                "timestamp": self.question.timestamp,
            },
            "answers": [
                {
                    "author": answer.author,
                    "text": answer.text,
                    "reactions": answer.reactions,
                    "timestamp": answer.timestamp,
                }
                for answer in self.answers
            ],
        }

    def to_markdown(self) -> str:
        def format_comment(comment: GithubIssueComment) -> str:
            reactions = (
                ", ".join(
                    [f"{emoji}: {count}" for emoji, count in comment.reactions.items()]
                )
                if comment.reactions
                else "No reactions"
            )
            timestamp = datetime.strptime(
                comment.timestamp, "%Y-%m-%dT%H:%M:%SZ"
            ).strftime("%d %b %Y")

            return f"""### {comment.author} - {timestamp}
{comment.text}
**Reactions:** {reactions}
"""

        answers = "\n".join([format_comment(answer) for answer in self.answers])
        return f"""# {self.title}

## Question
{format_comment(self.question)}

## Answers
{answers}
"""


""" 
    Github Discussions Data Structures
"""


@dataclass
class GithubDiscussionMessage:
    text: str
    author: str
    timestamp: str
    reactions: dict[str, int]
    marked_as_answer: bool = False


@dataclass
class GithubDiscussionComment:
    message: GithubDiscussionMessage
    replies: list[GithubDiscussionMessage]


@dataclass
class GithubDiscussionDocument(MarkdownSerializable, JsonSerializable):
    title: str
    question: GithubDiscussionMessage
    comments: list[GithubDiscussionComment]

    def to_json(self) -> str:
        return {
            "title": self.title,
            "question": {
                "text": self.question.text,
                "author": self.question.author,
                "timestamp": self.question.timestamp,
                "reactions": self.question.reactions,
            },
            "comments": [
                {
                    "message": {
                        "text": comment.message.text,
                        "author": comment.message.author,
                        "timestamp": comment.message.timestamp,
                        "reactions": comment.message.reactions,
                    },
                    "replies": [
                        {
                            "text": reply.text,
                            "author": reply.author,
                            "timestamp": reply.timestamp,
                            "reactions": reply.reactions,
                        }
                        for reply in comment.replies
                    ],
                }
                for comment in self.comments
            ],
        }

    def to_markdown(self) -> str:
        def format_message(
            message: GithubDiscussionMessage, is_list_item: bool = False
        ) -> str:
            answer_marker = " **Marked as answer**" if message.marked_as_answer else ""
            if len(message.reactions) == 0:
                reactions = "No reactions"
            else:
                reactions = ", ".join(
                    [f"{emoji}: {count}" for emoji, count in message.reactions.items()]
                )

            if is_list_item:
                title_prefix = " - "
                newline = "\n   "
                mesage_text = message.text.replace("\n", f"\n   ")
            else:
                title_prefix = ""
                newline = "\n"
                mesage_text = message.text
            timestamp = datetime.strptime(
                message.timestamp, "%Y-%m-%dT%H:%M:%SZ"
            ).strftime("%d %b %Y")

            header = f"{title_prefix}### {message.author} - {timestamp}{answer_marker}"
            return f"{header}{newline}{mesage_text}{newline}{'**Reactions:**'} {reactions}\n"

        def format_replies(replies: list[GithubDiscussionMessage]) -> str:
            if len(replies) == 0:
                return ""
            replies = "".join(
                [format_message(reply, is_list_item=True) for reply in replies]
            )
            return replies

        def format_comment(comment: GithubDiscussionComment) -> str:
            replies = format_replies(comment.replies)
            comment = f"{format_message(comment.message)}\n{'**Replies:**'}\n{replies}"
            return comment

        comments = "\n".join([format_comment(comment) for comment in self.comments])

        return f"""# {self.title}

## Question
{format_message(self.question)}

## Answers
{comments}
"""


"""
    Discourse based websites Data Structures
"""


@dataclass
class DiscourseMessage:
    author: str
    text: str
    timestamp: str


@dataclass
class DiscourseComment:
    message: DiscourseMessage


@dataclass
class DiscourseDocument(MarkdownSerializable, JsonSerializable):
    title: str
    question: DiscourseMessage
    comments: list[DiscourseComment]

    def to_json(self) -> str:
        return {
            "title": self.title,
            "question": {
                "author": self.question.author,
                "text": self.question.text,
                "timestamp": self.question.timestamp,
            },
            "comments": [
                {
                    "message": {
                        "author": comment.message.author,
                        "text": comment.message.text,
                        "timestamp": comment.message.timestamp,
                    }
                }
                for comment in self.comments
            ],
        }

    def to_markdown(self) -> str:
        def format_message(
            message: DiscourseMessage, is_list_item: bool = False
        ) -> str:
            if is_list_item:
                title_prefix = " - "
                newline = "\n   "
                mesage_text = message.text.replace("\n", f"\n   ")
            else:
                title_prefix = ""
                newline = "\n"
                mesage_text = message.text
            timestamp = datetime.strptime(
                message.timestamp, "%Y-%m-%dT%H:%M:%SZ"
            ).strftime("%d %b %Y")

            header = f"{title_prefix}### {message.author} - {timestamp}"
            return f"{header}{newline}{mesage_text}{newline}\n"

        def format_comment(comment: DiscourseComment) -> str:
            comment = f"{format_message(comment.message)}"
            return comment

        comments = "\n".join([format_comment(comment) for comment in self.comments])
        return f"""# {self.title}

## Question
{format_message(self.question)}

## Comments
{comments}
"""
