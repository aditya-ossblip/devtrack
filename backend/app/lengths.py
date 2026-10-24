"""Turn "too long for the column" into a message instead of a crash.

SQLite ignores VARCHAR lengths and stores whatever it is given. Postgres
enforces them: a 201-character issue title is refused by the database, and
without this the person who typed it would see "Something went wrong on our
end". Checking every string column just before it is written covers every
route at once, including ones added later, and keeps the limit in exactly one
place: the model.
"""

from sqlalchemy import String, event
from sqlalchemy.orm import Session

from .errors import ApiError

# Column names as a person would say them. Anything not listed is shown with
# its underscores turned into spaces.
LABELS = {
    'name': 'Name',
    'title': 'Title',
    'goal': 'Sprint goal',
    'labels': 'Labels',
    'email': 'Email',
    'text': 'Text',
    'key': 'Key',
    'filename': 'File name',
    'content_type': 'File type',
    'subject': 'Subject',
}


def _label(column_name: str) -> str:
    return LABELS.get(column_name, column_name.replace('_', ' ').capitalize())


def check_lengths(session, flush_context, instances) -> None:
    for obj in list(session.new) + list(session.dirty):
        mapper = getattr(obj, '__mapper__', None)
        if mapper is None:
            continue
        for column in mapper.columns:
            if not isinstance(column.type, String) or not column.type.length:
                continue
            value = getattr(obj, column.key, None)
            if isinstance(value, str) and len(value) > column.type.length:
                raise ApiError(
                    f'{_label(column.name)} is too long. '
                    f'Keep it to {column.type.length} characters or fewer.'
                )


def install() -> None:
    """Listen on every session. Safe to call more than once."""
    if not event.contains(Session, 'before_flush', check_lengths):
        event.listen(Session, 'before_flush', check_lengths)
