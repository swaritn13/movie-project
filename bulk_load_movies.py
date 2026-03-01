import os
import pandas as pd
import psycopg2
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer
from huggingface_hub import login

# Load variables from .env
load_dotenv()

# 1. Authenticate with your SwaritN Token
HF_TOKEN = os.getenv("HF_TOKEN")
if HF_TOKEN:
    login(token=HF_TOKEN)
    print("🔓 Hugging Face authenticated successfully.")

# 2. Initialize AI Model
print("🤖 Loading AI Model...")
model = SentenceTransformer('all-MiniLM-L6-v2')

# 3. Database Connection
try:
    conn = psycopg2.connect(
        host=os.getenv("DB_HOST"),
        database=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD")
    )
    cur = conn.cursor()
    print("🐘 Connected to PostgreSQL.")
except Exception as e:
    print(f"❌ Database Connection Error: {e}")
    exit()

def bulk_load_local():
    # Since the file is in your folder, we use the direct name
    FILE_PATH = "imdb_top_1000.csv"
    
    try:
        if not os.path.exists(FILE_PATH):
            print(f"❌ Error: {FILE_PATH} not found in the current folder!")
            return

        print(f"📂 Reading local file: {FILE_PATH}")
        df = pd.read_csv(FILE_PATH)
        
        # Taking top 100 movies for the "Big Data" experience
        movies = df[['Series_Title', 'Genre', 'Overview']].dropna().head(100)

        print(f"🧠 Generating AI Vectors for {len(movies)} movies... This may take a moment.")
        
        for index, row in movies.iterrows():
            # A. Extract First Genre
            genre_name = str(row['Genre']).split(',')[0].strip()
            
            # B. Insert/Get Category
            cur.execute("""
                INSERT INTO Category (cat_name) 
                VALUES (%s) 
                ON CONFLICT (cat_name) DO UPDATE SET cat_name = EXCLUDED.cat_name
                RETURNING cat_id
            """, (genre_name,))
            cat_id = cur.fetchone()[0]

            # C. Insert Movie into Source_Data (With Duplicate Protection)
            cur.execute("""
                INSERT INTO Source_Data (title, description, cat_id) 
                VALUES (%s, %s, %s) 
                ON CONFLICT (title) DO NOTHING
                RETURNING data_id
            """, (row['Series_Title'], row['Overview'], cat_id))

            # Get the ID of the movie we just inserted
            result = cur.fetchone()

            # D. AI Vector Generation (Only happens if the movie is NEW)
            if result:
                data_id = result[0]
                vector = model.encode(row['Overview']).tolist()
                cur.execute("""
                    INSERT INTO Vector_Index (data_id, embedding_array) 
                    VALUES (%s, %s)
                """, (data_id, vector))
            else:
                # If result is None, it means the movie already existed
                # and 'ON CONFLICT DO NOTHING' worked perfectly.
                continue

        conn.commit()
        print(f"\n🚀 SUCCESS! 100 movies from your CSV are now AI-indexed in PostgreSQL.")

    except Exception as e:
        print(f"❌ Error during load: {e}")
        conn.rollback()
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    bulk_load_local()