
API_KEY = "963a1e5eded243a39875e555567a565e"
import gradio as gr
import bcrypt
import json
import os
import requests
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from sentence_transformers import SentenceTransformer

# Load SentenceTransformer model
model = SentenceTransformer('all-mpnet-base-v2')

# Constants
# API_KEY = "6da9f21c78fa4034811c25e29543eea9"
USER_FILE = "users.json"
category_choices = ["Sports", "Politics", "Business", "Technology", "Entertainment", "Health", "Science", "Education", "Environment"]

# Load/save users
def load_users():
    if not os.path.exists(USER_FILE):
        return {}
    with open(USER_FILE, 'r') as f:
        return json.load(f)

def save_users(data):
    with open(USER_FILE, 'w') as f:
        json.dump(data, f, indent=4)

# Registration/login/logout
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
        return "❌ User not found.", "", *[gr.update(visible=False)]*4, gr.update(visible=True), gr.update(visible=False)

    if bcrypt.checkpw(password.encode(), users[username]["password"].encode()):
        return (
            "✅ Login successful.",
            username,
            gr.update(visible=False),  # home
            gr.update(visible=False),  # register
            gr.update(visible=False),  # login
            gr.update(visible=True),   # preference
            gr.update(visible=False),  # news
        )
    else:
        return "❌ Incorrect password.", "", *[gr.update(visible=False)]*4, gr.update(visible=True), gr.update(visible=False)

def logout():
    return (
        "",
        gr.update(visible=True),
        gr.update(visible=False),
        gr.update(visible=False),
        gr.update(visible=False),
        gr.update(visible=False),
    )

# Preferences
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
    return [gr.update(visible=(cat in selected)) for cat in category_choices]

# NewsAPI

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
        print(f"NewsAPI response for '{query}':", response.status_code, response.json())
        return response.json().get("articles", [])
    except Exception as e:
        print("NewsAPI error:", e)
        return []

