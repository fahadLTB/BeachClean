import os
import sqlite3
from contextlib import closing
from datetime import datetime
import hashlib
import secrets
from pathlib import Path

import pandas as pd
import streamlit as st

# =============================
# Config
# =============================
DB_PATH = os.getenv("DB_PATH", "student_app.db")
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "uploads"))
UPLOAD_DIR.mkdir(exist_ok=True)

ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@school.local")
ADMIN_NAME = os.getenv("ADMIN_NAME", "School Admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")  # Change in production!

st.set_page_config(page_title="Student Info Portal", page_icon="🎓", layout="wide")

# =============================
# Helpers: Auth
# =============================

def hash_password(password: str, salt: str | None = None) -> tuple[str, str]:
    """Return (salt, hash). If salt not provided, a new one is generated."""
    if salt is None:
        salt = secrets.token_hex(16)
    pw_hash = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), 200_000
    ).hex()
    return salt, pw_hash


def verify_password(password: str, salt: str, expected_hash: str) -> bool:
    _, test_hash = hash_password(password, salt)
    return secrets.compare_digest(test_hash, expected_hash)


# =============================
# Database
# =============================

SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('admin','student')),
    salt TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS students (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER UNIQUE NOT NULL,
    full_name TEXT,
    grade TEXT,
    section TEXT,
    roll_no TEXT,
    parent_name TEXT,
    parent_phone TEXT,
    emergency_contact TEXT,
    address TEXT,
    allergies TEXT,
    health_notes TEXT,
    subjects TEXT,
    photo_path TEXT,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
"""


def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)


def init_db():
    with closing(get_conn()) as conn:
        conn.executescript(SCHEMA_SQL)
        conn.commit()


def seed_admin():
    with closing(get_conn()) as conn:
        cur = conn.cursor()
        cur.execute("SELECT id FROM users WHERE email=?", (ADMIN_EMAIL,))
        row = cur.fetchone()
        if row is None:
            salt, pw_hash = hash_password(ADMIN_PASSWORD)
            cur.execute(
                "INSERT INTO users (email, name, role, salt, password_hash, created_at) VALUES (?,?,?,?,?,?)",
                (
                    ADMIN_EMAIL,
                    ADMIN_NAME,
                    "admin",
                    salt,
                    pw_hash,
                    datetime.utcnow().isoformat(),
                ),
            )
            conn.commit()


# =============================
# Repos / Data Access
# =============================

def create_student_user(email: str, name: str, password: str) -> int | None:
    with closing(get_conn()) as conn:
        cur = conn.cursor()
        try:
            salt, pw_hash = hash_password(password)
            cur.execute(
                "INSERT INTO users (email, name, role, salt, password_hash, created_at) VALUES (?,?,?,?,?,?)",
                (email, name, "student", salt, pw_hash, datetime.utcnow().isoformat()),
            )
            user_id = cur.lastrowid
            # Create empty student profile
            cur.execute(
                "INSERT INTO students (user_id, updated_at) VALUES (?,?)",
                (user_id, datetime.utcnow().isoformat()),
            )
            conn.commit()
            return user_id
        except sqlite3.IntegrityError:
            return None


def get_user_by_email(email: str):
    with closing(get_conn()) as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, email, name, role, salt, password_hash FROM users WHERE email=?",
            (email,),
        )
        row = cur.fetchone()
        if row:
            keys = ["id", "email", "name", "role", "salt", "password_hash"]
            return dict(zip(keys, row))
        return None


def get_student_profile(user_id: int):
    with closing(get_conn()) as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM students WHERE user_id=?", (user_id,))
        row = cur.fetchone()
        if row:
            cols = [
                "id",
                "user_id",
                "full_name",
                "grade",
                "section",
                "roll_no",
                "parent_name",
                "parent_phone",
                "emergency_contact",
                "address",
                "allergies",
                "health_notes",
                "subjects",
                "photo_path",
                "updated_at",
            ]
            return dict(zip(cols, row))
        return None


def update_student_profile(user_id: int, data: dict):
    fields = [
        "full_name",
        "grade",
        "section",
        "roll_no",
        "parent_name",
        "parent_phone",
        "emergency_contact",
        "address",
        "allergies",
        "health_notes",
        "subjects",
        "photo_path",
    ]
    set_clause = ", ".join(f"{f}=?" for f in fields) + ", updated_at=?"
    values = [data.get(f) for f in fields] + [datetime.utcnow().isoformat(), user_id]
    with closing(get_conn()) as conn:
        cur = conn.cursor()
        cur.execute(
            f"UPDATE students SET {set_clause} WHERE user_id=?",
            tuple(values),
        )
        conn.commit()


def list_all_students_df() -> pd.DataFrame:
    with closing(get_conn()) as conn:
        df = pd.read_sql_query(
            """
            SELECT s.id, u.name as account_name, u.email, s.full_name, s.grade, s.section, s.roll_no,
                   s.parent_name, s.parent_phone, s.emergency_contact, s.address, s.allergies,
                   s.health_notes, s.subjects, s.photo_path, s.updated_at
            FROM students s
            JOIN users u ON u.id = s.user_id
            ORDER BY s.updated_at DESC
            """,
            conn,
        )
    return df


def delete_student(user_email: str) -> bool:
    with closing(get_conn()) as conn:
        cur = conn.cursor()
        cur.execute("SELECT id FROM users WHERE email=? AND role='student'", (user_email,))
        row = cur.fetchone()
        if not row:
            return False
        user_id = row[0]
        cur.execute("DELETE FROM users WHERE id=?", (user_id,))  # cascades to students
        conn.commit()
        return True


# =============================
# UI: Auth Forms
# =============================

def login_form():
    st.subheader("Login")
    email = st.text_input("Email")
    password = st.text_input("Password", type="password")
    if st.button("Sign in", type="primary"):
        user = get_user_by_email(email.strip().lower())
        if user and verify_password(password, user["salt"], user["password_hash"]):
            st.session_state["auth_user"] = {
                "id": user["id"],
                "email": user["email"],
                "name": user["name"],
                "role": user["role"],
            }
            st.experimental_rerun()
        else:
            st.error("Invalid email or password")


def signup_form():
    st.subheader("Student Sign Up")
    with st.form("signup_form"):
        name = st.text_input("Full Name")
        email = st.text_input("School Email")
        password = st.text_input("Password", type="password")
        confirm = st.text_input("Confirm Password", type="password")
        submitted = st.form_submit_button("Create Account")
    if submitted:
        if not (name and email and password and confirm):
            st.warning("Please fill all fields")
            return
        if password != confirm:
            st.warning("Passwords do not match")
            return
        user_id = create_student_user(email.strip().lower(), name.strip(), password)
        if user_id is None:
            st.error("Email already registered")
            return
        st.success("Account created. Please login.")


def ensure_logged_in():
    if "auth_user" not in st.session_state:
        return False
    return True


def logout_button():
    if st.sidebar.button("Logout"):
        st.session_state.pop("auth_user", None)
        st.experimental_rerun()


# =============================
# UI: Student Dashboard
# =============================

def student_dashboard(user):
    st.header("Student Profile")
    prof = get_student_profile(user["id"]) or {}

    colA, colB = st.columns([1, 2])
    with colA:
        uploaded = st.file_uploader("Upload Photo (optional)", type=["png", "jpg", "jpeg"], key="photo")
        photo_path = prof.get("photo_path")
        if uploaded is not None:
            filename = f"{user['id']}_{int(datetime.utcnow().timestamp())}_{uploaded.name}"
            dest = UPLOAD_DIR / filename
            with open(dest, "wb") as f:
                f.write(uploaded.read())
            photo_path = str(dest)
            st.success("Photo uploaded")
        if photo_path and Path(photo_path).exists():
            st.image(photo_path, caption="Current Photo", width=180)

    with colB:
        with st.form("student_form", clear_on_submit=False):
            full_name = st.text_input("Full Name", value=prof.get("full_name") or user["name"])
            grade = st.text_input("Grade (e.g., 7, 8, 9)", value=prof.get("grade") or "")
            section = st.text_input("Section", value=prof.get("section") or "")
            roll_no = st.text_input("Roll No.", value=prof.get("roll_no") or "")
            parent_name = st.text_input("Parent/Guardian Name", value=prof.get("parent_name") or "")
            parent_phone = st.text_input("Parent/Guardian Phone", value=prof.get("parent_phone") or "")
            emergency_contact = st.text_input("Emergency Contact", value=prof.get("emergency_contact") or "")
            address = st.text_area("Address", value=prof.get("address") or "")
            allergies = st.text_area("Allergies (if any)", value=prof.get("allergies") or "")
            health_notes = st.text_area("Health Notes (optional)", value=prof.get("health_notes") or "")
            subjects = st.text_area("Subjects (comma separated)", value=prof.get("subjects") or "")

            submitted = st.form_submit_button("Save Profile", type="primary")
        if submitted:
            data = {
                "full_name": full_name.strip(),
                "grade": grade.strip(),
                "section": section.strip(),
                "roll_no": roll_no.strip(),
                "parent_name": parent_name.strip(),
                "parent_phone": parent_phone.strip(),
                "emergency_contact": emergency_contact.strip(),
                "address": address.strip(),
                "allergies": allergies.strip(),
                "health_notes": health_notes.strip(),
                "subjects": subjects.strip(),
                "photo_path": photo_path,
            }
            update_student_profile(user["id"], data)
            st.success("Profile saved!")

    st.info("Only you and admins can view this data. Admins cannot change your password.")


# =============================
# UI: Admin Dashboard
# =============================

def admin_dashboard(user):
    st.header("Admin Dashboard")
    df = list_all_students_df()

    # Filters
    with st.expander("Filters", expanded=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            grade_f = st.text_input("Grade contains")
        with col2:
            name_f = st.text_input("Name contains")
        with col3:
            email_f = st.text_input("Email contains")

    filt_df = df.copy()
    if grade_f:
        filt_df = filt_df[filt_df["grade"].fillna("").str.contains(grade_f, case=False)]
    if name_f:
        filt_df = filt_df[
            filt_df["full_name"].fillna("").str.contains(name_f, case=False)
            | filt_df["account_name"].fillna("").str.contains(name_f, case=False)
        ]
    if email_f:
        filt_df = filt_df[filt_df["email"].fillna("").str.contains(email_f, case=False)]

    st.dataframe(filt_df, use_container_width=True, hide_index=True)

    # Export
    csv = filt_df.to_csv(index=False).encode("utf-8")
    st.download_button("Download CSV", data=csv, file_name="students_export.csv", mime="text/csv")

    st.subheader("Danger Zone")
    del_email = st.text_input("Delete student by email")
    if st.button("Delete Student", type="secondary"):
        if del_email:
            ok = delete_student(del_email.strip().lower())
            if ok:
                st.success("Student deleted")
                st.experimental_rerun()
            else:
                st.error("Student not found")
        else:
            st.warning("Enter an email")

    st.caption("Admins can view and export data, and delete student accounts if necessary.")


# =============================
# Main App
# =============================

def main():
    init_db()
    seed_admin()

    st.title("🎓 Student Information Portal")
    st.write("Students can sign up, fill their profile, and view/update only their own data. Admins can view/export all.")

    user = st.session_state.get("auth_user")

    if not user:
        tab1, tab2 = st.tabs(["Login", "Student Sign Up"])
        with tab1:
            login_form()
        with tab2:
            signup_form()
        st.stop()

    # Sidebar
    st.sidebar.success(f"Logged in as {user['name']} ({user['role']})")
    logout_button()

    if user["role"] == "student":
        student_dashboard(user)
    elif user["role"] == "admin":
        admin_dashboard(user)
    else:
        st.error("Unknown role")


if __name__ == "__main__":
    main()
