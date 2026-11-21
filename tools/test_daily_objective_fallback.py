"""Daily objectives use the shipped content database when loose XML is absent."""
import pytest

from test_competiciones import world
import daily_events
import house_services


@pytest.fixture(autouse=True)
def missing_xml(monkeypatch):
    house_services.monster_identity.cache_clear()
    original = house_services.xml_rows
    monkeypatch.setattr(house_services, 'xml_rows', lambda name: {} if name == 'monster.xml' else original(name))
    monkeypatch.setattr(daily_events, '_ROOMS', {})
    yield
    house_services.monster_identity.cache_clear()


@pytest.mark.parametrize('identifier,sprite', [(9238, 42107), (9264, 43294), (9359, 43294), (9360, 43294), (23221, 43294)])
def test_official_identity_is_present_in_shipped_database(identifier, sprite):
    name, actual = house_services.monster_identity(identifier)
    assert name and actual == sprite


def test_available_xml_remains_preferred(monkeypatch):
    monkeypatch.setattr(house_services, 'xml_rows', lambda name: {9238: {'名稱': 'Original XML', '圖號': '42108'}})
    assert house_services.monster_identity(9238) == ('Original XML', 42108)


def test_missing_extraction_directory_also_uses_database(monkeypatch):
    def missing(name):
        raise FileNotFoundError(name)
    monkeypatch.setattr(house_services, 'xml_rows', missing)
    assert house_services.monster_identity(9238) == ('Baby Slarm', 42107)


@pytest.mark.parametrize('stage,identifier,hp,count', [(178, 9238, 5500000, 4), (376, 23221, 1800000000, 1)])
def test_daily_clock_builds_native_objectives_without_keyerror(world, stage, identifier, hp, count):
    daily_events.iniciar(stage, registration=0)
    current = daily_events.actual(stage)
    room = daily_events.room(current)
    objectives = [monster for monster in room.monstruos.values() if getattr(monster, 'daily_objective', False)]
    assert len(objectives) == count
    assert all(monster.npc_type == identifier and monster.hp_max == hp for monster in objectives)
    daily_events.cron()
    assert daily_events.room(current) is room