# Get news with confidence scoring
def get_news(username):
    users = load_users()
    prefs = users.get(username, {}).get("preferences", {})
    if not prefs:
        return "<p style='color:red;'>No preferences found for this user.</p>"

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
    .news-card.low-confidence {
        background: #2a2a2a;
        border-color: #555;
        color: #aaa;
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
    .confidence {
        font-size: 13px;
        color: lightgreen;
        margin-bottom: 5px;
    }
    .confidence.low {
        color: orange;
    }
    </style>
    """

    threshold = 0.45

    for category, keywords in prefs.items():
        html += f"<h2 style='color: orange;'>{category}</h2>"
        if not keywords:
            html += "<p>No specific interests provided.</p>"
            continue
        for keyword in keywords:
            html += f"<h4>🔍 {keyword}</h4>"
            articles = fetch_news(keyword)
            print(f"Articles for '{keyword}':", articles)
            if not articles:
                html += "<p>No news found.</p>"
                continue
            user_vector = model.encode(keyword)
            match_found = False
            for a in articles:
                title = a.get("title", "")
                desc = a.get("description", "")
                url = a.get("url", "#")
                if not title and not desc:
                    continue
                article_text = f"{title} {desc}".strip()
                article_vector = model.encode(article_text)
                confidence = cosine_similarity([user_vector], [article_vector])[0][0]
                conf_percent = round(confidence * 100, 2)
                confidence_class = "confidence low" if confidence < threshold else "confidence"
                card_class = "news-card low-confidence" if confidence < threshold else "news-card"
                conf_display = f"<div class='{confidence_class}'>Confidence: {conf_percent}%</div>"
                html += f"""
                <div class='{card_class}'>
                    <div class='news-title'>{title or "No Title"}</div>
                    <div class='news-desc'>{desc or "No Description"}</div>
                    {conf_display}
                    <a href='{url}' target='_blank'>Read more</a>
                </div>
                """
                match_found = True
            if not match_found:
                html += "<p>No relevant news articles matched your interest.</p>"

    return html

# UI
with gr.Blocks(theme=gr.themes.Glass()) as demo:
    gr.HTML("""
    <style>
    .centered-container {
        max-width: 600px;
        margin: 0 auto;
        padding: 20px;
    }
    </style>
    <div class='centered-container'>
        <div style='text-align:center'>
            <img src='https://img.icons8.com/fluency/96/news.png' height='80'>
            <h1 style='color: #0af;'>Personalized News Recommender</h1>
        </div>
    """)

    user_state = gr.State("")

    with gr.Group(visible=True) as home_page:
        gr.Markdown("### 👋 Welcome to Your AI News App")
        to_register = gr.Button("📝 Register")
        to_login = gr.Button("🔐 Login")

    with gr.Group(visible=False) as register_page:
        reg_user = gr.Text(label="👤 Username")
        reg_pass = gr.Text(label="🔐 Password", type="password")
        reg_btn = gr.Button("✅ Register")
        reg_out = gr.Textbox(label="Status")
        back_from_reg = gr.Button("⬅ Back")

    with gr.Group(visible=False) as login_page:
        login_user = gr.Text(label="👤 Username")
        login_pass = gr.Text(label="🔐 Password", type="password")
        login_btn = gr.Button("➡ Login")
        login_out = gr.Textbox(label="Status")
        back_from_login = gr.Button("⬅ Back")

    with gr.Group(visible=False) as preference_page:
        pref_user = gr.Textbox(label="Logged-in Username", interactive=False)
        cat_input = gr.CheckboxGroup(choices=category_choices, label="📁 Select News Categories")
        custom_inputs = [gr.Text(label=f"📝 Custom Interests for {cat} (comma separated)", visible=False) for cat in category_choices]
        cat_input.change(update_custom_inputs, inputs=cat_input, outputs=custom_inputs)
        save_btn = gr.Button("💾 Save Preferences")
        pref_status = gr.Textbox(label="Status")
        to_news_page = gr.Button("📢 Go to News")
        logout_btn_1 = gr.Button("🚪 Logout")

    with gr.Group(visible=False) as news_page:
        view_user = gr.Textbox(label="Logged-in Username", interactive=False)
        view_btn = gr.Button("🔍 Get My News")
        news_output = gr.HTML()
        logout_btn_2 = gr.Button("🚪 Logout")

    to_register.click(lambda: (gr.update(visible=False), gr.update(visible=True), gr.update(visible=False), gr.update(visible=False), gr.update(visible=False)),
                      outputs=[home_page, register_page, login_page, preference_page, news_page])
    to_login.click(lambda: (gr.update(visible=False), gr.update(visible=False), gr.update(visible=True), gr.update(visible=False), gr.update(visible=False)),
                   outputs=[home_page, register_page, login_page, preference_page, news_page])
    back_from_reg.click(lambda: (gr.update(visible=True), gr.update(visible=False)), outputs=[home_page, register_page])
    back_from_login.click(lambda: (gr.update(visible=True), gr.update(visible=False)), outputs=[home_page, login_page])

    reg_btn.click(register, inputs=[reg_user, reg_pass], outputs=reg_out)
    login_btn.click(fn=login_and_redirect, inputs=[login_user, login_pass], outputs=[login_out, user_state, home_page, register_page, login_page, preference_page, news_page])

    user_state.change(lambda u: (u, u), inputs=user_state, outputs=[pref_user, view_user])
    save_btn.click(fn=set_preferences, inputs=[user_state, cat_input] + custom_inputs, outputs=pref_status)
    to_news_page.click(lambda: (gr.update(visible=False), gr.update(visible=True)), outputs=[preference_page, news_page])
    view_btn.click(get_news, inputs=user_state, outputs=news_output)

    logout_btn_1.click(fn=logout, outputs=[user_state, home_page, register_page, login_page, preference_page, news_page])
    logout_btn_2.click(fn=logout, outputs=[user_state, home_page, register_page, login_page, preference_page, news_page])

    gr.HTML("""</div>""")

# Launch
demo.launch()