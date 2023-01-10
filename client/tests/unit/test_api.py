import pytest

from beiboot import api
from beiboot.types import BeibootRequest
from beiboot.configuration import __VERSION__


class TestReadBeiboots:
    def test_a_read_beiboot(self, operator):
        with pytest.raises(RuntimeError) as e:
            api.read(name="does-not-exist")
            assert str(e) == "The Beiboot does-not-exist does not exist"
        _ = api.create(BeibootRequest(name="test-read"))
        bbt = api.read(name="test-read")
        assert bbt.name == "test-read"
        assert bbt.labels == {"beiboot.getdeck.dev/client-version": __VERSION__}

    def test_b_read_labels_beiboot(self, operator):
        _ = api.create(
            BeibootRequest(
                name="test-read-labels", labels={"user-id": "123", "label1": "label2"}
            )
        )
        bbt = api.read(name="test-read-labels")
        assert bbt.name == "test-read-labels"
        assert bbt.labels == {
            "beiboot.getdeck.dev/client-version": __VERSION__,
            "user-id": "123",
            "label1": "label2",
        }

    def test_c_read_all_beiboot(self, operator):
        _all = api.read_all()
        assert len(_all) == 2
        _ = api.create(BeibootRequest(name="test-read-all", labels={"user-id": "456"}))
        _all = api.read_all()
        assert len(_all) == 3
        _filtered = api.read_all(labels={"user-id": "123", "label1": "label2"})
        assert len(_filtered) == 1
        _filtered1 = api.read_all(labels={"user-id": "123"})
        assert len(_filtered1) == 1
        _filtered2 = api.read_all(labels={"user-id": "456"})
        assert len(_filtered1) == 1

    def test_d_read_events(self, operator):
        beiboot = api.read("test-read-all")
        events = beiboot.events_by_timestamp
        assert type(events) == dict
