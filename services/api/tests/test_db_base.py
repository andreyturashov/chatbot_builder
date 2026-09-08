from app.db.base import Base, TableNameMixin, UUIDPrimaryKeyMixin


class DummyItem(Base, TableNameMixin, UUIDPrimaryKeyMixin):
    pass


def test_table_name_mixin() -> None:
    assert DummyItem.__tablename__ == "dummyitems"
