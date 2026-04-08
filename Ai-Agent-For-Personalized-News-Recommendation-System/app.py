import gradio as gr
import bcrypt
import json
import os
import requests
from sentence_transformers import SentenceTransformer
from transformers import pipeline
from dotenv import load_dotenv

load_dotenv()
API_KEY = "YOUR_NEWSAPI"

# Load BERT model for embeddings (if needed for extensions)
model = SentenceTransformer('YOUR_MODEL')

# Summarizer pipeline from transformers (default model)
summarizer = pipeline("summarization", model="sshleifer/distilbart-cnn-12-6", device=-1)  # CPU

USER_FILE = "users.json"
category_choices = ["Sports", "Politics", "Business", "Technology", "Entertainment", "Health", "Science", "Education", "Environment"]


# --- User data handling ---
def load_users():
    if not os.path.exists(USER_FILE):
        return {}
    with open(USER_FILE, 'r') as f:
        return json.load(f)

def save_users(data):
    with open(USER_FILE, 'w') as f:
        json.dump(data, f, indent=4)


# --- Authentication ---
def register(username, password):
    users = load_users()
    if username in users:
        return "❌ Username already exists."
    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    users[username] = {"password": hashed, "preferences": {}}
    save_users(users)
    return "✅ Registered successfully."

def login_and_redirect(username, password):
    users = load_users()
    if username not in users:
        return ("❌ User not found.", "", gr.update(visible=True), gr.update(visible=False), gr.update(visible=True), gr.update(visible=False), gr.update(visible=False), gr.update(visible=False))
    if bcrypt.checkpw(password.encode(), users[username]["password"].encode()):
        return ("✅ Login successful.", username,
                gr.update(visible=False),  # home_page hidden
                gr.update(visible=False),  # register_page hidden
                gr.update(visible=False),  # login_page hidden
                gr.update(visible=True),   # preference_page visible
                gr.update(visible=False),  # news_page hidden
                gr.update(visible=False))  # dashboard_page hidden
    return ("❌ Incorrect password.", "", gr.update(visible=True), gr.update(visible=False), gr.update(visible=True), gr.update(visible=False), gr.update(visible=False), gr.update(visible=False))

def logout():
    # Show home page and clear username state
    return "", gr.update(visible=True), gr.update(visible=False), gr.update(visible=False), gr.update(visible=False), gr.update(visible=False), gr.update(visible=False), gr.update(visible=False)


# --- Preferences ---
def set_preferences(username, selected_categories, *custom_inputs):
    users = load_users()
    if username not in users:
        return "❌ User not found."
    prefs = {}
    for i, category in enumerate(category_choices):
        if category in selected_categories:
            interests = [k.strip() for k in custom_inputs[i].split(",") if k.strip()]
            prefs[category] = interests
    users[username]["preferences"] = prefs
    save_users(users)
    return f"✅ Preferences saved for {username}"

def update_custom_inputs(selected):
    # Show custom inputs only for selected categories
    return [gr.update(visible=(cat in selected)) for cat in category_choices]


# --- News API fetching ---
def fetch_news(query, max_results=5):
    url = "https://newsapi.org/v2/everything"
    params = {
        "q": query,
        "pageSize": max_results,
        "apiKey": API_KEY,
        "language": "en",
        "sortBy": "publishedAt",
    }
    try:
        response = requests.get(url, params=params)
        data = response.json()
        if data.get("status") != "ok":
            return []
        return data.get("articles", [])
    except Exception:
        return []

def generate_news_card(title, desc, url):
    return f"""
    <div class='news-card'>
        <div class='news-title'>{title}</div>
        <div class='news-desc'>{desc}</div>
        <a href='{url}' target='_blank'>Read more</a>
    </div>
    """

