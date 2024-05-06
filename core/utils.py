import requests


def search_stackoverflow(query):
    url = "https://api.stackexchange.com/2.2/search"
    params = {
        "order": "desc",
        "sort": "relevance",
        "intitle": query,
        "site": "stackoverflow",
    }
    response = requests.get(url, params=params).json()
    if "items" in response:
        return [item["link"] for item in response["items"]]
    return []
