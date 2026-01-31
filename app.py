import os
from datetime import timedelta
from functools import wraps

from flask import Flask, request, jsonify, render_template_string
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import (
    JWTManager,
    create_access_token,
    jwt_required,
    get_jwt_identity
)
from werkzeug.security import generate_password_hash, check_password_hash

# =====================================
# CONFIGURATION + PORT SETUP
# =====================================

app = Flask(__name__)

# SECRET KEYS
app.config["SECRET_KEY"] = "super-secret-key"
app.config["JWT_SECRET_KEY"] = "jwt-secret-key"

# TOKEN EXPIRATION
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(minutes=30)

# DATABASE
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///cv.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# INIT EXTENSIONS
db = SQLAlchemy(app)
jwt = JWTManager(app)

# =====================================
# DATABASE MODELS
# =====================================

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)

    role = db.Column(db.String(20), default="user")  # user/admin

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class CVProfile(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    full_name = db.Column(db.String(120))
    title = db.Column(db.String(120))

    skills = db.Column(db.Text)
    projects = db.Column(db.Text)

# =====================================
# ADMIN ROLE DECORATOR
# =====================================

def admin_required(fn):
    @wraps(fn)
    @jwt_required()
    def wrapper(*args, **kwargs):

        identity = get_jwt_identity()
        user = User.query.filter_by(username=identity).first()

        if not user or user.role != "admin":
            return jsonify({"error": "Admin access required"}), 403

        return fn(*args, **kwargs)

    return wrapper

# =====================================
# AUTH ROUTES (REGISTER + LOGIN)
# =====================================

@app.route("/api/register", methods=["POST"])
def register():
    data = request.json

    username = data.get("username")
    password = data.get("password")

    if User.query.filter_by(username=username).first():
        return jsonify({"error": "User already exists"}), 400

    user = User(username=username)
    user.set_password(password)

    db.session.add(user)
    db.session.commit()

    return jsonify({"message": "User registered successfully"})


@app.route("/api/login", methods=["POST"])
def login():
    data = request.json

    username = data.get("username")
    password = data.get("password")

    user = User.query.filter_by(username=username).first()

    if not user or not user.check_password(password):
        return jsonify({"error": "Invalid credentials"}), 401

    token = create_access_token(identity=username)

    return jsonify({"access_token": token})

# =====================================
# PROTECTED CV API ROUTES
# =====================================

@app.route("/api/cv", methods=["GET"])
@jwt_required()
def get_cv():
    profile = CVProfile.query.first()

    if not profile:
        return jsonify({"error": "CV not found"}), 404

    return jsonify({
        "full_name": profile.full_name,
        "title": profile.title,
        "skills": profile.skills,
        "projects": profile.projects
    })


@app.route("/api/cv/update", methods=["POST"])
@admin_required
def update_cv():
    data = request.json

    profile = CVProfile.query.first()
    if not profile:
        profile = CVProfile()

    profile.full_name = data.get("full_name")
    profile.title = data.get("title")
    profile.skills = data.get("skills")
    profile.projects = data.get("projects")

    db.session.add(profile)
    db.session.commit()

    return jsonify({"message": "CV updated successfully"})

# =====================================
# FRONTEND (HTML + JS FULL UI)
# =====================================

@app.route("/")
def home():
    return render_template_string("""
<!DOCTYPE html>
<html>
<head>
    <title>My CV Portfolio</title>
    <style>
        body {
            font-family: Arial;
            margin: 50px;
            background: #f4f4f4;
        }

        .card {
            background: white;
            padding: 20px;
            border-radius: 10px;
            width: 500px;
            box-shadow: 0px 0px 10px gray;
            margin-bottom: 20px;
        }

        input, button {
            padding: 10px;
            margin: 5px;
            width: 95%;
        }

        button {
            cursor: pointer;
            font-weight: bold;
        }

        pre {
            background: black;
            color: lime;
            padding: 15px;
            border-radius: 8px;
        }
    </style>
</head>

<body>

<h1>🔥 CV Backend + Frontend Portfolio App</h1>

<div class="card">
    <h2>Login</h2>

    <input id="username" placeholder="Username">
    <input id="password" type="password" placeholder="Password">

    <button onclick="login()">Login</button>
</div>

<div class="card">
    <h2>Protected CV Data</h2>

    <button onclick="loadCV()">Load My CV</button>

    <pre id="cvOutput">CV will appear here...</pre>
</div>

<script>
let token = "";

function login() {
    fetch("/api/login", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({
            username: document.getElementById("username").value,
            password: document.getElementById("password").value
        })
    })
    .then(res => res.json())
    .then(data => {
        token = data.access_token;
        alert("Login successful!");
    });
}

function loadCV() {
    fetch("/api/cv", {
        headers: {
            "Authorization": "Bearer " + token
        }
    })
    .then(res => res.json())
    .then(data => {
        document.getElementById("cvOutput").innerText =
            JSON.stringify(data, null, 4);
    });
}
</script>

</body>
</html>
    """)

# =====================================
# RUN SERVER ON PORT
# =====================================

if __name__ == "__main__":

    PORT = 5000   # 👈 CHANGE PORT HERE IF YOU WANT

    with app.app_context():
        db.create_all()

        # AUTO CREATE ADMIN USER
        if not User.query.filter_by(username="admin").first():
            admin = User(username="admin", role="admin")
            admin.set_password("admin123")

            db.session.add(admin)
            db.session.commit()

        # AUTO CREATE DEFAULT CV
        if not CVProfile.query.first():
            cv = CVProfile(
                full_name="Aleksa Popovic",
                title="Backend Engineer (Flask + JWT)",
                skills="Flask, JWT, SQLAlchemy, Security, Docker",
                projects="Secure Todo API, Auth System, CV Portfolio App"
            )
            db.session.add(cv)
            db.session.commit()

    print("===================================")
    print("🚀 CV APP RUNNING!")
    print(f"🌍 Open: http://localhost:{PORT}")
    print("===================================")

    app.run(host="0.0.0.0", port=PORT, debug=True)
