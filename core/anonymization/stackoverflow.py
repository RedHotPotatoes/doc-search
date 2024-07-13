from core.data_structures import StackOverflowDocument


def _get_username_mapping(document: StackOverflowDocument) -> dict[str, str]:
    usernames = set()
    author = document.question.username
    usernames.add(author)

    for comment in document.question.comments:
        usernames.add(comment.username)

        # search for @username in comment
        for word in comment.text.split():
            if word.startswith("@"):
                usernames.add(word[1:].rstrip(",._-/"))
    for answer in document.answers:
        usernames.add(answer.username)
        for comment in answer.comments:
            usernames.add(comment.username)
            for word in comment.text.split():
                if word.startswith("@"):
                    usernames.add(word[1:].rstrip(",._-/"))
    
    username_mapping = {username: f"User {i}" for i, username in enumerate(usernames) }
    username_mapping[author] = "Question Author" 
    return username_mapping


def replace_occurences(text: str, mapping: dict[str, str]) -> str:
    text_split = text.split()

    # CAN_BE_OPTIMIZED
    for index in range(len(text_split)):
        word = text_split[index]
        for key in mapping:
            if key in word:
                text_split[index] = word.replace(key, mapping[key])
    return " ".join(text_split)


def anonymize_stackoverflow_document(document: StackOverflowDocument) -> StackOverflowDocument:
    username_mapping = _get_username_mapping(document)

    document.question.username = username_mapping[document.question.username]
    for comment in document.question.comments:
        comment.username = username_mapping[comment.username]
    for answer in document.answers:
        answer.username = username_mapping[answer.username]
        for comment in answer.comments:
            comment.username = username_mapping[comment.username]
    
    for answer in document.answers:
        for data in answer.answer:
            if hasattr(data, "text"):
                data.text = replace_occurences(data.text, username_mapping)
        for comment in answer.comments:
            comment.text = replace_occurences(comment.text, username_mapping)

    for data in document.question.question:
        if hasattr(data, "text"):
            data.text = replace_occurences(data.text, username_mapping)
    for comment in document.question.comments:
        comment.text = replace_occurences(comment.text, username_mapping)

    return document
