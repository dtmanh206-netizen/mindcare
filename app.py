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
    print("WARNING: Chưa tìm thấy GEMINI_API_KEY.")

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
    conn = sqlite3.connect(
        DATABASE,
        timeout=10
    )

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

@app.route(
    "/register",
    methods=["GET", "POST"]
)
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
            (
                name,
                email,
                password
            )
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

        return redirect(
            url_for("login")
        )

    return render_template(
        "register.html"
    )


# ============================================================
# LOGIN
# ============================================================

@app.route(
    "/login",
    methods=["GET", "POST"]
)
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

            return redirect(
                url_for("home")
            )

        return render_template(
            "login.html",
            error="Email hoặc mật khẩu không đúng."
        )

    return render_template(
        "login.html"
    )


# ============================================================
# LOGOUT
# ============================================================

@app.route("/logout")
@login_required
def logout():

    logout_user()

    return redirect(
        url_for("home")
    )


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
# MINDCARE AI PROMPT
# ============================================================

def build_mindcare_prompt(message):

    return f"""
Bạn là MindCare, một trợ lý AI hỗ trợ sức khỏe tinh thần
dành riêng cho sinh viên Việt Nam.

MỤC TIÊU:

Giúp sinh viên cảm thấy được lắng nghe, hiểu cảm xúc
và tìm được một bước nhỏ, an toàn để cải thiện tình trạng
hiện tại.

CÁC CHỦ ĐỀ MINDCARE HỖ TRỢ:

- Stress và áp lực học tập
- Áp lực thi cử
- Lo âu
- Buồn bã
- Mất động lực
- Cô đơn
- Khó ngủ do căng thẳng
- Áp lực gia đình
- Vấn đề tình cảm
- Mâu thuẫn bạn bè
- Khó khăn trong cuộc sống sinh viên
- Cảm xúc tiêu cực

NGUYÊN TẮC TRẢ LỜI:

1. Lắng nghe trước khi đưa lời khuyên.

2. Thể hiện sự đồng cảm nhưng không phán xét.

3. Không chẩn đoán bệnh tâm lý.

4. Không tự nhận là bác sĩ hoặc nhà trị liệu.

5. Không khẳng định người dùng mắc một căn bệnh nào.

6. Không đưa ra lời khuyên nguy hiểm.

7. Không làm người dùng cảm thấy có lỗi vì cảm xúc của họ.

8. Không trả lời quá dài.

9. Ưu tiên những hành động nhỏ và thực tế.

10. Nếu phù hợp, hỏi một câu ngắn để hiểu người dùng hơn.

CÁCH TRẢ LỜI:

Thông thường hãy trả lời theo cấu trúc:

- Một câu thể hiện rằng bạn đã hiểu cảm xúc của người dùng.
- Giải thích ngắn gọn điều có thể đang khiến họ cảm thấy như vậy.
- Đưa ra 1–3 gợi ý thực tế.
- Nếu cần, kết thúc bằng một câu hỏi nhẹ nhàng.

Ví dụ:

"Mình hiểu cảm giác đó. Khi phải chịu quá nhiều áp lực
cùng lúc, đầu óc rất dễ rơi vào trạng thái quá tải.

Trước mắt bạn có thể thử:
• Tạm nghỉ 5 phút.
• Viết ra 1 việc quan trọng nhất cần làm hôm nay.
• Sau đó chỉ tập trung vào việc đó thay vì nghĩ đến
toàn bộ mọi thứ cùng lúc.

Điều khiến bạn áp lực nhất lúc này là chuyện học,
gia đình hay một vấn đề khác?"

QUY TẮC VỀ NGUY HIỂM:

Nếu người dùng nói về tự sát, tự làm hại bản thân,
muốn chết hoặc đang gặp nguy hiểm ngay lập tức:

- Ưu tiên sự an toàn.
- Khuyến khích họ không ở một mình.
- Khuyến khích liên hệ ngay với người đáng tin cậy
  đang ở gần.
- Khuyến khích tìm dịch vụ y tế/cấp cứu hoặc hỗ trợ
  khẩn cấp tại nơi họ đang ở.
- Không cung cấp phương pháp hoặc hướng dẫn tự làm hại.
- Không tranh luận hoặc trách móc người dùng.

Nếu người dùng có vấn đề kéo dài hoặc ảnh hưởng đáng kể
đến học tập, giấc ngủ hoặc cuộc sống, hãy nhẹ nhàng
khuyến khích họ tìm chuyên gia tâm lý hoặc nhân viên y tế.

PHONG CÁCH:

- Tiếng Việt tự nhiên.
- Gần gũi với sinh viên.
- Ấm áp.
- Ngắn gọn.
- Không dùng văn phong quá máy móc.
- Có thể sử dụng emoji vừa phải.
- Không gọi người dùng là "bệnh nhân".

TIN NHẮN CỦA NGƯỜI DÙNG:

{message}
"""


