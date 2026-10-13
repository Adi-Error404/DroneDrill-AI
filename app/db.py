"""DroneDrill AI - Database Layer (SQLite).

Manages storage for trainees, training sessions, simulation events,
skill cells encountered, and scenario fingerprints.
"""

from pathlib import Path
import sqlite3
import json
from typing import Optional, Set, Tuple, Any

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = BASE_DIR / "data" / "dronedrill.db"


def get_db_path(custom_path: Optional[str] = None) -> Path:
    """Resolve database file path."""
    if custom_path:
        return Path(custom_path)
    return DEFAULT_DB_PATH


def get_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    """Create and return a SQLite database connection with row factory."""
    path = get_db_path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: Optional[str] = None) -> None:
    """Initialize database tables."""
    conn = get_connection(db_path)
    cursor = conn.cursor()

    # 1. Trainees table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS trainees (
            id TEXT PRIMARY KEY,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    # 2. Sessions table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            session_id TEXT PRIMARY KEY,
            trainee_id TEXT NOT NULL,
            scenario_id TEXT NOT NULL,
            cell TEXT NOT NULL,
            difficulty_index REAL NOT NULL,
            started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(trainee_id) REFERENCES trainees(id)
        );
    """)

    # 3. Events table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            event_type TEXT NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            payload TEXT,
            FOREIGN KEY(session_id) REFERENCES sessions(session_id)
        );
    """)

    # 4. Skill cells table (tracks cells seen per trainee)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS skill_cells (
            trainee_id TEXT NOT NULL,
            cell TEXT NOT NULL,
            seen_count INTEGER DEFAULT 1,
            last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (trainee_id, cell),
            FOREIGN KEY(trainee_id) REFERENCES trainees(id)
        );
    """)

    # 5. Scenario fingerprints table (for deduplication / repeated detection)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS scenario_fingerprints (
            fingerprint TEXT PRIMARY KEY,
            scenario_id TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    conn.commit()
    conn.close()


def record_trainee(trainee_id: str, db_path: Optional[str] = None) -> None:
    """Ensure trainee is registered."""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR IGNORE INTO trainees (id) VALUES (?);",
        (trainee_id,),
    )
    conn.commit()
    conn.close()


def record_session(
    session_id: str,
    trainee_id: str,
    scenario_id: str,
    cell: Any,
    difficulty_index: float,
    db_path: Optional[str] = None,
) -> None:
    """Record a newly started training session."""
    cell_str = json.dumps(list(cell)) if not isinstance(cell, str) else cell
    record_trainee(trainee_id, db_path=db_path)

    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO sessions (session_id, trainee_id, scenario_id, cell, difficulty_index)
        VALUES (?, ?, ?, ?, ?);
        """,
        (session_id, trainee_id, scenario_id, cell_str, float(difficulty_index)),
    )
    conn.commit()
    conn.close()


def record_cell_seen(
    trainee_id: str,
    cell: Any,
    db_path: Optional[str] = None,
) -> None:
    """Record that a trainee has encountered a specific condition cell."""
    cell_str = json.dumps(list(cell)) if not isinstance(cell, str) else cell
    record_trainee(trainee_id, db_path=db_path)

    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO skill_cells (trainee_id, cell, seen_count, last_seen)
        VALUES (?, ?, 1, CURRENT_TIMESTAMP)
        ON CONFLICT(trainee_id, cell) DO UPDATE SET
            seen_count = seen_count + 1,
            last_seen = CURRENT_TIMESTAMP;
        """,
        (trainee_id, cell_str),
    )
    conn.commit()
    conn.close()


def get_seen_cells(trainee_id: str, db_path: Optional[str] = None) -> Set[Tuple[str, ...]]:
    """Fetch all unique condition cells seen by a trainee."""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT cell FROM skill_cells WHERE trainee_id = ?;",
        (trainee_id,),
    )
    rows = cursor.fetchall()
    conn.close()

    seen: Set[Tuple[str, ...]] = set()
    for row in rows:
        cell_raw = row["cell"]
        try:
            parsed = json.loads(cell_raw)
            seen.add(tuple(parsed))
        except Exception:
            seen.add(tuple(cell_raw.split(":")))
    return seen


def has_fingerprint(fingerprint: str, db_path: Optional[str] = None) -> bool:
    """Check if a scenario fingerprint already exists in the database."""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT 1 FROM scenario_fingerprints WHERE fingerprint = ? LIMIT 1;",
        (fingerprint,),
    )
    row = cursor.fetchone()
    conn.close()
    return row is not None


def record_fingerprint(
    fingerprint: str,
    scenario_id: str,
    db_path: Optional[str] = None,
) -> bool:
    """Record a fingerprint. Returns True if new, False if it was already recorded."""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO scenario_fingerprints (fingerprint, scenario_id) VALUES (?, ?);",
            (fingerprint, scenario_id),
        )
        conn.commit()
        inserted = True
    except sqlite3.IntegrityError:
        inserted = False
    finally:
        conn.close()
    return inserted


def record_event(
    session_id: str,
    event_type: str,
    payload: Optional[Any] = None,
    db_path: Optional[str] = None,
) -> None:
    """Record a simulation event in the events table."""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    payload_str = json.dumps(payload) if payload is not None and not isinstance(payload, str) else payload
    cursor.execute(
        "INSERT INTO events (session_id, event_type, payload) VALUES (?, ?, ?);",
        (session_id, event_type, payload_str),
    )
    conn.commit()
    conn.close()


# Initialize database automatically on module import
init_db()
