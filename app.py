from flask import Flask, jsonify, request, render_template
import sqlite3

app = Flask(__name__)

# ─────────────────────────────────────────────────────────────────
#  In-memory SQLite — works 100% on Render (no disk write needed)
#  NOTE: Data resets on each deploy/restart — for persistent data
#        upgrade to PostgreSQL via Render's managed DB addon.
# ─────────────────────────────────────────────────────────────────
_DB = sqlite3.connect(":memory:", check_same_thread=False)
_DB.row_factory = sqlite3.Row

def get_db():
    return _DB

def init_db():
    db = get_db()
    db.execute("""
        CREATE TABLE IF NOT EXISTS students (
            id      INTEGER PRIMARY KEY AUTOINCREMENT,
            name    TEXT    NOT NULL,
            section TEXT    NOT NULL,
            grade   INTEGER NOT NULL,
            remarks TEXT    NOT NULL
        )
    """)
    db.commit()

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
        ("Jerome Lim",      "Genesis",   77),
        ("Patricia Sy",     "Zion",      84),
        ("Kevin Tan",       "Exodus",    58),
    ]
    for name, section, grade in seed:
        remarks = "Pass" if grade >= 75 else "Fail"
        db.execute(
            "INSERT INTO students (name,section,grade,remarks) VALUES (?,?,?,?)",
            (name, section, grade, remarks)
        )
    db.commit()

# ── Frontend ──────────────────────────────────────────────────────
@app.route("/")
def index():
    return render_template("index.html")

# ── GET all / filtered students ───────────────────────────────────
@app.route("/api/students", methods=["GET"])
def get_students():
    search  = request.args.get("search",  "").strip().lower()
    remarks = request.args.get("remarks", "").strip()
    section = request.args.get("section", "").strip()

    sql, params = "SELECT * FROM students WHERE 1=1", []
    if search:
        sql += " AND (LOWER(name) LIKE ? OR LOWER(section) LIKE ?)"
        params += [f"%{search}%", f"%{search}%"]
    if remarks:
        sql += " AND remarks=?";  params.append(remarks)
    if section:
        sql += " AND section=?";  params.append(section)
    sql += " ORDER BY id DESC"

    rows = get_db().execute(sql, params).fetchall()
    return jsonify([dict(r) for r in rows])

# ── GET one student ───────────────────────────────────────────────
@app.route("/api/students/<int:sid>", methods=["GET"])
def get_student(sid):
    row = get_db().execute("SELECT * FROM students WHERE id=?", (sid,)).fetchone()
    if not row:
        return jsonify({"error": "Student not found"}), 404
    return jsonify(dict(row))

# ── POST create student ───────────────────────────────────────────
@app.route("/api/students", methods=["POST"])
def add_student():
    data    = request.get_json(force=True, silent=True) or {}
    name    = str(data.get("name")    or "").strip()
    section = str(data.get("section") or "").strip()
    grade   = data.get("grade")

    if not name:
        return jsonify({"error": "Name is required"}), 400
    try:
        grade = int(grade)
        assert 0 <= grade <= 100
    except Exception:
        return jsonify({"error": "Grade must be 0–100"}), 400

    remarks = "Pass" if grade >= 75 else "Fail"
    db  = get_db()
    cur = db.execute(
        "INSERT INTO students (name,section,grade,remarks) VALUES (?,?,?,?)",
        (name, section, grade, remarks)
    )
    db.commit()
    row = db.execute("SELECT * FROM students WHERE id=?", (cur.lastrowid,)).fetchone()
    return jsonify({"message": "Student added", "student": dict(row)}), 201

# ── PUT update student ────────────────────────────────────────────
@app.route("/api/students/<int:sid>", methods=["PUT"])
def update_student(sid):
    db = get_db()
    if not db.execute("SELECT id FROM students WHERE id=?", (sid,)).fetchone():
        return jsonify({"error": "Student not found"}), 404

    data    = request.get_json(force=True, silent=True) or {}
    name    = str(data.get("name")    or "").strip()
    section = str(data.get("section") or "").strip()
    grade   = data.get("grade")

    if not name:
        return jsonify({"error": "Name is required"}), 400
    try:
        grade = int(grade)
        assert 0 <= grade <= 100
    except Exception:
        return jsonify({"error": "Grade must be 0–100"}), 400

    remarks = "Pass" if grade >= 75 else "Fail"
    db.execute(
        "UPDATE students SET name=?,section=?,grade=?,remarks=? WHERE id=?",
        (name, section, grade, remarks, sid)
    )
    db.commit()
    row = db.execute("SELECT * FROM students WHERE id=?", (sid,)).fetchone()
    return jsonify({"message": "Student updated", "student": dict(row)})

# ── DELETE student ────────────────────────────────────────────────
@app.route("/api/students/<int:sid>", methods=["DELETE"])
def delete_student(sid):
    db = get_db()
    if not db.execute("SELECT id FROM students WHERE id=?", (sid,)).fetchone():
        return jsonify({"error": "Student not found"}), 404
    db.execute("DELETE FROM students WHERE id=?", (sid,))
    db.commit()
    return jsonify({"message": f"Student #{sid} deleted"})

# ── GET analytics summary ─────────────────────────────────────────
@app.route("/api/summary", methods=["GET"])
def summary():
    rows   = get_db().execute("SELECT * FROM students").fetchall()
    grades = [r["grade"] for r in rows]
    total  = len(grades)
    passed = sum(1 for g in grades if g >= 75)
    avg    = round(sum(grades) / total, 1) if total else 0

    secs = {}
    for r in rows:
        s = secs.setdefault(r["section"], {"section": r["section"], "count": 0, "total": 0, "passed": 0})
        s["count"] += 1; s["total"] += r["grade"]
        if r["remarks"] == "Pass": s["passed"] += 1

    brackets = [
        ("90–100", 90, 100), ("80–89", 80, 89), ("75–79", 75, 79),
        ("60–74",  60,  74), ("0–59",   0,  59),
    ]

    return jsonify({
        "total":    total,
        "passed":   passed,
        "failed":   total - passed,
        "average":  avg,
        "pass_rate": round(passed / total * 100, 1) if total else 0,
        "sections": [
            {
                "section":   s["section"],
                "count":     s["count"],
                "average":   round(s["total"] / s["count"], 1),
                "passed":    s["passed"],
                "failed":    s["count"] - s["passed"],
                "pass_rate": round(s["passed"] / s["count"] * 100, 1),
            }
            for s in secs.values()
        ],
        "distribution": [
            {"label": lbl, "count": sum(1 for g in grades if lo <= g <= hi)}
            for lbl, lo, hi in brackets
        ],
    })

# ── Boot ──────────────────────────────────────────────────────────
init_db()

if __name__ == "__main__":
    import os
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)
