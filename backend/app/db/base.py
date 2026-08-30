"""
SQLAlchemy declarative base.

All ORM models inherit from Base. This single Base instance lets Alembic
auto-detect all models for migration generation.
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
