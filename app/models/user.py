from sqlalchemy import Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.mixins import CreatedAtMixin, IdMixin


# Inheritance order: mixins first, Base last. This class gets `id` and
# `created_at` from the mixins and becomes a table because of Base.
class User(IdMixin, CreatedAtMixin, Base):
    __tablename__ = "users"  # the real table name in Postgres (plural)

    # unique=True -> UNIQUE constraint "uq_users_email". The application must
    # lowercase emails before saving, or "A@x.com" and "a@x.com" both get in.
    email: Mapped[str] = mapped_column(Text, unique=True)

    # Only ever a hash (argon2/bcrypt) - never the plaintext password.
    password_hash: Mapped[str] = mapped_column(Text)

    # No relationship() attributes yet: relationships are a Python-side
    # convenience and do not change the database. The ForeignKeys on other
    # tables are what define the schema. Add relationships when an API needs them.
