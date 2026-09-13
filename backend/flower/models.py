from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from flower.db import Base


class SchemaInfo(Base):
    __tablename__ = "schema_info"
    spec_version: Mapped[str] = mapped_column(String, primary_key=True)
