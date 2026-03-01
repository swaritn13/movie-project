import pymongo
from datetime import datetime

# 1. Connect to MongoDB (Standard local connection)
mongo_client = pymongo.MongoClient("mongodb://localhost:27017/")
db = mongo_client["movie_project_logs"]

# Define collections at the top level so all functions can see them
logs_collection = db["search_history"]
feedback_collection = db["user_feedback"]

def save_to_nosql(user_id, query, match_title, score):
    """Archives search events into MongoDB for scalability."""
    log_document = {
        "user_id": user_id,
        "query": query,
        "matched_movie": match_title,
        "ai_score": float(score), # Ensure score is a float for JSON compatibility
        "timestamp": datetime.utcnow(),
        "metadata": {
            "platform": "VS Code Terminal",
            "version": "v2.0-nosql"
        }
    }
    result = logs_collection.insert_one(log_document)
    print(f"[NoSQL] Log archived in MongoDB with ID: {result.inserted_id}")
    return result.inserted_id

def log_feedback_nosql(log_id, rating, comment):
    """Mirrors user feedback into MongoDB for unstructured analysis."""
    feedback_doc = {
        "sql_log_id": log_id,
        "rating": rating,
        "comment": comment,
        "sentiment_analysis_placeholder": "Positive" if rating >= 4 else "Neutral",
        "timestamp": datetime.utcnow()
    }
    result = feedback_collection.insert_one(feedback_doc)
    print(f"[NoSQL] Feedback mirrored to MongoDB collection.")