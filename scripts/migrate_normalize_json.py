#!/usr/bin/env python3
"""
Migration: Normalize JSON fields to separate tables.

Creates:
- villager_relationships (villager_id, other_id, score)
- villager_achievements (villager_id, achievement_id)
- villager_votes (villager_id, king_id)

Run: python scripts/migrate_normalize_json.py
"""
import json
import sqlite3
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import DB_PATH


def migrate():
    """Run the migration."""
    print(f"Migrating database: {DB_PATH}")
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    
    # Create new tables
    print("\n1. Creating new tables...")
    
    cur.execute("""
        CREATE TABLE IF NOT EXISTS villager_relationships (
            villager_id INTEGER NOT NULL,
            other_id INTEGER NOT NULL,
            score INTEGER DEFAULT 0,
            PRIMARY KEY (villager_id, other_id)
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_vr_villager ON villager_relationships(villager_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_vr_other ON villager_relationships(other_id)")
    print("   ✓ villager_relationships")
    
    cur.execute("""
        CREATE TABLE IF NOT EXISTS villager_achievements (
            villager_id INTEGER NOT NULL,
            achievement_id TEXT NOT NULL,
            earned_day INTEGER DEFAULT 0,
            PRIMARY KEY (villager_id, achievement_id)
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_va_villager ON villager_achievements(villager_id)")
    print("   ✓ villager_achievements")
    
    cur.execute("""
        CREATE TABLE IF NOT EXISTS villager_votes (
            villager_id INTEGER NOT NULL,
            king_id INTEGER NOT NULL,
            vote_day INTEGER DEFAULT 0,
            PRIMARY KEY (villager_id, king_id)
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_vv_villager ON villager_votes(villager_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_vv_king ON villager_votes(king_id)")
    print("   ✓ villager_votes")
    
    conn.commit()
    
    # Migrate existing data
    print("\n2. Migrating existing JSON data...")
    
    cur.execute("SELECT id, relationships, achievements, kingsVotedFor FROM villagers")
    rows = cur.fetchall()
    
    rel_count = 0
    ach_count = 0
    vote_count = 0
    
    for row in rows:
        vid = row["id"]
        
        # Migrate relationships
        rel_str = row["relationships"] or "{}"
        try:
            rels = json.loads(rel_str) if rel_str else {}
            for other_id, score in rels.items():
                cur.execute("""
                    INSERT OR REPLACE INTO villager_relationships (villager_id, other_id, score)
                    VALUES (?, ?, ?)
                """, (vid, int(other_id), int(score)))
                rel_count += 1
        except (json.JSONDecodeError, TypeError, ValueError):
            pass
        
        # Migrate achievements
        ach_str = row["achievements"] or "[]"
        try:
            achs = json.loads(ach_str) if ach_str else []
            for ach_id in achs:
                cur.execute("""
                    INSERT OR IGNORE INTO villager_achievements (villager_id, achievement_id)
                    VALUES (?, ?)
                """, (vid, str(ach_id)))
                ach_count += 1
        except (json.JSONDecodeError, TypeError):
            pass
        
        # Migrate kingsVotedFor
        vote_str = row["kingsVotedFor"] or "[]"
        try:
            votes = json.loads(vote_str) if vote_str else []
            for king_id in votes:
                cur.execute("""
                    INSERT OR IGNORE INTO villager_votes (villager_id, king_id)
                    VALUES (?, ?)
                """, (vid, int(king_id)))
                vote_count += 1
        except (json.JSONDecodeError, TypeError, ValueError):
            pass
    
    conn.commit()
    
    print(f"   ✓ Migrated {rel_count} relationships")
    print(f"   ✓ Migrated {ach_count} achievements")
    print(f"   ✓ Migrated {vote_count} votes")
    
    # Verify
    print("\n3. Verification...")
    cur.execute("SELECT COUNT(*) FROM villager_relationships")
    print(f"   villager_relationships: {cur.fetchone()[0]} rows")
    cur.execute("SELECT COUNT(*) FROM villager_achievements")
    print(f"   villager_achievements: {cur.fetchone()[0]} rows")
    cur.execute("SELECT COUNT(*) FROM villager_votes")
    print(f"   villager_votes: {cur.fetchone()[0]} rows")
    
    conn.close()
    print("\n✓ Migration complete!")
    print("\nNote: Old JSON columns kept for backward compatibility.")
    print("After code update, you can drop them with:")
    print("  ALTER TABLE villagers DROP COLUMN relationships;")
    print("  ALTER TABLE villagers DROP COLUMN achievements;")
    print("  ALTER TABLE villagers DROP COLUMN kingsVotedFor;")


if __name__ == "__main__":
    resp = input("This will create new tables and migrate JSON data. Continue? [y/N] ")
    if resp.lower() == "y":
        migrate()
    else:
        print("Aborted.")
