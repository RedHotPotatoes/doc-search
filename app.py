from flask import Flask
from pymongo import MongoClient
import os

app = Flask(__name__)

mongo_host = os.getenv("MONGODB_HOST", "mongodb")
mongo_port = os.getenv("MONGODB_PORT", 27017)

client = MongoClient(
    f"mongodb://{mongo_host}:{mongo_port}/",
    username=os.getenv("MONGODB_ADMIN_USER"),
    password=os.getenv("MONGODB_ADMIN_PASS"),
    authSource="admin",
)

@app.route("/")
def startup_page():
    databases = client.list_database_names()
    return f"Databases: {databases}"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5009)
