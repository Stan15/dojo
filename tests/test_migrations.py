import sqlite3
from dojo.db import init_db

def test_db_migration_adds_missing_columns(tmp_path):
    db_path = tmp_path / "dojo.sqlite3"
    # 1. Create a database with the old schema (attempts table missing the new columns)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE attempts (
            id VARCHAR PRIMARY KEY,
            session_id VARCHAR,
            exercise_id VARCHAR,
            source_id VARCHAR,
            prompt VARCHAR,
            user_answer VARCHAR,
            score FLOAT,
            latency_seconds FLOAT,
            created_at VARCHAR
        )
    """)
    conn.commit()
    conn.close()

    # 2. Run init_db which should run the migrations and create everything else
    init_db(db_path)

    # 3. Check that the columns now exist
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(attempts)")
    columns = {row[1] for row in cursor.fetchall()}
    conn.close()

    assert "skip_reason" in columns
    assert "feedback" in columns
    assert "campaign_id" in columns
    assert "consolidated" in columns


def test_db_migration_source_id_nullable(tmp_path):
    db_path = tmp_path / "dojo.sqlite3"
    # 1. Create a database where candidates table has source_id as NOT NULL
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE candidates (
            id VARCHAR PRIMARY KEY,
            source_id VARCHAR NOT NULL,
            prompt VARCHAR,
            answer VARCHAR,
            rubric VARCHAR,
            topic_path VARCHAR,
            source_refs VARCHAR,
            difficulty VARCHAR,
            quality VARCHAR,
            generation_run_id INTEGER,
            created_at VARCHAR
        )
    """)
    # Insert a dummy candidate to verify data copy works
    cursor.execute("""
        INSERT INTO candidates (id, source_id, prompt, topic_path, source_refs, quality, created_at)
        VALUES ('cand_1', 'src_1', 'Prompt', 'topic', '[]', 'candidate', '2026-06-16T04:39:56.493764+00:00')
    """)
    conn.commit()
    conn.close()

    # 2. Run init_db which should migrate candidates to make source_id nullable
    init_db(db_path)

    # 3. Check table info to verify notnull constraint is now 0
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(candidates)")
    columns = cursor.fetchall()
    
    # Verify candidate data is preserved
    cursor.execute("SELECT id, source_id FROM candidates")
    rows = cursor.fetchall()
    conn.close()

    source_id_col = [col for col in columns if col[1] == "source_id"][0]
    # col[3] is notnull (1 if NOT NULL, 0 if NULL)
    assert source_id_col[3] == 0
    
    # Assert data was copied correctly
    assert len(rows) == 1
    assert rows[0][0] == "cand_1"
    assert rows[0][1] == "src_1"
