db = db.getSiblingDB("github_crawl");
db.createCollection("repositories");
db.repositories.createIndex({ full_name: 1 }, { unique: true });
db.repositories.insertMany([
    {
        "id": -1,
        "name": "repo_name",
        "full_name": "user/repo_name",
        "private": false,
        "fork": false,
        "url": "https://api.github.com/repos/user/repo_name",
        "html_url": "https://github.com/repos/user/repo_name"
    },
]);