# ============================================================
# GEMINI STREAMING
# ============================================================

def stream_ai_response(prompt):

    """
    Gọi Gemini theo dạng streaming thật.

    Gemini trả dữ liệu đến đâu,
    MindCare gửi đến trình duyệt đến đó.
    """

    try:

        response_stream = client.models.generate_content_stream(
            model="gemini-3.5-flash",
            contents=prompt
        )

        for chunk in response_stream:

            text = getattr(
                chunk,
                "text",
                None
            )

            if text:

                yield text

        return

    except Exception as e:

        error_text = str(e)

        print(
            "GEMINI STREAM ERROR:",
            error_text
        )

        # Retry tối đa 1 lần đối với lỗi tạm thời.
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
            return

        print(
            "Gemini đang bận. Thử lại sau 1 giây..."
        )

        time.sleep(1)

        try:

            response_stream = client.models.generate_content_stream(
                model="gemini-3.5-flash",
                contents=prompt
            )

            for chunk in response_stream:

                text = getattr(
                    chunk,
                    "text",
                    None
                )

                if text:
                    yield text

        except Exception as retry_error:

            print(
                "GEMINI RETRY ERROR:",
                retry_error
            )

            return


# ============================================================
# CHAT AI
# ============================================================

@app.route(
    "/chat",
    methods=["POST"]
)
def chat():

    data = request.get_json(
        silent=True
    ) or {}

    message = data.get(
        "message",
        ""
    ).strip()

    if not message:

        return Response(
            "Bạn hãy chia sẻ điều bạn đang cảm thấy nhé 💚",
            mimetype="text/plain; charset=utf-8"
        )

    prompt = build_mindcare_prompt(
        message
    )

    def generate():

        full_reply = ""

        try:

            for chunk in stream_ai_response(
                prompt
            ):

                full_reply += chunk

                yield chunk

            # Nếu AI không trả được gì
            if not full_reply.strip():

                fallback = (
                    "Xin lỗi, MindCare chưa nhận được "
                    "phản hồi từ AI. Bạn thử gửi lại "
                    "sau một chút nhé 💚"
                )

                yield fallback

                full_reply = fallback

            # Lưu lịch sử sau khi hoàn thành
            if current_user.is_authenticated:

                try:

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
                            full_reply.strip()
                        )
                    )

                    conn.commit()
                    conn.close()

                except Exception as db_error:

                    print(
                        "CHAT HISTORY ERROR:",
                        db_error
                    )

        except Exception as e:

            print(
                "CHAT ERROR:",
                e
            )

            error_message = (
                "MindCare đang gặp một chút vấn đề "
                "khi kết nối với AI. Bạn thử lại nhé 💚"
            )

            yield error_message

    return Response(
        stream_with_context(
            generate()
        ),
        mimetype="text/plain; charset=utf-8",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no"
        }
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
            (
                user_id,
                mood
            )
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
        (
            current_user.id,
        )
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
        (
            current_user.id,
        )
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
def delete_journal(
    journal_id
):

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
        (
            current_user.id,
        )
    ).fetchone()[0]

    total_journals = conn.execute(
        """
        SELECT COUNT(*)
        FROM journals
        WHERE user_id = ?
        """,
        (
            current_user.id,
        )
    ).fetchone()[0]

    total_chats = conn.execute(
        """
        SELECT COUNT(*)
        FROM chat_history
        WHERE user_id = ?
        """,
        (
            current_user.id,
        )
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
        (
            current_user.id,
        )
    ).fetchall()

    conn.close()

    return jsonify({
        "history": [
            dict(item)
            for item in history
        ]
    })


# ============================================================
# RUN LOCAL
# ============================================================

if __name__ == "__main__":

    print("=" * 60)
    print("       MINDCARE - AI MENTAL HEALTH")
    print("=" * 60)

    print(
        "Website: http://127.0.0.1:5000"
    )

    print("=" * 60)

    app.run(
        debug=True,
        host="127.0.0.1",
        port=5000
    )