"""
One-time script to migrate schemes.json into MongoDB.
Run this once: python migrate_json_to_mongo.py
"""
import json
import os
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

MONGODB_URI = os.environ.get("MONGODB_URI")
DB_NAME = "janseva_db"
COLLECTION_NAME = "schemes"


def migrate():
    if not MONGODB_URI:
        print("ERROR: MONGODB_URI not found in .env")
        return

    client = MongoClient(MONGODB_URI)
    db = client[DB_NAME]
    collection = db[COLLECTION_NAME]

    json_path = os.path.join(os.path.dirname(__file__), "schemes.json")
    with open(json_path, "r", encoding="utf-8") as f:
        schemes = json.load(f)

    # Clear existing data first, so re-running this script doesn't create duplicates
    collection.delete_many({})

    result = collection.insert_many(schemes)
    print(f"Successfully migrated {len(result.inserted_ids)} schemes to MongoDB.")

    client.close()


if __name__ == "__main__":
    migrate()
    