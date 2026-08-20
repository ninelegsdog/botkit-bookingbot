from dataclasses import dataclass, field


@dataclass(frozen=True)
class Migration:
    version: int
    name: str
    statements: tuple[str, ...] = ()


class MigrationRegistry:
    def __init__(self) -> None:
        self._migrations: list[Migration] = []

    def add(self, migration: Migration) -> None:
        self._migrations.append(migration)

    @property
    def migrations(self) -> list[Migration]:
        return sorted(self._migrations, key=lambda m: m.version)
