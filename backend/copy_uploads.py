"""Copy uploaded files into the storage configured in backend/.env.

    npm run files:copy                    # from backend/instance/uploads
    npm run files:copy -- path/to/folder  # from another folder

Use it once when files move somewhere new: going live (your computer's
uploads -> Supabase), or switching to a different bucket later (download the
old bucket to a folder first, then run this against that folder).

It goes through the database's list of files, so only files DevTrack knows
about are copied, under the same names. Files that are missing from the folder
are listed, not guessed at. The source folder is only read, never changed.
Safe to run twice: a file already there is simply written again.
Works the same on Windows, macOS and Linux.
"""

import mimetypes
import sys
from pathlib import Path

from app import create_app
from app.config import INSTANCE_DIR
from app.extensions import db
from app.models import Attachment
from app.storage import LocalStorage, get_storage


def main() -> None:
    source_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else INSTANCE_DIR / 'uploads'
    if not source_dir.is_dir():
        print(f'\n  !!  No folder at {source_dir}\n')
        sys.exit(1)

    app = create_app()
    with app.app_context():
        target = get_storage()
        if isinstance(target, LocalStorage) and Path(target.directory).resolve() == source_dir.resolve():
            print('\n  !!  STORAGE_BACKEND points at the same folder. Set it to s3 first.\n')
            sys.exit(1)

        source = LocalStorage(source_dir)
        rows = db.session.scalars(db.select(Attachment).order_by(Attachment.id)).all()
        print(f'Copying {len(rows)} file(s) from {source_dir} to {target.name} storage')

        copied, missing = 0, []
        for row in rows:
            data = source.read(row.stored_name)
            if data is None:
                missing.append(f'{row.filename} ({row.stored_name})')
                continue
            content_type = row.content_type or mimetypes.guess_type(row.filename)[0] or 'application/octet-stream'
            target.save(row.stored_name, data, content_type)
            copied += 1

        print(f'  copied   {copied}')
        if missing:
            print(f'  missing  {len(missing)} (not in the folder, so not copied):')
            for name in missing:
                print(f'           {name}')
    print('\nDone. The source folder was not changed.')


if __name__ == '__main__':
    main()
