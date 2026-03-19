#!/usr/bin/env python3
"""
Migration script to fix TEXT columns that should be INTEGER.

This fixes columns that were created before they were added to INT_FIELDS:
- huntWins: TEXT -> INTEGER
- huntWinsYear: TEXT -> INTEGER

SQLite doesn't support ALTER COLUMN, so we:
1. Create new table with correct schema
2. Copy data with type conversion
3. Drop old table
4. Rename new table
5. Recreate indexes

Run this script once to fix existing databases.
New databases will be created correctly automatically.

Usage: python scripts/migrate_fix_int_columns.py
"""

import os
import sys
import sqlite3
import json

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config


def get_column_info(conn, table_name):
    """Get column names and types for a table."""
    cur = conn.execute(f"PRAGMA table_info({table_name});")
    return {row[1]: row[2] for row in cur.fetchall()}


def migrate_villagers_table(conn):
    """Fix villagers table column types."""
    
    # Get current schema
    columns = get_column_info(conn, "villagers")
    
    # Check if migration needed
    needs_migration = False
    for field in ["huntWins", "huntWinsYear"]:
        if field in columns and columns[field].upper() == "TEXT":
            print(f"  - {field}: TEXT -> INTEGER (needs fix)")
            needs_migration = True
        elif field in columns:
            print(f"  - {field}: {columns[field]} (OK)")
    
    if not needs_migration:
        print("  No migration needed for villagers table.")
        return False
    
    print("\n  Migrating villagers table...")
    
    # Build new column definitions
    col_defs = []
    col_names = []
    for f in config.FIELDNAMES:
        col_names.append(f)
        if f == "id":
            col_defs.append("id INTEGER PRIMARY KEY")
        elif f in config.INT_FIELDS:
            col_defs.append(f"{f} INTEGER DEFAULT 0")
        else:
            col_defs.append(f"{f} TEXT DEFAULT ''")
    
    # Create new table
    conn.execute(f"""
        CREATE TABLE villagers_new (
            {", ".join(col_defs)}
        );
    """)
    
    # Copy data with type conversion
    # For INT_FIELDS, use CAST to convert TEXT to INTEGER
    select_cols = []
    for f in config.FIELDNAMES:
        if f in config.INT_FIELDS and f != "id":
            # Handle empty strings and NULL
            select_cols.append(f"COALESCE(NULLIF(CAST({f} AS INTEGER), ''), 0) AS {f}")
        else:
            select_cols.append(f)
    
    # Actually, SQLite CAST handles this automatically, but let's be explicit
    # for TEXT -> INTEGER conversion with empty string handling
    insert_cols = []
    for f in config.FIELDNAMES:
        if f in config.INT_FIELDS and f != "id":
            insert_cols.append(f"""
                CASE 
                    WHEN {f} IS NULL OR {f} = '' THEN 0
                    ELSE CAST({f} AS INTEGER)
                END
            """)
        else:
            insert_cols.append(f)
    
    conn.execute(f"""
        INSERT INTO villagers_new ({", ".join(col_names)})
        SELECT {", ".join(insert_cols)}
        FROM villagers;
    """)
    
    # Get row count
    count = conn.execute("SELECT COUNT(*) FROM villagers_new;").fetchone()[0]
    print(f"  Copied {count} rows")
    
    # Drop old table and rename new
    conn.execute("DROP TABLE villagers;")
    conn.execute("ALTER TABLE villagers_new RENAME TO villagers;")
    
    # Recreate indexes
    conn.execute("CREATE INDEX IF NOT EXISTS idx_villagers_alive ON villagers(alive);")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_villagers_owner ON villagers(owner);")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_villagers_family ON villagers(family);")
    
    print("  Migration complete!")
    return True


def verify_migration(conn):
    """Verify the migration was successful."""
    columns = get_column_info(conn, "villagers")
    
    print("\nVerification:")
    all_good = True
    for field in config.INT_FIELDS:
        if field in columns:
            expected = "INTEGER"
            actual = columns[field].upper()
            status = "✓" if actual == expected else "✗"
            if actual != expected:
                all_good = False
            print(f"  {status} {field}: {actual}")
    
    return all_good


def main():
    print("=" * 60)
    print("Ashen World Database Migration")
    print("Fix TEXT columns that should be INTEGER")
    print("=" * 60)
    
    db_path = config.DB_PATH
    print(f"\nDatabase: {db_path}")
    
    if not os.path.exists(db_path):
        print("Database does not exist. Nothing to migrate.")
        return
    
    # Backup recommendation
    print("\n⚠️  BACKUP RECOMMENDED before running migration!")
    print(f"   cp {db_path} {db_path}.backup")
    
    response = input("\nProceed with migration? [y/N]: ").strip().lower()
    if response != 'y':
        print("Migration cancelled.")
        return
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    
    try:
        print("\nChecking villagers table...")
        migrated = migrate_villagers_table(conn)
        
        if migrated:
            conn.commit()
            verify_migration(conn)
        
        print("\n" + "=" * 60)
        print("Done!")
        print("=" * 60)
        
    except Exception as e:
        conn.rollback()
        print(f"\n❌ Error during migration: {e}")
        print("Changes have been rolled back.")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