def get_news(username):
    users = load_users()
    prefs = users.get(username, {}).get("preferences", {})
    if not prefs:
        return "<p style='color:red;'>No preferences found for this user. Please set your preferences.</p>"

    html = """
    <style>
    .news-card {
        border: 1px solid #444;
        border-radius: 10px;
        padding: 14px;
        margin: 10px 0;
        background: #1c1c1c;
        color: #eee;
        transition: 0.3s ease;
    }
    .news-card:hover {
        background-color: #222;
        transform: scale(1.01);
    }
    .news-title {
        font-weight: bold;
        font-size: 18px;
        margin-bottom: 5px;
    }
    .news-desc {
        font-size: 14px;
        margin-bottom: 5px;
    }
    </style>
    """

    for category, keywords in prefs.items():
        html += f"<h2 style='color: orange;'>{category}</h2>"
        if not keywords:
            html += "<p>No specific interests provided.</p>"
            continue
        for keyword in keywords:
            html += f"<h4>🔍 {keyword}</h4>"
            articles = fetch_news(keyword)
            if not articles:
                html += "<p>No news found.</p>"
                continue
            for a in articles:
                title = a.get("title", "")
                desc = a.get("description", "")
                url = a.get("url", "#")
                html += generate_news_card(title, desc, url)
    return html


# --- Summarizer ---
def summarize_text(text):
    if not text.strip():
        return "❌ Please enter text to summarize."
    max_input_length = 512
    text = text[:max_input_length]
    summary = summarizer(text, max_length=100, min_length=30, do_sample=False)
    return summary[0]['summary_text']


# --- Dashboard ---
def get_dashboard(username):
    users = load_users()
    prefs = users.get(username, {}).get("preferences", {})
    total_categories = len(prefs)
    total_keywords = sum(len(v) for v in prefs.values())
    return f"""
    <h2>Dashboard for {username}</h2>
    <p>Total Categories Selected: <b>{total_categories}</b></p>
    <p>Total Keywords Across Categories: <b>{total_keywords}</b></p>
    <p>You can now visit the News page to see your personalized news feed.</p>
    """


# --- UI ---

