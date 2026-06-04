import pytest

from rdk_x5_nav_assistant.grasp_utils import verify_grasp_event


@pytest.fixture
def target_product():
    return {"id": "fanta_orange", "name": "芬达橙味汽水"}


def test_wrong_tag(target_product):
    event = verify_grasp_event(
        target_product=target_product,
        product_pose=None,
        wrong_tag_seen=True,
    )
    assert event["event"] == "wrong_item_possible"
    assert "芬达橙味汽水" in event["spoken"]


def test_user_confirmed_and_lost(target_product):
    event = verify_grasp_event(
        target_product=target_product,
        product_pose=None,
        target_recently_lost=True,
        user_confirmed=True,
    )
    assert event["event"] == "correct_item_grasped"


def test_waiting_no_data(target_product):
    event = verify_grasp_event(target_product=target_product, product_pose=None)
    assert event["event"] == "waiting"


def test_in_grasp_range(target_product):
    pose = {"distance": 0.3, "offset_x": 0.05}
    event = verify_grasp_event(target_product=target_product, product_pose=pose)
    assert event["event"] == "hand_near_target"


def test_tracking_target_far(target_product):
    pose = {"distance": 0.8, "offset_x": 0.0}
    event = verify_grasp_event(target_product=target_product, product_pose=pose)
    assert event["event"] == "tracking_target"


def test_tracking_target_offset_right(target_product):
    pose = {"distance": 0.4, "offset_x": 0.15}
    event = verify_grasp_event(target_product=target_product, product_pose=pose)
    assert event["event"] == "tracking_target"
    assert "偏右" in event["spoken"]
