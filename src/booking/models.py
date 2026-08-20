from src.core.migrations import Migration, MigrationRegistry

MIGRATION = Migration(
    version=1,
    name="booking_init",
    statements=(
        """CREATE TABLE IF NOT EXISTS services (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            duration_min INTEGER NOT NULL DEFAULT 60,
            price INTEGER NOT NULL DEFAULT 0,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )""",
        """CREATE TABLE IF NOT EXISTS weekly_schedule (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            day_of_week INTEGER NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL
        )""",
        """CREATE TABLE IF NOT EXISTS slots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            service_id INTEGER NOT NULL REFERENCES services(id),
            date TEXT NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            is_booked INTEGER NOT NULL DEFAULT 0,
            UNIQUE(service_id, date, start_time)
        )""",
        """CREATE TABLE IF NOT EXISTS bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            service_id INTEGER NOT NULL REFERENCES services(id),
            slot_id INTEGER UNIQUE REFERENCES slots(id),
            client_user_id INTEGER NOT NULL,
            client_name TEXT,
            client_phone TEXT,
            booking_date TEXT NOT NULL,
            start_time TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )""",
        """CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            booking_id INTEGER NOT NULL REFERENCES bookings(id),
            provider TEXT NOT NULL,
            amount INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            external_id TEXT,
            UNIQUE(external_id)
        )""",
        """CREATE TABLE IF NOT EXISTS feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            service_id INTEGER NOT NULL REFERENCES services(id),
            rating INTEGER NOT NULL,
            text TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )""",
        """CREATE TABLE IF NOT EXISTS reminders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            booking_id INTEGER NOT NULL REFERENCES bookings(id),
            user_id INTEGER NOT NULL,
            fire_at TEXT NOT NULL,
            text TEXT NOT NULL,
            is_active INTEGER NOT NULL DEFAULT 1
        )""",
        "CREATE INDEX IF NOT EXISTS idx_bookings_user_status ON bookings(client_user_id, status)",
        "CREATE INDEX IF NOT EXISTS idx_slots_service_date ON slots(service_id, date, is_booked)",
        "CREATE INDEX IF NOT EXISTS idx_payments_external ON payments(external_id)",
    ),
)


def register_migrations(registry: MigrationRegistry) -> None:
    registry.add(MIGRATION)
