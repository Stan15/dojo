import pytest
from dojo import db


@pytest.fixture
def temp_db(tmp_path):
    db_path = tmp_path / "dojo_test.sqlite3"
    db.init_db(db_path)
    return db_path


from sqlmodel import text, select
from dojo.db import Exercise

def test_tables_created_on_init(temp_db):
    with db.connect(temp_db) as conn:
        tables = [
            row[0]
            for row in conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table'")
            ).fetchall()
        ]
        assert "sources" in tables
        assert "campaigns" in tables
        assert "candidates" in tables
        assert "exercises" in tables


def test_sources_repository(temp_db):
    with db.connect(temp_db) as conn:
        src1 = db.save_source(
            conn,
            id="src_1",
            title="First Source",
            content="Hello world",
            kind="text",
            mission="Learn basic stuff",
        )
        assert src1["id"] == "src_1"
        assert src1["title"] == "First Source"
        assert src1["content"] == "Hello world"
        assert src1["kind"] == "text"
        assert src1["mission"] == "Learn basic stuff"
        assert src1["created_at"] is not None

        # Test ON CONFLICT DO UPDATE
        src1_updated = db.save_source(
            conn,
            id="src_1",
            title="First Source Updated",
            content="Hello world updated",
            kind="text",
            mission="Learn basic stuff updated",
        )
        assert src1_updated["title"] == "First Source Updated"
        assert src1_updated["content"] == "Hello world updated"
        assert src1_updated["mission"] == "Learn basic stuff updated"

        # Test get_source
        fetched = db.get_source(conn, "src_1")
        assert fetched == src1_updated

        # Test list_sources
        db.save_source(
            conn, id="src_2", title="Second", content="...", kind="file"
        )
        sources = db.list_sources(conn)
        assert len(sources) == 2
        assert sources[0]["id"] == "src_2"  # Ordered by created_at DESC


def test_candidates_repository(temp_db):
    with db.connect(temp_db) as conn:
        # Save a source first due to foreign key
        db.save_source(conn, id="src_1", title="S", content="C", kind="t")

        span = {"start_line": 5, "end_line": 10, "anchor_text": "Header"}
        cand1 = db.save_candidate(
            conn,
            id="cand_1",
            source_id="src_1",
            prompt="Question 1",
            answer="Answer 1",
            rubric={"score": 1},
            topic_path="math.calc",
            source_refs=span,
            difficulty="easy",
        )
        assert cand1["id"] == "cand_1"
        assert cand1["prompt"] == "Question 1"
        assert cand1["rubric"] == {"score": 1}
        assert cand1["source_refs"] == span
        assert cand1["difficulty"] == "easy"
        assert cand1["quality"] == "candidate"

        # Test list candidates
        db.save_candidate(
            conn,
            id="cand_2",
            source_id="src_1",
            prompt="Q2",
            topic_path="math.algebra",
            source_refs=span,
        )
        candidates = db.list_candidates(conn, "src_1")
        assert len(candidates) == 2

        # Test list candidates by topic
        calc_candidates = db.list_candidates(conn, "src_1", "math.calc")
        assert len(calc_candidates) == 1
        assert calc_candidates[0]["id"] == "cand_1"

        # Test get candidate
        assert db.get_candidate(conn, "cand_1") == cand1


def test_remove_candidate(temp_db):
    with db.connect(temp_db) as conn:
        db.save_source(conn, id="src_1", title="S", content="C", kind="t")
        db.save_candidate(
            conn,
            id="cand_1",
            source_id="src_1",
            prompt="Q",
            topic_path="topic",
            source_refs={},
        )
        removed = db.remove_candidate(conn, "cand_1")
        assert removed["id"] == "cand_1"
        assert db.get_candidate(conn, "cand_1") is None

        with pytest.raises(ValueError):
            db.remove_candidate(conn, "cand_non_existent")


def test_promote_candidate(temp_db):
    with db.connect(temp_db) as conn:
        db.save_source(conn, id="src_1", title="S", content="C", kind="t")
        span = {"start_line": 1, "end_line": 2, "anchor_text": "A"}
        db.save_candidate(
            conn,
            id="cand_1",
            source_id="src_1",
            prompt="Q",
            answer="A",
            rubric={"r": 1},
            topic_path="t",
            source_refs=span,
            difficulty="medium",
        )

        exercise = db.promote_candidate(conn, "cand_1")
        assert exercise["id"] == "ex_1"
        assert exercise["candidate_id"] == "cand_1"
        assert exercise["prompt"] == "Q"
        assert exercise["answer"] == "A"
        assert exercise["rubric"] == {"r": 1}
        assert exercise["topic_path"] == "t"
        assert exercise["source_refs"] == span
        assert exercise["difficulty"] == "medium"
        assert exercise["quality"] == "reviewed"

        # Ensure candidate is removed
        assert db.get_candidate(conn, "cand_1") is None

        # Ensure exercise exists in database
        ex_fetched = conn.exec(select(Exercise).where(Exercise.id == "ex_1")).first()
        assert ex_fetched is not None
        assert ex_fetched.prompt == "Q"


def test_campaigns_repository(temp_db):
    with db.connect(temp_db) as conn:
        plan = {
            "active_phase_index": 0,
            "phases": [
                {
                    "name": "Phase 1",
                    "target_topics": ["math"],
                    "strategy": "Learn basic math",
                }
            ],
        }
        camp = db.save_campaign(
            conn,
            id="camp_1",
            name="Math Study",
            topic_path="math",
            mission="Improve algebra speed",
            attack_plan=plan,
            active_phase_index=0,
        )
        assert camp["id"] == "camp_1"
        assert camp["name"] == "Math Study"
        assert camp["topic_path"] == "math"
        assert camp["mission"] == "Improve algebra speed"
        assert camp["attack_plan"] == plan
        assert camp["active_phase_index"] == 0

        # Test ON CONFLICT DO UPDATE
        camp_updated = db.save_campaign(
            conn,
            id="camp_1",
            name="Math Study Updated",
            topic_path="math.algebra",
            mission="Improve speed",
            attack_plan=plan,
            active_phase_index=1,
        )
        assert camp_updated["name"] == "Math Study Updated"
        assert camp_updated["topic_path"] == "math.algebra"
        assert camp_updated["active_phase_index"] == 1

        # Test get campaign
        assert db.get_campaign(conn, "camp_1") == camp_updated
