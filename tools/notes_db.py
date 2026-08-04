import os
import sqlite3
from loguru import logger

DB_PATH = "database/notes.sqlite"


def init_db():
    """Initializes the SQLite database with FTS5 for fast text search."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()

        # Standard table for storage
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS voice_notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                raw_transcript TEXT NOT NULL,
                tags TEXT
            )
        """)

        # FTS5 Virtual Table for instant keyword search
        cursor.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS voice_notes_fts USING fts5(
                raw_transcript,
                tags,
                content='voice_notes',
                content_rowid='id'
            )
        """)
        conn.commit()
        logger.info("SQLite Database and FTS5 index initialized.")


async def save_note_tool(arguments: dict) -> str:
    transcript = arguments.get("transcript")
    tags = arguments.get("tags", "")

    if not transcript:
        return "Error: transcript is required."

    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO voice_notes (raw_transcript, tags) VALUES (?, ?)",
                (transcript, tags),
            )
            rowid = cursor.lastrowid

            # SQLite requires manual insert into the FTS table if using external content tables
            cursor.execute(
                "INSERT INTO voice_notes_fts (rowid, raw_transcript, tags) VALUES (?, ?, ?)",
                (rowid, transcript, tags),
            )
            conn.commit()
            return f"System: Note saved successfully with ID {rowid}."
    except Exception as e:
        logger.error(f"DB Insert Error: {e}")
        return "System: Failed to save the note."


async def search_notes_tool(arguments: dict) -> str:
    query = arguments.get("query")

    if not query:
        return "Error: search query is required."

    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            # FTS5 MATCH query joined with the main table to get timestamps
            cursor.execute(
                """
                SELECT v.timestamp, f.raw_transcript, f.tags
                FROM voice_notes_fts f
                JOIN voice_notes v ON f.rowid = v.id
                WHERE voice_notes_fts MATCH ?
                ORDER BY rank LIMIT 5
                """,
                (query,),
            )

            results = cursor.fetchall()
            if not results:
                return f"System: No notes found matching '{query}'."

            formatted = [f"[{row[0]}] (Tags: {row[2]}) {row[1]}" for row in results]
            return "System: Found the following notes:\n" + "\n".join(formatted)

    except Exception as e:
        logger.error(f"DB Search Error: {e}")
        return "System: Failed to search notes."
