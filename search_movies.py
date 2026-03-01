import os
import psycopg2
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer
from huggingface_hub import login
# Import the NoSQL functions from your migrate_logs.py
from migrate_logs import save_to_nosql, log_feedback_nosql

load_dotenv()

# 1. Authentication & Model Setup
if os.getenv("HF_TOKEN"):
    login(token=os.getenv("HF_TOKEN"))
    print("🔓 Hugging Face authenticated.")

model = SentenceTransformer('all-MiniLM-L6-v2')

# 2. Get User Input
query_text = input("\nWhat movie are you looking for? ")
query_vector = model.encode(query_text).tolist()

# 3. Connect to Database
try:
    conn = psycopg2.connect(
        host=os.getenv("DB_HOST"),
        database=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD")
    )
    cur = conn.cursor()

    # --- A. SEARCH FIRST ---
    # We need the movie ID to log it later
    cur.execute("SELECT * FROM smart_search(%s::vector)", (query_vector,))
    results = cur.fetchall()
    
    if results:
        # Get data from the top match
        # smart_search returns: (id, title, category, distance)
        best_movie_id = results[0][0]
        best_title = results[0][1]
        best_cat = results[0][2]
        best_score = results[0][3]

        print(f"\n🎯 Top Match: [{best_cat}] {best_title}")
        print(f"Match Score: {round(best_score, 4)}")

        # --- B. LOG TO SQL (Using the Movie ID) ---
        # Matches your SQL: log_and_search_results(user_id, query, movie_id)
        cur.execute("CALL log_and_search_results(%s, %s, %s)", (1, query_text, best_movie_id))
        
        # --- C. ARCHIVE TO NOSQL (MongoDB) ---
        save_to_nosql(1, query_text, best_title, best_score)

        # --- D. FEEDBACK LOOP ---
        print("\n" + "="*30)
        rating = int(input("Rate this match (1-5): ") or 0)
        comment = input("Feedback comments: ")

        # 1. Update SQL (Fires the Trigger to update avg_rating)
        cur.execute("""
            INSERT INTO Feedback (log_id, rating, user_comments) 
            VALUES ((SELECT MAX(log_id) FROM Search_History), %s, %s)
        """, (rating, comment))
        
        # 2. Update NoSQL
        log_feedback_nosql(best_movie_id, rating, comment) 
        
        conn.commit()
        print("\n✅ All systems synced (SQL + NoSQL + AI).")
    else:
        print("❌ No movies found.")

except Exception as e:
    print(f"Error: {e}")
    if 'conn' in locals(): conn.rollback()
finally:
    if 'cur' in locals(): cur.close()
    if 'conn' in locals(): conn.close()