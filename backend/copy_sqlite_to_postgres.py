"""Copy everything from the old SQLite file into Postgres.

    npm run db:copy-sqlite                  # from backend/instance/devtrack.db
    npm run db:copy-sqlite -- path/to/other.db

Run it once, after pointing DATABASE_URL at Postgres and running
`npm run db:upgrade` there. It refuses to start unless:

  - DATABASE_URL is Postgres,
  - both databases are on the same migration (so the columns line up), and
  - the Postgres tables are empty (so nothing gets copied twice).

The SQLite file is only read, never changed, so it stays as a backup.
Works the same on Windows, macOS and Linux.
"""

import sys
from pathlib import Path

from sqlalchemy import create_engine, func, inspect, select, text, update

from app import create_app
from app.config import INSTANCE_DIR
from app.extensions import db


def fail(message: str) -> None:
    print(f'\n  !!  {message}\n')
    sys.exit(1)


def migration_version(connection) -> str | None:
    if not inspect(connection).has_table('alembic_version'):
        return None
    return connection.execute(text('SELECT version_num FROM alembic_version')).scalar()


def main() -> None:
    source_path = Path(sys.argv[1]) if len(sys.argv) > 1 else INSTANCE_DIR / 'devtrack.db'
    if not source_path.exists():
        fail(f'No SQLite database at {source_path}.')

    app = create_app()
    target_url = app.config['SQLALCHEMY_DATABASE_URI']
    if not str(target_url).startswith('postgresql'):
        fail('DATABASE_URL in backend/.env does not point at Postgres yet.')

    source = create_engine(f'sqlite:///{source_path}')

    with app.app_context():
        target = db.engine
        tables = db.metadata.sorted_tables

        with source.connect() as src, target.connect() as dst:
            src_version, dst_version = migration_version(src), migration_version(dst)
            if dst_version is None:
                fail('Postgres has no tables yet. Run:  npm run db:upgrade')
            if src_version != dst_version:
                fail(
                    f'The two databases are on different migrations '
                    f'(SQLite {src_version}, Postgres {dst_version}). '
                    'Run npm run db:upgrade against both first.'
                )
            for table in tables:
                if dst.execute(select(func.count()).select_from(table)).scalar():
                    fail(f'Postgres already has rows in "{table.name}". '
                         'This only copies into an empty database.')

        print(f'Copying {source_path.name} -> Postgres ({dst_version})')

        # One transaction: either everything arrives or nothing does.
        with source.connect() as src, target.begin() as dst:
            for table in tables:
                if not inspect(src).has_table(table.name):
                    continue
                rows = [dict(row._mapping) for row in src.execute(select(table))]

                # issues.epic_id points at another issue, which may come later
                # in the same table. Insert without it, then fill it in.
                epics = {}
                if table.name == 'issues':
                    for row in rows:
                        if row.get('epic_id') is not None:
                            epics[row['id']] = row['epic_id']
                            row['epic_id'] = None

                if rows:
                    dst.execute(table.insert(), rows)
                for issue_id, epic_id in epics.items():
                    dst.execute(update(table).where(table.c.id == issue_id).values(epic_id=epic_id))

                print(f'  {table.name:<22} {len(rows):>6} rows')

            # Postgres hands out ids from a sequence that knows nothing about
            # the rows just inserted with explicit ids. Move each one past the
            # highest id, or the next new row collides with a copied one.
            for table in tables:
                if 'id' not in table.c or not table.c.id.primary_key:
                    continue
                dst.execute(text(
                    f"SELECT setval(pg_get_serial_sequence('{table.name}', 'id'), "
                    f"COALESCE((SELECT MAX(id) FROM {table.name}), 0) + 1, false)"
                ))

    print('\nDone. Your SQLite file was not changed; keep it as a backup.')


if __name__ == '__main__':
    main()
