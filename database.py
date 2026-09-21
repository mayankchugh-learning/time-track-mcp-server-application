"""
TimeTrack's persistence layer -- SQLite, shared by the website and the MCP
server, exactly like RecipeBox's was. One real, professional use case this
time: logging billable hours against projects, and summarizing them.
"""
import os
import sqlite3
import tempfile
from pathlib import Path

# Next to the code on a writable laptop checkout. Horizon packages the
# checkout read-only after import-time init_db() baked a seeded file into
# the artifact — SQLite can still READ that file, but INSERT fails with
# "attempt to write a readonly database" because it also needs a journal
# in the same directory. Fall back to the OS temp dir in that case.
_LOCAL_DB_PATH = Path(__file__).resolve().parent / "timetrack.db"
_TEMP_DB_PATH = Path(tempfile.gettempdir()) / "timetrack.db"


def _path_is_sqlite_writable(path: Path) -> bool:
    """True when SQLite can write the db file and create a journal beside it."""
    probe = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, probe = tempfile.mkstemp(prefix=".timetrack_write_probe_", dir=path.parent)
        os.close(fd)
        if path.exists():
            with path.open("r+b"):
                pass
        return True
    except OSError:
        return False
    finally:
        if probe:
            try:
                os.remove(probe)
            except OSError:
                pass


def _resolve_db_path() -> Path:
    candidate = Path(os.environ.get("TIMETRACK_DB_PATH", _LOCAL_DB_PATH))
    if _path_is_sqlite_writable(candidate):
        return candidate
    return _TEMP_DB_PATH


DB_PATH = _resolve_db_path()


def get_connection():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    already_exists = DB_PATH.exists()
    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS time_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_name TEXT NOT NULL,
            project TEXT NOT NULL,
            entry_date TEXT NOT NULL,
            hours REAL NOT NULL,
            description TEXT NOT NULL DEFAULT ''
        )
    """)
    if already_exists:
        conn.close()
        return
    count = conn.execute("SELECT COUNT(*) FROM time_entries").fetchone()[0]
    if count == 0:
        seed = [
            ("Asha Patel", "Website Redesign", "2026-09-08", 6.5, "Homepage layout"),
            ("Asha Patel", "Website Redesign", "2026-09-09", 7.0, "Mobile responsive fixes"),
            ("Asha Patel", "Client Onboarding", "2026-09-10", 3.0, "Kickoff call + notes"),
            ("Rahul Mehta", "Website Redesign", "2026-09-08", 5.5, "API integration"),
            ("Rahul Mehta", "Internal Tools", "2026-09-09", 8.0, "Dashboard bug fixes"),
        ]
        conn.executemany(
            "INSERT INTO time_entries (employee_name, project, entry_date, hours, description) "
            "VALUES (?, ?, ?, ?, ?)",
            seed,
        )
        conn.commit()
    conn.close()


def _row_to_dict(row) -> dict:
    return {
        "id": row["id"],
        "employee_name": row["employee_name"],
        "project": row["project"],
        "entry_date": row["entry_date"],
        "hours": row["hours"],
        "description": row["description"],
    }


def list_all_entries() -> list[dict]:
    conn = get_connection()
    rows = conn.execute("SELECT * FROM time_entries ORDER BY entry_date DESC, id DESC").fetchall()
    conn.close()
    return [_row_to_dict(r) for r in rows]


def log_time(employee_name: str, project: str, entry_date: str, hours: float, description: str = "") -> dict:
    if hours <= 0:
        raise ValueError("hours must be a positive number")
    conn = get_connection()
    cursor = conn.execute(
        "INSERT INTO time_entries (employee_name, project, entry_date, hours, description) "
        "VALUES (?, ?, ?, ?, ?)",
        (employee_name, project, entry_date, hours, description),
    )
    conn.commit()
    new_id = cursor.lastrowid
    row = conn.execute("SELECT * FROM time_entries WHERE id = ?", (new_id,)).fetchone()
    conn.close()
    return _row_to_dict(row)


def get_timesheet(employee_name: str, start_date: str | None = None, end_date: str | None = None) -> list[dict]:
    conn = get_connection()
    query = "SELECT * FROM time_entries WHERE employee_name = ?"
    params: list = [employee_name]
    if start_date:
        query += " AND entry_date >= ?"
        params.append(start_date)
    if end_date:
        query += " AND entry_date <= ?"
        params.append(end_date)
    query += " ORDER BY entry_date"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [_row_to_dict(r) for r in rows]

def execute_query(query: str, params: list = []) -> list[dict]:
    conn = get_connection()
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [_row_to_dict(r) for r in rows]

def list_projects() -> list[str]:
    conn = get_connection()
    rows = conn.execute("SELECT DISTINCT project FROM time_entries ORDER BY project").fetchall()
    conn.close()
    return [r["project"] for r in rows]


def get_project_summary(project: str) -> dict:
    conn = get_connection()
    rows = conn.execute(
        "SELECT employee_name, SUM(hours) as total_hours FROM time_entries "
        "WHERE project = ? GROUP BY employee_name ORDER BY employee_name",
        (project,),
    ).fetchall()
    conn.close()
    if not rows:
        raise ValueError(f"No time logged against project '{project}'")
    by_employee = {r["employee_name"]: r["total_hours"] for r in rows}
    return {
        "project": project,
        "total_hours": sum(by_employee.values()),
        "by_employee": by_employee,
    }
