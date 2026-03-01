import streamlit as st
import psycopg2
import os
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer
from migrate_logs import save_to_nosql, log_feedback_nosql

# Load credentials from .env
load_dotenv()

# --- 1. Page Config & Professional Dark Theme ---
st.set_page_config(page_title="AI Movie Search Engine", page_icon="🎬", layout="wide")

# Custom CSS for Pure Black and White High-Contrast UI
st.markdown("""
    <style>
    /* Force entire background to deep black */
    .stApp {
        background-color: #000000;
        color: #ffffff;
    }

    /* Force all standard text and labels to white */
    h1, h2, h3, p, span, label, .stMarkdown {
        color: #ffffff !important;
    }

    /* --- THE BUTTON FIX --- */
    /* Target the Submit button to make it visible (Black text on White background) */
    div.stButton > button {
        background-color: #ffffff !important; 
        color: #000000 !important;           
        font-weight: 800 !important;
        border: 2px solid #ffffff !important;
        width: 100%;
        text-transform: uppercase;
        letter-spacing: 1px;
        padding: 10px;
        transition: 0.3s;
    }

    /* Hover effect for the button (Matrix Green) */
    div.stButton > button:hover {
        background-color: #00ff41 !important; 
        border-color: #00ff41 !important;
        color: #000000 !important;
    }

    /* --- MOVIE CARDS --- */
    .movie-card {
        background-color: #0a0a0a; /* Slightly lighter than pitch black */
        padding: 25px;
        border-radius: 12px;
        border: 1px solid #333333;
        margin-bottom: 20px;
        transition: all 0.3s ease;
    }

    .movie-card:hover {
        border-color: #ffffff;
        background-color: #111111;
        transform: translateY(-5px);
    }

    .movie-card h3 {
        color: #ffffff !important;
        margin-top: 0;
        font-weight: 800;
        text-transform: uppercase;
    }

    /* Score styling */
    .match-badge {
        color: #00ff41 !important; /* Matrix Green */
        font-weight: bold;
        font-family: 'Courier New', monospace;
    }

    /* Sidebar Styling */
    section[data-testid="stSidebar"] {
        background-color: #050505 !important;
        border-right: 1px solid #333333;
    }

    /* Search Input box styling */
    .stTextInput input {
        background-color: #111111 !important;
        color: white !important;
        border: 1px solid #333333 !important;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 2. Initialize AI Model ---
@st.cache_resource
def load_model():
    return SentenceTransformer('all-MiniLM-L6-v2')

model = load_model()

# --- 3. UI Header ---
st.title("🎬 AI MOVIE SEARCH ENGINE")
st.write("---")

# --- 4. Search Section ---
query_text = st.text_input("ENTER SEARCH QUERY", placeholder="e.g., A dystopian future with robots")

if query_text:
    # Convert query to Vector
    query_vector = model.encode(query_text).tolist()

    try:
        # Connect to Postgres
        conn = psycopg2.connect(
            host=os.getenv("DB_HOST"),
            database=os.getenv("DB_NAME"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD")
        )
        cur = conn.cursor()

        # Execute Vector Search
        cur.execute("SELECT * FROM smart_search(%s::vector)", (query_vector,))
        results = cur.fetchall()

        if results:
            st.subheader(f"TOP SYSTEM MATCHES FOR: '{query_text.upper()}'")
            
            # Create Grid Layout
            cols = st.columns(3)
            movie_options = {}

            for i, (movie_id, title, category, score) in enumerate(results):
                movie_options[title] = (movie_id, score)
                
                with cols[i % 3]:
                    st.markdown(f"""
                        <div class="movie-card">
                            <h3>{title}</h3>
                            <p style="color: #888888;">GENRE: {category}</p>
                            <p class="match-badge">SIMILARITY_SCORE: {round(score, 3)}</p>
                        </div>
                    """, unsafe_allow_html=True)

            # --- 5. Feedback Sidebar ---
            with st.sidebar:
                st.header("⚙️ SYSTEM CONTROL")
                st.write("Provide feedback to tune the AI.")
                
                with st.form("feedback_form"):
                    selected_movie = st.selectbox("SELECT MOVIE TARGET", options=list(movie_options.keys()))
                    rating = st.select_slider("ACCURACY RATING", options=[1, 2, 3, 4, 5], value=5)
                    comment = st.text_area("DEVELOPER NOTES")
                    
                    # This button is now fixed with CSS above
                    if st.form_submit_button("COMMIT TO DATABASES"):
                        sel_id, sel_score = movie_options[selected_movie]
                        
                        # SQL Updates
                        cur.execute("CALL log_and_search_results(%s, %s, %s)", (1, query_text, sel_id))
                        cur.execute("""
                            INSERT INTO Feedback (log_id, rating, user_comments) 
                            VALUES ((SELECT MAX(log_id) FROM Search_History), %s, %s)
                        """, (rating, comment))
                        
                        # NoSQL Mirroring (MongoDB)
                        save_to_nosql(1, query_text, selected_movie, sel_score)
                        log_feedback_nosql(sel_id, rating, comment)
                        
                        conn.commit()
                        st.success(f"LOGGED: {selected_movie}")
                        st.balloons()

        else:
            st.warning("NO MATCHES DETECTED IN LOCAL INDEX.")

        cur.close()
        conn.close()

    except Exception as e:
        st.error(f"DATABASE CONNECTION FAILURE: {e}")

st.markdown("---")
st.caption("TECH STACK: PGVECTOR | SENTENCE-TRANSFORMERS | MONGODB | STREAMLIT")