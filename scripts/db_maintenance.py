#!/usr/bin/env python3
"""
Database Maintenance Utility for Ashen World

Usage:
    python scripts/db_maintenance.py [command]

Commands:
    status    - Show database status and statistics
    vacuum    - Optimize database (reclaim space)
    integrity - Check database integrity
    cleanup   - Remove old graveyard entries (>50 years dead)
    backup    - Create a backup of the database
"""
import os
import sys
import shutil
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from src.repositories.base import db_conn, init_db


def get_db_size():
    """Get database file size in MB."""
    if os.path.exists(config.DB_PATH):
        return os.path.getsize(config.DB_PATH) / (1024 * 1024)
    return 0


def show_status():
    """Show database status and statistics."""
    print("=" * 50)
    print("ASHEN WORLD DATABASE STATUS")
    print("=" * 50)
    
    print(f"\nDatabase Path: {config.DB_PATH}")
    print(f"Database Size: {get_db_size():.2f} MB")
    
    init_db()
    with db_conn() as conn:
        # Count villagers
        alive = conn.execute("SELECT COUNT(*) FROM villagers WHERE alive = 1").fetchone()[0]
        dead = conn.execute("SELECT COUNT(*) FROM villagers WHERE alive = 0").fetchone()[0]
        total = alive + dead
        print(f"\nVillagers Table:")
        print(f"  - Alive: {alive}")
        print(f"  - Dead (pending cleanup): {dead}")
        print(f"  - Total: {total}")
        
        # Count graveyard
        graveyard = conn.execute("SELECT COUNT(*) FROM graveyard").fetchone()[0]
        print(f"\nGraveyard Table: {graveyard} entries")
        
        # Count users
        users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        print(f"Users Table: {users} entries")
        
        # Count yearly stats
        years = conn.execute("SELECT COUNT(*) FROM yearly_stats").fetchone()[0]
        print(f"Yearly Stats: {years} years recorded")
        
        # World state
        world = conn.execute("SELECT value FROM world_state WHERE key='day_payload'").fetchone()
        if world:
            import json
            data = json.loads(world[0])
            print(f"\nWorld State:")
            print(f"  - Current Day: {data.get('total_day', 1)}")
            print(f"  - Year: {data.get('year', 1)}")
            print(f"  - Weather: {data.get('weather', 'sunny')}")
        
        # Bank state
        bank = conn.execute("SELECT value FROM bank_state WHERE key='bank_payload'").fetchone()
        if bank:
            import json
            data = json.loads(bank[0])
            print(f"\nBank State:")
            print(f"  - Balance: {data.get('balance', 0)} coins")
            print(f"  - Tax Rate: {data.get('tax_rate', 0.10) * 100:.1f}%")
            print(f"  - Quest History: {len(data.get('quest_history', []))} quests")
    
    print("\n" + "=" * 50)


def vacuum_db():
    """Optimize database by running VACUUM."""
    print("Running VACUUM to optimize database...")
    size_before = get_db_size()
    
    init_db()
    with db_conn() as conn:
        conn.execute("VACUUM")
    
    size_after = get_db_size()
    saved = size_before - size_after
    print(f"Done! Size: {size_before:.2f} MB -> {size_after:.2f} MB (saved {saved:.2f} MB)")


def check_integrity():
    """Check database integrity."""
    print("Checking database integrity...")
    init_db()
    with db_conn() as conn:
        result = conn.execute("PRAGMA integrity_check").fetchone()[0]
        if result == "ok":
            print("✓ Database integrity check PASSED")
        else:
            print(f"✗ Database integrity issue: {result}")


def cleanup_graveyard():
    """Remove very old graveyard entries to save space."""
    print("Cleaning up old graveyard entries...")
    init_db()
    
    with db_conn() as conn:
        # Get current day
        world = conn.execute("SELECT value FROM world_state WHERE key='day_payload'").fetchone()
        if not world:
            print("No world state found!")
            return
        
        import json
        data = json.loads(world[0])
        current_day = data.get('total_day', 1)
        
        # Remove entries older than 50 years (4500 days)
        cutoff_day = current_day - (50 * config.DAYS_PER_YEAR)
        if cutoff_day < 1:
            print("World is too young for cleanup (< 50 years)")
            return
        
        before = conn.execute("SELECT COUNT(*) FROM graveyard").fetchone()[0]
        conn.execute("DELETE FROM graveyard WHERE born_day < ?", (cutoff_day,))
        after = conn.execute("SELECT COUNT(*) FROM graveyard").fetchone()[0]
        
        removed = before - after
        print(f"Removed {removed} old graveyard entries (born before day {cutoff_day})")


def backup_db():
    """Create a backup of the database."""
    if not os.path.exists(config.DB_PATH):
        print("No database to backup!")
        return
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = f"{config.DB_PATH}.backup_{timestamp}"
    
    print(f"Creating backup: {backup_path}")
    shutil.copy2(config.DB_PATH, backup_path)
    print(f"✓ Backup created ({get_db_size():.2f} MB)")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return
    
    command = sys.argv[1].lower()
    
    if command == "status":
        show_status()
    elif command == "vacuum":
        vacuum_db()
    elif command == "integrity":
        check_integrity()
    elif command == "cleanup":
        cleanup_graveyard()
    elif command == "backup":
        backup_db()
    else:
        print(f"Unknown command: {command}")
        print(__doc__)


if __name__ == "__main__":
    main()
