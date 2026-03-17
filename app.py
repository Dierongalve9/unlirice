from flask import Flask, jsonify, request, render_template
import sqlite3
import os

app = Flask(__name__)

# Use absolute path so Gunicorn on Render can find the DB
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH  = os.path.join(BASE_DIR, "students.db")

# ── DB helpers ────────────────────────────────────────────────────
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS students (
                id      INTEGER PRIMARY KEY AUTOINCREMENT,
                name    TEXT    NOT NULL,
                section TEXT    NOT NULL,
                grade   INTEGER NOT NULL,
                remarks TEXT    NOT NULL
            )
        """)
        count = conn.execute("SELECT COUNT(*) FROM students").fetchone()[0]
        if count == 0:
            seed = [
                ("Juan Dela Cruz",  "Zechariah", 85),
                ("Maria Santos",    "Stallman",  90),
                ("Pedro Reyes",     "Zion",      70),
                ("Ana Garcia",      "Zechariah", 78),
                ("Jose Mendoza",    "Genesis",   55),
                ("Luisa Bautista",  "Stallman",  92),
                ("Carlos Rivera",   "Exodus",    66),
                ("Rosa Aquino",     "Zion",      88),
                ("Miguel Torres",   "Genesis",   74),
                ("Elena Flores",    "Zechariah", 95),
                ("Ryan Dela Pena",  "Stallman",  81),
                ("Carla Vega",      "Exodus",    63),
            ]
            for name, section, grade in seed:
                remarks = "Pass" if grade >= 75 else "Fail"
                conn.execute(
                    "INSERT INTO students (name,section,grade,remarks) VALUES (?,?,?,?)",
                    (name, section, grade, remarks)
                )
        conn.commit()
    finally:
        conn.close()

# ── Frontend ──────────────────────────────────────────────────────
@app.route("/")
def index():
    return render_template("index.html")

# ── GET all students (with optional filters) ──────────────────────
@app.route("/api/students", methods=["GET"])
def get_students():
    search  = request.args.get("search", "").strip().lower()
    remarks = request.args.get("remarks", "").strip()
    section = request.args.get("section", "").strip()

    sql    = "SELECT * FROM students WHERE 1=1"
    params = []
    if search:
        sql += " AND (LOWER(name) LIKE ? OR LOWER(section) LIKE ?)"
        params += [f"%{search}%", f"%{search}%"]
    if remarks:
        sql += " AND remarks = ?"
        params.append(remarks)
    if section:
        sql += " AND section = ?"
        params.append(section)
    sql += " ORDER BY id DESC"

    conn = get_db()
    try:
        rows = conn.execute(sql, params).fetchall()
        return jsonify([dict(r) for r in rows])
    finally:
        conn.close()

# ── GET single student ────────────────────────────────────────────
@app.route("/api/students/<int:student_id>", methods=["GET"])
def get_student(student_id):
    conn = get_db()
    try:
        row = conn.execute("SELECT * FROM students WHERE id=?", (student_id,)).fetchone()
    finally:
        conn.close()
    if not row:
        return jsonify({"error": "Student not found"}), 404
    return jsonify(dict(row))

# ── POST add student ──────────────────────────────────────────────
@app.route("/api/students", methods=["POST"])
def add_student():
    data    = request.get_json(force=True, silent=True) or {}
    name    = str(data.get("name") or "").strip()
    section = str(data.get("section") or "").strip()
    grade   = data.get("grade")

    if not name:
        return jsonify({"error": "Name is required"}), 400
    try:
        grade = int(grade)
        if not (0 <= grade <= 100):
            raise ValueError
    except (TypeError, ValueError):
        return jsonify({"error": "Grade must be an integer between 0 and 100"}), 400

    remarks = "Pass" if grade >= 75 else "Fail"
    conn = get_db()
    try:
        cur = conn.execute(
            "INSERT INTO students (name,section,grade,remarks) VALUES (?,?,?,?)",
            (name, section, grade, remarks)
        )
        conn.commit()
        student = conn.execute("SELECT * FROM students WHERE id=?", (cur.lastrowid,)).fetchone()
        return jsonify({"message": "Student added successfully", "student": dict(student)}), 201
    finally:
        conn.close()

# ── PUT update student ────────────────────────────────────────────
@app.route("/api/students/<int:student_id>", methods=["PUT"])
def update_student(student_id):
    conn = get_db()
    try:
        if not conn.execute("SELECT id FROM students WHERE id=?", (student_id,)).fetchone():
            return jsonify({"error": "Student not found"}), 404

        data    = request.get_json(force=True, silent=True) or {}
        name    = str(data.get("name") or "").strip()
        section = str(data.get("section") or "").strip()
        grade   = data.get("grade")

        if not name:
            return jsonify({"error": "Name is required"}), 400
        try:
            grade = int(grade)
            if not (0 <= grade <= 100):
                raise ValueError
        except (TypeError, ValueError):
            return jsonify({"error": "Grade must be an integer between 0 and 100"}), 400

        remarks = "Pass" if grade >= 75 else "Fail"
        conn.execute(
            "UPDATE students SET name=?,section=?,grade=?,remarks=? WHERE id=?",
            (name, section, grade, remarks, student_id)
        )
        conn.commit()
        updated = conn.execute("SELECT * FROM students WHERE id=?", (student_id,)).fetchone()
        return jsonify({"message": "Student updated successfully", "student": dict(updated)})
    finally:
        conn.close()

# ── DELETE student ────────────────────────────────────────────────
@app.route("/api/students/<int:student_id>", methods=["DELETE"])
def delete_student(student_id):
    conn = get_db()
    try:
        if not conn.execute("SELECT id FROM students WHERE id=?", (student_id,)).fetchone():
            return jsonify({"error": "Student not found"}), 404
        conn.execute("DELETE FROM students WHERE id=?", (student_id,))
        conn.commit()
        return jsonify({"message": f"Student #{student_id} deleted successfully"})
    finally:
        conn.close()

# ── GET analytics summary ─────────────────────────────────────────
@app.route("/api/summary", methods=["GET"])
def summary():
    conn = get_db()
    try:
        rows   = conn.execute("SELECT * FROM students").fetchall()
        grades = [r["grade"] for r in rows]
        total  = len(grades)
        passed = sum(1 for g in grades if g >= 75)
        failed = total - passed
        avg    = round(sum(grades) / total, 1) if total else 0

        sections = {}
        for r in rows:
            s = sections.setdefault(r["section"], {"section": r["section"], "count": 0, "total_grade": 0, "passed": 0})
            s["count"]       += 1
            s["total_grade"] += r["grade"]
            if r["remarks"] == "Pass":
                s["passed"] += 1

        section_stats = [
            {
                "section":   s["section"],
                "count":     s["count"],
                "average":   round(s["total_grade"] / s["count"], 1),
                "passed":    s["passed"],
                "failed":    s["count"] - s["passed"],
                "pass_rate": round(s["passed"] / s["count"] * 100, 1),
            }
            for s in sections.values()
        ]

        brackets = [
            {"label": "90-100", "min": 90, "max": 100},
            {"label": "80-89",  "min": 80, "max": 89},
            {"label": "75-79",  "min": 75, "max": 79},
            {"label": "60-74",  "min": 60, "max": 74},
            {"label": "0-59",   "min":  0, "max": 59},
        ]
        distribution = [
            {"label": b["label"], "count": sum(1 for g in grades if b["min"] <= g <= b["max"])}
            for b in brackets
        ]

        return jsonify({
            "total":        total,
            "passed":       passed,
            "failed":       failed,
            "average":      avg,
            "pass_rate":    round(passed / total * 100, 1) if total else 0,
            "sections":     section_stats,
            "distribution": distribution,
        })
    finally:
        conn.close()

# ── Init DB on startup, then run ──────────────────────────────────
init_db()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
