import os
import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Flask, request, session, redirect, url_for, render_template, flash
from functools import wraps

app = Flask(__name__)

app.secret_key = os.environ.get("SECRET_KEY", "change-this-secret-key")
TEACHER_PASSWORD = os.environ.get("TEACHER_PASSWORD")

DATABASE_URL = os.environ.get("DATABASE_URL")

STUDENTS = [
    ("AO0990032025", "ABREGO ORELLANA", "ELSY JAMILETH"),
    ("CM0140032025", "CARBAJAL MENA", "NELSON DANIEL"),
    ("CG1047032024", "CASTRO GOMEZ", "ANA PATRICIA"),
    ("CS0464032024", "CRUZ SERRANO", "CAMILA ALEXANDRA"),
    ("GA0828032014", "GARCIA DE ALVARENGA", "INGRID VANESSA"),
    ("GV0865032025", "GOMEZ VASQUEZ", "ALEJANDRO JOSE"),
    ("GR0794032025", "GUARDADO RECINOS", "JEFFERSON STEVENTH"),
    ("GH0490032025", "GUILLEN HERNANDEZ", "FRANCESCA PAOLA"),
    ("GM1038032025", "GUTIERREZ MARTINEZ", "DENNIS EDUARDO"),
    ("GS0931032024", "GUTIERREZ SEGURA", "RUBI MARIELOS"),
    ("JA0298032025", "JIMENEZ ALVARADO", "JULISSA MICHELLE"),
    ("LM1185032025", "LOPEZ MENJIVAR", "SELVIN ADONAY"),
    ("LS1177032024", "LOPEZ SORIANO", "YULIANA NOEMY"),
    ("MP0832032025", "MARTINEZ PINEDA", "STEVEN ALEXANDER"),
    ("NA0191032025", "NUÑEZ ANDASOL", "JOSE ROBERTO"),
    ("OG0903032025", "ORANTES GUARDADO", "MARTIR ALBERTO"),
    ("RG0891032025", "RODRIGUEZ GUEVARA", "KENIA ODALIS"),
    ("RR1102032025", "ROMERO ROJAS", "JEYSER NOEMY"),
    ("SM0162032025", "SANTAMARIA MARTINEZ", "BRANDON YUREM"),
    ("SG0319032025", "SANTOS GUARDADO", "JOSUE ADALBERTO"),
    ("SP0724032025", "SOLORZANO PERLERA", "WILBER JONATHAN"),
    ("TC0553032024", "TEJADA CASTANEDA", "DIEGO ANTONIO"),
    ("UQ0445032025", "URBINA QUIJADA", "ALEJANDRA GUADALUPE"),
    ("VM0376032025", "VILLALTA MENJIVAR", "CESAR AUGUSTO"),
    ("ZJ0472032024", "ZAVALA JACOBO", "TYRA GABRIELA")
]

PARTIALS = [
    ("1", "1.er Examen Parcial"),
    ("2", "2.º Examen Parcial"),
    ("3", "3.er Examen Parcial")
]


def db():
    return psycopg2.connect(DATABASE_URL)


