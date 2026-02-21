from flask import Flask, render_template, request, redirect, url_for, send_file
from flask import abort
import requests
from bs4 import BeautifulSoup
import psycopg2
import qrcode
import os
import uuid
from datetime import datetime

app = Flask(__name__)

DATABASE_URL = os.environ.get("DATABASE_URL")
QR_FOLDER = "static/qr_codes"
os.makedirs(QR_FOLDER, exist_ok=True)

def get_connection():
    return psycopg2.connect(DATABASE_URL)

def init_db():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS history (
            id SERIAL PRIMARY KEY,
            link TEXT NOT NULL,
            filename TEXT NOT NULL,
            created_at TIMESTAMP NOT NULL,
            title TEXT
        );
    """)
    conn.commit()
    cur.close()
    conn.close()

init_db()

@app.route("/", methods=["GET", "POST"])
def index():
    conn = get_connection()
    cur = conn.cursor()
    error = None

    if request.method == "POST":
        link = request.form["link"]

        if link.strip() == "":
            error = "Please enter a valid URL"
        else:
            if not link.startswith("http://") and not link.startswith("https://"):
                link = "https://" + link

            filename = f"{uuid.uuid4().hex}.png"
            filepath = os.path.join(QR_FOLDER, filename)

            img = qrcode.make(link)
            img.save(filepath)

            page_title = "Untitled"
            try:
                headers = {"User-Agent": "Mozilla/5.0"}
                response = requests.get(link, headers=headers, timeout=5)
                soup = BeautifulSoup(response.text, "html.parser")
                if soup.title and soup.title.string:
                    page_title = soup.title.string.strip()
            except:
                pass

            cur.execute(
                "INSERT INTO history (link, filename, created_at, title) VALUES (%s, %s, %s, %s)",
                (link, filename, datetime.now(), page_title)
            )
            conn.commit()

            cur.close()
            conn.close()
            return redirect(url_for("index"))

    cur.execute("SELECT * FROM history ORDER BY id DESC")
    history = cur.fetchall()

    cur.close()
    conn.close()

    return render_template("index.html", history=history, error=error)

@app.route("/delete/<int:id>")
def delete(id):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT filename FROM history WHERE id=%s", (id,))
    file = cur.fetchone()

    if file:
        file_path = os.path.join(QR_FOLDER, file[0])
        if os.path.exists(file_path):
            os.remove(file_path)

        cur.execute("DELETE FROM history WHERE id=%s", (id,))
        conn.commit()

    cur.close()
    conn.close()

    return redirect(url_for("index"))

@app.route("/download/<filename>")
def download(filename):
    conn = get_connection()
    cur = conn.cursor()

    # Fetch title + link from DB
    cur.execute("SELECT title, link FROM history WHERE filename=%s", (filename,))
    result = cur.fetchone()

    cur.close()
    conn.close()

    path = os.path.join(QR_FOLDER, filename)

    if not os.path.exists(path):
        abort(404)

    if result:
        title, link = result

        domain = link.replace("https://", "").replace("http://", "")
        domain = domain.split("/")[0]

        safe_title = "".join(
            c for c in title if c.isalnum() or c in (" ", "_", "-")
        ).strip()

        download_name = f"{safe_title}({domain})-qr.png"
    else:
        download_name = "QR_Code.png"

    return send_file(path, as_attachment=True, download_name=download_name)

if __name__ == "__main__":
    app.run()