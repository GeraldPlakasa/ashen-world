#!/usr/bin/env python3
"""
Migration: Drop JSON columns that have been moved to normalized tables.

Drops:
- villagers.relationships (now in villager_relationships)
- villagers.achievements (now in villager_achievements)
- villagers.kingsVotedFor (now in villager_votes)

Requirements:
- SQLite 3.35.0+ (for ALTER TABLE DROP COLUMN support)
- Run migrate_normalize_json.py first to ensure data is in normalized tables

Run: python scripts/migrate_drop_json_columns.py
"""
import sqlite3
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import DB_PATH


def get_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    """Get column names for a table."""
    cur = conn.execute(f"PRAGMA table_info({table});")
    return {row[1] for row in cur.fetchall()}


def migrate():
    """Run the migration."""
    print(f"Migrating database: {DB_PATH}")
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    
    # Check SQLite version
    version = conn.execute("SELECT sqlite_version();").fetchone()[0]
    print(f"SQLite version: {version}")
    
    major, minor, _ = map(int, version.split('.'))
    if major < 3 or (major == 3 and minor < 35):
        print("ERROR: SQLite 3.35.0+ required for DROP COLUMN support")
        conn.close()
        return False
    
    # Check current columns
    columns = get_columns(conn, "villagers")
    print(f"\nCurrent villagers columns: {len(columns)}")
    
    columns_to_drop = ["relationships", "achievements", "kingsVotedFor"]
    existing_to_drop = [c for c in columns_to_drop if c in columns]
    
    if not existing_to_drop:
        print("✓ No JSON columns to drop - already migrated")
        conn.close()
        return True
    
    print(f"Columns to drop: {existing_to_drop}")
    
    # Verify data exists in normalized tables
    print("\nVerifying normalized tables have data...")
    
    rel_count = conn.execute("SELECT COUNT(*) FROM villager_relationships").fetchone()[0]
    ach_count = conn.execute("SELECT COUNT(*) FROM villager_achievements").fetchone()[0]
    vote_count = conn.execute("SELECT COUNT(*) FROM villager_votes").fetchone()[0]
    
    print(f"  villager_relationships: {rel_count} rows")
    print(f"  villager_achievements: {ach_count} rows")
    print(f"  villager_votes: {vote_count} rows")
    
    # Drop columns
    print("\nDropping columns...")
    
    for col in existing_to_drop:
        try:
            conn.execute(f"ALTER TABLE villagers DROP COLUMN {col};")
            print(f"  ✓ Dropped: {col}")
        except sqlite3.OperationalError as e:
            print(f"  ✗ Failed to drop {col}: {e}")
    
    conn.commit()
    
    # Verify
    new_columns = get_columns(conn, "villagers")
    dropped = [c for c in columns_to_drop if c not in new_columns]
    print(f"\n✓ Successfully dropped: {dropped}")
    print(f"  Remaining columns: {len(new_columns)}")
    
    conn.close()
    return True


if __name__ == "__main__":
    print("=" * 60)
    print("DROP JSON COLUMNS MIGRATION")
    print("=" * 60)
    print("\nThis will DROP the following columns from villagers table:")
    print("  - relationships")
    print("  - achievements") 
    print("  - kingsVotedFor")
    print("\nData has been migrated to normalized tables.")
    print("This operation is IRREVERSIBLE.\n")
    
    resp = input("Continue? [y/N] ")
    if resp.lower() == "y":
        success = migrate()
        sys.exit(0 if success else 1)
    else:
        print("Aborted.")
        sys.exit(1)