def init_db():
    if not DATABASE_URL:
        return

    c = db()
    cur = c.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS students (
            code TEXT PRIMARY KEY,
            last_name TEXT NOT NULL,
            first_name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS grades (
            student_code TEXT NOT NULL,
            partial TEXT NOT NULL,
            grade DOUBLE PRECISION DEFAULT 0,
            prevention TEXT DEFAULT '',
            PRIMARY KEY (student_code, partial)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS appeals (
            id SERIAL PRIMARY KEY,
            student_code TEXT NOT NULL,
            partial TEXT NOT NULL,
            reason TEXT NOT NULL,
            status TEXT DEFAULT 'PENDIENTE',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    for code, last, first in STUDENTS:

        cur.execute("""
            INSERT INTO students (code, last_name, first_name, email)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (code) DO NOTHING
        """, (
            code,
            last,
            first,
            code + "@UNAB.EDU.SV"
        ))

        for partial, _ in PARTIALS:
            cur.execute("""
                INSERT INTO grades
                (student_code, partial, grade, prevention)
                VALUES (%s, %s, 0, '')
                ON CONFLICT (student_code, partial) DO NOTHING
            """, (code, partial))

    c.commit()
    cur.close()
    c.close()


def teacher_required(f):
    @wraps(f)
    def w(*args, **kwargs):
        if session.get("teacher"):
            return f(*args, **kwargs)
        return redirect(url_for("teacher_login"))
    return w


@app.route("/", methods=["GET", "POST"])
def index():

    if request.method == "POST":

        email = request.form.get("email", "").strip().upper()

        c = db()
        cur = c.cursor(cursor_factory=RealDictCursor)

        cur.execute(
            "SELECT * FROM students WHERE email = %s",
            (email,)
        )

        st = cur.fetchone()

        cur.close()
        c.close()

        if not st:
            flash(
                "El correo institucional no corresponde a un estudiante registrado."
            )
            return render_template("index.html")

        session["student_code"] = st["code"]

        return redirect(
            url_for("student", code=st["code"])
        )

    return render_template("index.html")


@app.route("/student/<code>")
def student(code):

    if (
        session.get("student_code") != code
        and not session.get("teacher")
    ):
        return redirect(url_for("index"))

    c = db()
    cur = c.cursor(cursor_factory=RealDictCursor)

    cur.execute(
        "SELECT * FROM students WHERE code = %s",
        (code,)
    )

    st = cur.fetchone()

    cur.execute("""
        SELECT *
        FROM grades
        WHERE student_code = %s
        ORDER BY partial
    """, (code,))

    grades = cur.fetchall()

    cur.close()
    c.close()

    return render_template(
        "student.html",
        st=st,
        grades=grades,
        partials=PARTIALS
    )


@app.post("/appeal")
def appeal():

    if not session.get("student_code"):
        return redirect(url_for("index"))

    reason = request.form.get("reason", "").strip()
    partial = request.form.get("partial", "")

    if (
        not reason
        or partial not in {"1", "2", "3"}
    ):
        flash(
            "Debe indicar el motivo de la inconformidad."
        )
        return redirect(
            url_for(
                "student",
                code=session["student_code"]
            )
        )

    c = db()
    cur = c.cursor()

    cur.execute("""
        INSERT INTO appeals
        (student_code, partial, reason)
        VALUES (%s, %s, %s)
    """, (
        session["student_code"],
        partial,
        reason
    ))

    c.commit()
    cur.close()
    c.close()

    return render_template("appeal_sent.html")


@app.route("/logout")
def logout():

    session.clear()

    return redirect(url_for("index"))


@app.route("/teacher/login", methods=["GET", "POST"])
def teacher_login():

    if request.method == "POST":

        password = request.form.get("password", "")

        if TEACHER_PASSWORD and password == TEACHER_PASSWORD:

            session["teacher"] = True

            return redirect(url_for("teacher"))

        flash("Contraseña incorrecta.")

    return render_template("teacher_login.html")


@app.route("/teacher")
@teacher_required
def teacher():

    selected = request.args.get("code") or STUDENTS[0][0]
    partial = request.args.get("partial") or "1"

    c = db()
    cur = c.cursor(cursor_factory=RealDictCursor)

    cur.execute(
        "SELECT * FROM students WHERE code = %s",
        (selected,)
    )

    st = cur.fetchone()

    cur.execute("""
        SELECT *
        FROM grades
        WHERE student_code = %s
        ORDER BY partial
    """, (selected,))

    grades = cur.fetchall()

    cur.execute("""
        SELECT *
        FROM appeals
        WHERE student_code = %s
        ORDER BY id DESC
    """, (selected,))

    appeals = cur.fetchall()

    cur.close()
    c.close()

    return render_template(
        "teacher.html",
        students=STUDENTS,
        st=st,
        grades=grades,
        appeals=appeals,
        selected=selected,
        partial=partial,
        partials=PARTIALS
    )


@app.post("/teacher/save")
@teacher_required
def teacher_save():

    code = request.form["code"]
    partial = request.form["partial"]

    try:
        grade = max(
            0,
            min(
                10,
                float(
                    request.form.get("grade", "0")
                )
            )
        )
    except:
        grade = 0

    prevention = request.form.get(
        "prevention",
        ""
    ).strip()

    c = db()
    cur = c.cursor()

    cur.execute("""
        UPDATE grades
        SET grade = %s,
            prevention = %s
        WHERE student_code = %s
          AND partial = %s
    """, (
        grade,
        prevention,
        code,
        partial
    ))

    c.commit()
    cur.close()
    c.close()

    flash("Cambios guardados correctamente.")

    return redirect(
        url_for(
            "teacher",
            code=code,
            partial=partial
        )
    )


@app.post("/teacher/appeal/<int:appeal_id>")
@teacher_required
def resolve_appeal(appeal_id):

    status = request.form.get("status")

    if status not in {
        "A LUGAR",
        "NO HA LUGAR"
    }:
        return redirect(
            url_for("teacher")
        )

    c = db()
    cur = c.cursor()

    cur.execute("""
        UPDATE appeals
        SET status = %s
        WHERE id = %s
    """, (
        status,
        appeal_id
    ))

    c.commit()
    cur.close()
    c.close()

    flash("Apelación resuelta.")

    return redirect(
        request.referrer
        or url_for("teacher")
    )


init_db()
