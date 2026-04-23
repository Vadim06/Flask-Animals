import os
import json
import io
import requests
from flask import Flask, render_template, request, redirect, url_for, session
from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont

load_dotenv()

app = Flask(__name__)
app.secret_key = "skibidiOpaPa"

API_KEY = os.getenv("API_KEY")
API_URL_CAT = "https://api.thecatapi.com/v1/images/search"
API_URL_DOG = "https://api.thedogapi.com/v1/images/search"
FAVORITES_FILE = "favorites.json"


def load_favorites():
    """
    Loads the list of favorite image URLs from the local JSON file.
    Returns an empty list if the file does not exist or is malformed.
    """
    if os.path.exists(FAVORITES_FILE):
        with open(FAVORITES_FILE, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return []
    return []


def save_favorite(image_url):
    """
    Appends a new image URL to the favorites JSON file.
    Ensures no duplicate URLs are saved to maintain uniqueness.
    """
    favorites = load_favorites()
    if image_url not in favorites:
        favorites.append(image_url)
        with open(FAVORITES_FILE, "w", encoding="utf-8") as f:
            json.dump(favorites, f, indent=4)


def remove_favorite(image_url):
    """
    Removes a specified image URL from the favorites JSON file.
    Updates the file only if the image URL is successfully found.
    """
    favorites = load_favorites()
    if image_url in favorites:
        favorites.remove(image_url)
        with open(FAVORITES_FILE, "w", encoding="utf-8") as f:
            json.dump(favorites, f, indent=4)


def wrap_text(text, font, max_width):
    """
    Splits a given string into multiple lines to ensure it fits within
    the specified maximum width when rendered with the provided font.
    """
    words = text.split()
    lines = []
    current_line = []

    for word in words:
        test_line = " ".join(current_line + [word])
        if font.getlength(test_line) <= max_width:
            current_line.append(word)
        else:
            lines.append(" ".join(current_line))
            current_line = [word]

    if current_line:
        lines.append(" ".join(current_line))

    return lines


@app.route("/")
def index():
    """
    Renders the main dashboard.
    Retrieves a random animal image from the external API
    based on the user's session state and loads
    saved favorites with pagination.
    """
    headers = {"x-api-key": API_KEY}

    force_new = request.args.get("new")
    new_animal = request.args.get("animal")

    if new_animal:
        session["animal_type"] = new_animal

    current_animal = session.get("animal_type", "cats")

    if current_animal == "cats":
        url = API_URL_CAT
        is_cats = True
    else:
        url = API_URL_DOG
        is_cats = False

    if force_new or "current_image" not in session:
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()
            image_url = data[0]["url"]
            session["current_image"] = image_url
        except requests.exceptions.RequestException:
            image_url = None
    else:
        image_url = session.get("current_image")

    # --- PAGINATION LOGIC ---
    all_favorites = load_favorites()
    all_favorites.reverse()

    try:
        page = int(request.args.get("page", 1))
    except ValueError:
        page = 1

    per_page = 6
    total_items = len(all_favorites)
    total_pages = (total_items + per_page - 1) // per_page

    if page < 1:
        page = 1
    elif page > total_pages and total_pages > 0:
        page = total_pages

    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page

    display_favorites = all_favorites[start_idx:end_idx]

    has_prev = page > 1
    has_next = page < total_pages

    return render_template(
        "index.html",
        image_url=image_url,
        favorites=display_favorites,
        show_cats=is_cats,
        page=page,
        total_pages=total_pages,
        has_prev=has_prev,
        has_next=has_next,
    )


@app.route("/save", methods=["POST"])
def save():
    """
    Handles the form submission to save a displayed image
    to the user's favorites.
    Redirects back to the index route upon completion.
    """
    cat_url = request.form.get("image_url")
    if cat_url:
        save_favorite(cat_url)
    return redirect(url_for("index"))


@app.route("/delete", methods=["POST"])
def delete():
    """
    Handles the form submission to remove an image from the user's favorites.
    Redirects back to the index route upon completion.
    """
    cat_url = request.form.get("image_url")
    if cat_url:
        remove_favorite(cat_url)
    return redirect(url_for("index"))


@app.route("/editor")
def editor():
    """
    Renders the meme editor UI,
    passing the selected image URL via query parameters.
    """
    image_url = request.args.get("url")
    return render_template("editor.html", image_url=image_url)


@app.route("/generate", methods=["POST"])
def generate():
    """
    Processes the meme generation request.
    Downloads the target image into memory,
    applies typography algorithms to wrap and draw the user's text, and saves
    the resulting image locally before rendering the result view.
    """
    image_url = request.form.get("image_url")
    text = request.form.get("meme_text")

    response = requests.get(image_url)
    img = Image.open(io.BytesIO(response.content)).convert("RGB")
    draw = ImageDraw.Draw(img)
    width, height = img.size

    try:
        font = ImageFont.truetype("impact.ttf", size=int(height / 12))
    except Exception:
        font = ImageFont.load_default()

    max_w = width * 0.9
    wrapped_lines = wrap_text(text, font, max_w)

    line_height = font.getbbox("Ay")[3] + 10
    y_start = height * 0.8 - (len(wrapped_lines) * line_height) / 2

    for line in wrapped_lines:
        draw.text(
            (width / 2, y_start),
            line,
            font=font,
            fill="white",
            stroke_width=2,
            stroke_fill="black",
            anchor="mm",
        )
        y_start += line_height

    save_path = os.path.join("static", "uploads", "current_meme.jpg")
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    img.save(save_path)

    return render_template(
        "editor.html", image_url=image_url, meme_generated=True)


app = Flask(__name__)
