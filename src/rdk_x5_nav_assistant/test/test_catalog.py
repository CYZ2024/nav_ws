import pytest

from rdk_x5_nav_assistant.catalog import (
    detect_command,
    find_product,
    load_yaml,
    normalize_text,
    product_by_id,
    product_by_tag_id,
)


@pytest.fixture
def catalog():
    return {
        "products": [
            {"id": "fanta_orange", "name": "芬达橙味汽水", "aliases": ["芬达"], "apriltag_id": 20, "shelf_id": "shelf_a"},
            {"id": "sprite", "name": "雪碧", "aliases": ["雪碧"], "apriltag_id": 21, "shelf_id": "shelf_a"},
        ]
    }


def test_normalize_text():
    assert normalize_text("  芬达橙味汽水  ") == "芬达橙味汽水"
    assert normalize_text("Fanta Orange!") == "fantaorange"


def test_detect_command():
    assert detect_command("停止") == "stop"
    assert detect_command("帮我找芬达") is None
    assert detect_command("确认拿到") == "confirm"


def test_find_product_by_name(catalog):
    assert find_product({"text": "芬达"}, catalog)["id"] == "fanta_orange"


def test_find_product_by_id(catalog):
    assert find_product({"product_id": "sprite"}, catalog)["id"] == "sprite"


def test_product_by_id(catalog):
    assert product_by_id("fanta_orange", catalog)["name"] == "芬达橙味汽水"
    assert product_by_id("nonexistent", catalog) is None


def test_product_by_tag_id(catalog):
    assert product_by_tag_id(20, catalog)["id"] == "fanta_orange"
    assert product_by_tag_id(999, catalog) is None
