import pytest

from beiboot import api
from beiboot.types import BeibootRequest


class TestReadBeiboots:
    def test_a_read_beiboot(self, operator):
        with pytest.raises(RuntimeError) as e:
            api.read(name="does-not-exist")
            assert str(e) == "The Beiboot does-not-exist does not exist"
        _ = api.create(BeibootRequest(name="test-read"))
        bbt = api.read(name="test-read")
        assert bbt.name == "test-read"

    def test_b_read_all_beiboot(self, operator):
        _all = api.read_all()
        assert len(_all) == 1
        _ = api.create(BeibootRequest(name="test-read-all"))
        _all = api.read_all()
        assert len(_all) == 2

    def test_c_read_events(self, operator):
        beiboot = api.read("test-read-all")
        events = beiboot.events_by_timestamp
        assert type(events) == dict
