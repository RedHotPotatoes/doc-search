import requests


def search_stackoverflow(query):
    url = "https://api.stackexchange.com/2.3/search/advanced"
    params = {
        "order": "desc",
        "sort": "relevance",
        "q": query,
        "site": "stackoverflow",
    }
    response = requests.get(url, params=params).json()
    if "items" in response:
        return [item["link"] for item in response["items"]]
    return []
