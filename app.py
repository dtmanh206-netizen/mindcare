```python
from flask import (
    Flask,
    render_template,
    request,
    jsonify,
    redirect,
    url_for,
    Response,
    stream_with_context
)

from flask_login import (
    LoginManager,
    UserMixin,
    login_user,
    login_required,
    logout_user,
    current_user
)

from werkzeug.security import (
    generate_password_hash,
    check_password_hash
)

from google import genai
from dotenv import load_dotenv

import sqlite3
import os
import time


# ============================================================
# CONFIG
# ============================================================

load_dotenv()

app = Flask(__name__)

app.secret_key = os.getenv(
    "FLASK_SECRET_KEY",
    "mindcare-secret-key-change-later"
)

DATABASE = "mindcare.db"

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    print("WARNING: Chưa tìm thấy GEMINI_API_KEY trong biến môi trường.")

client = genai.Client(
    api_key=GEMINI_API_KEY
)


# ============================================================
# LOGIN
# ============================================================

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"


# ============================================================
# DATABASE
# ============================================================

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():

    conn = get_db()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS chat_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            message TEXT NOT NULL,
            reply TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS mood_checkins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            mood TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS journals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            title TEXT,
            content TEXT NOT NULL,
            mood TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    """)

    conn.commit()
    conn.close()


init_db()


# ============================================================
# USER MODEL
# ============================================================

class User(UserMixin):

    def __init__(
        self,
        id,
        name,
        email,
        password
    ):
        self.id = id
        self.name = name
        self.email = email
        self.password = password


@login_manager.user_loader
def load_user(user_id):

    conn = get_db()

    user = conn.execute(
        """
        SELECT *
        FROM users
        WHERE id = ?
        """,
        (user_id,)
    ).fetchone()

    conn.close()

    if user:

        return User(
            user["id"],
            user["name"],
            user["email"],
            user["password"]
        )

    return None


# ============================================================
# HOME
# ============================================================

@app.route("/")
def home():

    return render_template("index.html")


# ============================================================
# REGISTER
# ============================================================

@app.route("/register", methods=["GET", "POST"])
def register():

    if current_user.is_authenticated:
        return redirect(url_for("home"))

    if request.method == "POST":

        name = request.form.get(
            "name",
            ""
        ).strip()

        email = request.form.get(
            "email",
            ""
        ).strip().lower()

        password = request.form.get(
            "password",
            ""
        )

        if not name or not email or not password:

            return render_template(
                "register.html",
                error="Vui lòng nhập đầy đủ thông tin."
            )

        if len(password) < 6:

            return render_template(
                "register.html",
                error="Mật khẩu phải có ít nhất 6 ký tự."
            )

        conn = get_db()

        existing_user = conn.execute(
            """
            SELECT id
            FROM users
            WHERE email = ?
            """,
            (email,)
        ).fetchone()

        if existing_user:

            conn.close()

            return render_template(
                "register.html",
                error="Email này đã được đăng ký."
            )

        hashed_password = generate_password_hash(
            password
        )

        conn.execute(
            """
            INSERT INTO users
            (name, email, password)
            VALUES (?, ?, ?)
            """,
            (
                name,
                email,
                hashed_password
            )
        )

        conn.commit()
        conn.close()

        return redirect(url_for("login"))

    return render_template("register.html")


# ============================================================
# LOGIN
# ============================================================

@app.route("/login", methods=["GET", "POST"])
def login():

    if current_user.is_authenticated:
        return redirect(url_for("home"))

    if request.method == "POST":

        email = request.form.get(
            "email",
            ""
        ).strip().lower()

        password = request.form.get(
            "password",
            ""
        )

        conn = get_db()

        user = conn.execute(
            """
            SELECT *
            FROM users
            WHERE email = ?
            """,
            (email,)
        ).fetchone()

        conn.close()

        if user and check_password_hash(
            user["password"],
            password
        ):

            user_object = User(
                user["id"],
                user["name"],
                user["email"],
                user["password"]
            )

            login_user(user_object)

            return redirect(url_for("home"))

        return render_template(
            "login.html",
            error="Email hoặc mật khẩu không đúng."
        )

    return render_template("login.html")


# ============================================================
# LOGOUT
# ============================================================

@app.route("/logout")
@login_required
def logout():

    logout_user()

    return redirect(url_for("home"))


# ============================================================
# CURRENT USER
# ============================================================

@app.route("/api/me")
def get_current_user():

    if not current_user.is_authenticated:

        return jsonify({
            "logged_in": False
        })

    return jsonify({
        "logged_in": True,
        "user": {
            "id": current_user.id,
            "name": current_user.name,
            "email": current_user.email
        }
    })


# ============================================================
# AI PROMPT
# ============================================================

def build_mindcare_prompt(message):

    return f"""
Bạn là MindCare – một trợ lý AI hỗ trợ sức khỏe tinh thần
dành cho sinh viên Việt Nam.

Nhiệm vụ của bạn:

- Lắng nghe người dùng một cách nhẹ nhàng.
- Không phán xét.
- Không chẩn đoán bệnh.
- Không tự nhận mình là bác sĩ hoặc chuyên gia.
- Giúp người dùng nhận diện cảm xúc.
- Đưa ra những gợi ý đơn giản, an toàn và thực tế.
- Có thể gợi ý nghỉ ngơi, hít thở, vận động nhẹ,
  ngủ đủ, viết nhật ký hoặc chia sẻ với người đáng tin cậy.
- Nếu vấn đề kéo dài và ảnh hưởng rõ tới học tập,
  giấc ngủ hoặc cuộc sống, khuyến khích tìm chuyên gia
  tâm lý hoặc nhân viên y tế.
- Nếu người dùng nói về tự làm hại bản thân,
  tự sát hoặc nguy hiểm ngay lập tức:
  ưu tiên an toàn, khuyến khích họ không ở một mình,
  liên hệ ngay người đáng tin cậy ở gần và tìm hỗ trợ
  y tế khẩn cấp khi cần.
- Tuyệt đối không cung cấp hướng dẫn tự làm hại bản thân.
- Trả lời bằng tiếng Việt.
- Trả lời tự nhiên, không quá dài.
- Khoảng 2–5 đoạn ngắn.
- Có thể dùng emoji vừa phải.

Tin nhắn của người dùng:

{message}
"""


# ============================================================
# GEMINI AI
# ============================================================

def generate_ai_response(prompt):

    """
    Gọi Gemini với cơ chế retry cho các lỗi tạm thời
    như 503 / 429 / 500.
    """

    max_attempts = 3

    for attempt in range(max_attempts):

        try:

            response = client.models.generate_content(
                model="gemini-3.5-flash",
                contents=prompt
            )

            text = getattr(
                response,
                "text",
                None
            )

            if text:
                return text.strip()

            return ""

        except Exception as e:

            error_text = str(e)

            print(
                f"GEMINI ERROR - attempt {attempt + 1}/{max_attempts}:",
                error_text
            )

            # Các lỗi có khả năng thử lại
            retryable = any(
                code in error_text
                for code in [
                    "503",
                    "UNAVAILABLE",
                    "429",
                    "RESOURCE_EXHAUSTED",
                    "500",
                    "INTERNAL"
                ]
            )

            if not retryable:
                break

            if attempt < max_attempts - 1:

                # 2 giây -> 4 giây
                wait_time = 2 ** (attempt + 1)

                print(
                    f"Gemini đang bận. Thử lại sau {wait_time} giây..."
                )

                time.sleep(wait_time)

    return None


# ============================================================
# CHAT AI
# ============================================================

@app.route("/chat", methods=["POST"])
def chat():

    data = request.get_json(
        silent=True
    ) or {}

    message = data.get(
        "message",
        ""
    ).strip()

    if not message:

        return jsonify({
            "reply": "Bạn hãy chia sẻ điều bạn đang cảm thấy nhé 💚"
        })

    prompt = build_mindcare_prompt(message)

    def generate():

        try:

            full_reply = generate_ai_response(
                prompt
            )

            if full_reply:

                # Streaming giả lập từng đoạn nhỏ
                # để frontend hiện câu trả lời mượt hơn.

                words = full_reply.split(" ")

                current_text = ""

                for index, word in enumerate(words):

                    if index == 0:
                        current_text = word
                    else:
                        current_text += " " + word

                    yield (
                        word
                        if index == 0
                        else " " + word
                    )

                    # Không delay quá nhiều
                    time.sleep(0.01)

                # Lưu lịch sử
                if current_user.is_authenticated:

                    conn = get_db()

                    conn.execute(
                        """
                        INSERT INTO chat_history
                        (
                            user_id,
                            message,
                            reply
                        )
                        VALUES (?, ?, ?)
                        """,
                        (
                            current_user.id,
                            message,
                            full_reply
                        )
                    )

                    conn.commit()
                    conn.close()

                return

            # Gemini không trả được câu trả lời
            yield (
                "Xin lỗi, MindCare đang tạm thời không thể "
                "kết nối với AI. Bạn chờ một chút rồi thử lại nhé 💚"
            )

        except Exception as e:

            print(
                "CHAT ERROR:",
                e
            )

            yield (
                "Xin lỗi, MindCare đang gặp sự cố "
                "khi xử lý tin nhắn. Bạn thử lại nhé 💚"
            )

    return Response(
        stream_with_context(generate()),
        mimetype="text/plain; charset=utf-8"
    )


# ============================================================
# SAVE MOOD
# ============================================================

@app.route(
    "/api/mood",
    methods=["POST"]
)
@login_required
def save_mood():

    try:

        data = request.get_json(
            silent=True
        ) or {}

        mood = data.get(
            "mood",
            ""
        ).strip()

        if not mood:

            return jsonify({
                "success": False,
                "error": "Chưa chọn cảm xúc."
            })

        conn = get_db()

        conn.execute(
            """
            INSERT INTO mood_checkins
            (user_id, mood)
            VALUES (?, ?)
            """,
            (
                current_user.id,
                mood
            )
        )

        conn.commit()
        conn.close()

        return jsonify({
            "success": True
        })

    except Exception as e:

        print(
            "MOOD ERROR:",
            e
        )

        return jsonify({
            "success": False,
            "error": "Không thể lưu cảm xúc."
        })


# ============================================================
# MOOD HISTORY
# ============================================================

@app.route("/api/moods")
@login_required
def get_moods():

    conn = get_db()

    moods = conn.execute(
        """
        SELECT
            id,
            mood,
            created_at
        FROM mood_checkins
        WHERE user_id = ?
        ORDER BY id DESC
        LIMIT 30
        """,
        (current_user.id,)
    ).fetchall()

    conn.close()

    return jsonify({
        "moods": [
            dict(mood)
            for mood in moods
        ]
    })


# ============================================================
# JOURNALS
# ============================================================

@app.route("/api/journals")
@login_required
def get_journals():

    conn = get_db()

    journals = conn.execute(
        """
        SELECT
            id,
            title,
            content,
            mood,
            created_at
        FROM journals
        WHERE user_id = ?
        ORDER BY id DESC
        """,
        (current_user.id,)
    ).fetchall()

    conn.close()

    return jsonify({
        "journals": [
            dict(journal)
            for journal in journals
        ]
    })


# ============================================================
# SAVE JOURNAL
# ============================================================

@app.route(
    "/api/journal",
    methods=["POST"]
)
@login_required
def save_journal():

    try:

        data = request.get_json(
            silent=True
        ) or {}

        title = data.get(
            "title",
            ""
        ).strip()

        content = data.get(
            "content",
            ""
        ).strip()

        mood = data.get(
            "mood",
            ""
        ).strip()

        if not content:

            return jsonify({
                "success": False,
                "error": "Nội dung nhật ký không được để trống."
            })

        conn = get_db()

        conn.execute(
            """
            INSERT INTO journals
            (
                user_id,
                title,
                content,
                mood
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                current_user.id,
                title,
                content,
                mood
            )
        )

        conn.commit()
        conn.close()

        return jsonify({
            "success": True
        })

    except Exception as e:

        print(
            "JOURNAL ERROR:",
            e
        )

        return jsonify({
            "success": False,
            "error": "Không thể lưu nhật ký."
        })


# ============================================================
# DELETE JOURNAL
# ============================================================

@app.route(
    "/api/journal/<int:journal_id>",
    methods=["DELETE"]
)
@login_required
def delete_journal(journal_id):

    conn = get_db()

    conn.execute(
        """
        DELETE FROM journals
        WHERE id = ?
        AND user_id = ?
        """,
        (
            journal_id,
            current_user.id
        )
    )

    conn.commit()
    conn.close()

    return jsonify({
        "success": True
    })


# ============================================================
# STATISTICS
# ============================================================

@app.route("/api/stats")
@login_required
def get_stats():

    conn = get_db()

    total_checkins = conn.execute(
        """
        SELECT COUNT(*)
        FROM mood_checkins
        WHERE user_id = ?
        """,
        (current_user.id,)
    ).fetchone()[0]

    total_journals = conn.execute(
        """
        SELECT COUNT(*)
        FROM journals
        WHERE user_id = ?
        """,
        (current_user.id,)
    ).fetchone()[0]

    total_chats = conn.execute(
        """
        SELECT COUNT(*)
        FROM chat_history
        WHERE user_id = ?
        """,
        (current_user.id,)
    ).fetchone()[0]

    conn.close()

    return jsonify({
        "total_checkins": total_checkins,
        "total_journals": total_journals,
        "total_chats": total_chats
    })


# ============================================================
# CHAT HISTORY
# ============================================================

@app.route("/api/history")
@login_required
def get_history():

    conn = get_db()

    history = conn.execute(
        """
        SELECT
            message,
            reply,
            created_at
        FROM chat_history
        WHERE user_id = ?
        ORDER BY id DESC
        LIMIT 50
        """,
        (current_user.id,)
    ).fetchall()

    conn.close()

    return jsonify({
        "history": [
            dict(item)
            for item in history
        ]
    })


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":

    print("=" * 60)
    print("        MINDCARE - AI MENTAL HEALTH")
    print("=" * 60)
    print("Website: http://127.0.0.1:5000")
    print("=" * 60)

    app.run(
        debug=True,
        host="127.0.0.1",
        port=5000
    )
```