with gr.Blocks(theme=gr.themes.Glass()) as demo:
    gr.HTML("""
    <style>
    body {background-color: #121212; color: #eee;}
    .centered-container {
        max-width: 700px;
        margin: 0 auto;
        padding: 20px;
    }
    .news-card {
        border: 1px solid #444;
        border-radius: 10px;
        padding: 14px;
        margin: 10px 0;
        background: #1c1c1c;
        color: #eee;
        transition: 0.3s ease;
    }
    .news-card:hover {
        background-color: #222;
        transform: scale(1.01);
    }
    .news-title {
        font-weight: bold;
        font-size: 18px;
        margin-bottom: 5px;
    }
    .news-desc {
        font-size: 14px;
        margin-bottom: 5px;
    }
    </style>
    <div class='centered-container'>
        <div style='text-align:center; margin-bottom:20px;'>
            <img src='https://img.icons8.com/fluency/96/news.png' height='80'>
            <h1 style='color: #0af;'>Personalized AI News Recommender</h1>
        </div>
    """)

    # User session state
    user_state = gr.State("")

    # --- Home page ---
    with gr.Group(visible=True) as home_page:
        gr.Markdown("### 👋 Welcome to Your AI News App")
        to_register = gr.Button("📝 Register")
        to_login = gr.Button("🔐 Login")

    # --- Register page ---
    with gr.Group(visible=False) as register_page:
        reg_user = gr.Text(label="👤 Username")
        reg_pass = gr.Text(label="🔐 Password", type="password")
        reg_btn = gr.Button("✅ Register")
        reg_out = gr.Textbox(label="Status", interactive=False)
        back_from_reg = gr.Button("⬅️ Back")

    # --- Login page ---
    with gr.Group(visible=False) as login_page:
        login_user = gr.Text(label="👤 Username")
        login_pass = gr.Text(label="🔐 Password", type="password")
        login_btn = gr.Button("➡️ Login")
        login_out = gr.Textbox(label="Status", interactive=False)
        back_from_login = gr.Button("⬅️ Back")

    # --- Preferences page ---
    with gr.Group(visible=False) as preference_page:
        pref_user = gr.Textbox(label="Logged-in Username", interactive=False)
        cat_input = gr.CheckboxGroup(choices=category_choices, label="📁 Select News Categories")
        custom_inputs = [gr.Text(label=f"📝 Custom Interests for {cat} (comma separated)", visible=False) for cat in category_choices]
        cat_input.change(update_custom_inputs, inputs=cat_input, outputs=custom_inputs)
        save_btn = gr.Button("💾 Save Preferences")
        pref_status = gr.Textbox(label="Status", interactive=False)
        to_news_page = gr.Button("📢 Go to News")
        to_dashboard_btn = gr.Button("📊 Go to Dashboard")
        logout_btn_1 = gr.Button("🚪 Logout")

    # --- News page ---
    with gr.Group(visible=False) as news_page:
        view_user = gr.Textbox(label="Logged-in Username", interactive=False)
        view_btn = gr.Button("🔍 Get My News")
        news_output = gr.HTML()
        summary_input = gr.Textbox(label="✍️ Paste text to summarize", lines=4)
        summary_btn = gr.Button("📝 Summarize")
        summary_output = gr.Textbox(label="Summary", interactive=False)
        back_to_pref_from_news = gr.Button("⬅️ Back to Preferences")
        logout_btn_2 = gr.Button("🚪 Logout")

    # --- Dashboard page ---
    with gr.Group(visible=False) as dashboard_page:
        dash_user = gr.Textbox(label="Logged-in Username", interactive=False)
        dash_content = gr.HTML()
        refresh_dash_btn = gr.Button("🔄 Refresh Dashboard")
        back_to_pref_from_dash = gr.Button("⬅️ Back to Preferences")
        logout_btn_3 = gr.Button("🚪 Logout")

    # --- Navigation ---

    # Home -> Register / Login
    to_register.click(lambda: (gr.update(visible=False), gr.update(visible=True), gr.update(visible=False), gr.update(visible=False), gr.update(visible=False), gr.update(visible=False), gr.update(visible=False), gr.update(visible=False)),
                      outputs=[home_page, register_page, login_page, preference_page, news_page, dashboard_page, user_state, pref_status])
    to_login.click(lambda: (gr.update(visible=False), gr.update(visible=False), gr.update(visible=True), gr.update(visible=False), gr.update(visible=False), gr.update(visible=False), gr.update(visible=False), gr.update(visible=False)),
                   outputs=[home_page, register_page, login_page, preference_page, news_page, dashboard_page, user_state, login_out])

    # Back buttons
    back_from_reg.click(lambda: (gr.update(visible=True), gr.update(visible=False)), outputs=[home_page, register_page])
    back_from_login.click(lambda: (gr.update(visible=True), gr.update(visible=False)), outputs=[home_page, login_page])
    back_to_pref_from_news.click(lambda: (gr.update(visible=False), gr.update(visible=True)), outputs=[news_page, preference_page])
    back_to_pref_from_dash.click(lambda: (gr.update(visible=False), gr.update(visible=True)), outputs=[dashboard_page, preference_page])

    # Register action
    reg_btn.click(register, inputs=[reg_user, reg_pass], outputs=reg_out)

    # Login action
    login_btn.click(login_and_redirect, inputs=[login_user, login_pass], 
                    outputs=[login_out, user_state, home_page, register_page, login_page, preference_page, news_page, dashboard_page])

    # Keep username synced across pages
    def sync_user_fields(username):
        return (username, username, username)
    user_state.change(sync_user_fields, inputs=user_state, outputs=[pref_user, view_user, dash_user])

    # Save preferences
    save_btn.click(set_preferences, inputs=[user_state, cat_input] + custom_inputs, outputs=pref_status)

    # Show/hide custom inputs based on categories selected
    cat_input.change(update_custom_inputs, inputs=cat_input, outputs=custom_inputs)

    # Navigate to news page
    to_news_page.click(lambda: (gr.update(visible=False), gr.update(visible=True)), outputs=[preference_page, news_page])

    # Navigate to dashboard page
    to_dashboard_btn.click(lambda: (gr.update(visible=False), gr.update(visible=True)), outputs=[preference_page, dashboard_page])

    # Get news button
    view_btn.click(get_news, inputs=user_state, outputs=news_output)

    # Summarizer button
    summary_btn.click(summarize_text, inputs=summary_input, outputs=summary_output)

    # Refresh dashboard content
    refresh_dash_btn.click(get_dashboard, inputs=dash_user, outputs=dash_content)

    # Logout buttons for all pages
    logout_btn_1.click(logout, outputs=[user_state, home_page, register_page, login_page, preference_page, news_page, dashboard_page, pref_status])
    logout_btn_2.click(logout, outputs=[user_state, home_page, register_page, login_page, preference_page, news_page, dashboard_page, pref_status])
    logout_btn_3.click(logout, outputs=[user_state, home_page, register_page, login_page, preference_page, news_page, dashboard_page, pref_status])

    gr.HTML("</div>")  # closing centered-container div

demo.launch()
