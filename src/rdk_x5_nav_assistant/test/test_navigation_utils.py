import pytest

from rdk_x5_nav_assistant.navigation_utils import (
    RouteGuide,
    nearest_route_distance,
    pose_xy,
    route_for_product,
    route_waypoints,
    shelf_tag_matches,
    waypoint_by_id,
    waypoint_distance,
)


@pytest.fixture
def store_map():
    return {
        "waypoints": [
            {"id": "wp1", "name": "入口", "pose": [0.0, 0.0, 0.0], "trigger_radius_m": 0.8},
            {"id": "wp2", "name": "货架", "pose": [2.0, 0.0, 0.0], "trigger_radius_m": 0.8},
        ],
        "shelves": [
            {"id": "shelf_a", "name": "饮料货架", "waypoint_id": "wp2", "pose": [2.0, 0.0, 0.0]},
        ],
        "apriltags": [
            {"id": 11, "name": "饮料货架定位标", "shelf_id": "shelf_a"},
        ],
    }


@pytest.fixture
def routes():
    return {
        "routes": [
            {"id": "find_fanta", "product_id": "fanta_orange", "waypoints": ["wp1", "wp2"]},
        ]
    }


def test_pose_xy():
    assert pose_xy([1.0, 2.0, 0.0]) == (1.0, 2.0)
    assert pose_xy({"x": 3.0, "y": 4.0}) == (3.0, 4.0)
    assert pose_xy(None) is None


def test_waypoint_by_id(store_map):
    assert waypoint_by_id(store_map, "wp1")["name"] == "入口"
    assert waypoint_by_id(store_map, "missing") is None


def test_shelf_tag_matches(store_map):
    assert shelf_tag_matches(store_map, "shelf_a", {"id": 11}) is True
    assert shelf_tag_matches(store_map, "shelf_a", {"id": 99}) is False
    assert shelf_tag_matches(store_map, "shelf_a", None) is False


def test_route_for_product(routes):
    product = {"id": "fanta_orange", "route_id": "find_fanta"}
    route = route_for_product(product, routes)
    assert route is not None
    assert route["id"] == "find_fanta"


def test_route_waypoints(store_map, routes):
    route = route_for_product({"id": "fanta_orange"}, routes)
    waypoints = route_waypoints(route, store_map)
    assert len(waypoints) == 2
    assert waypoints[0]["id"] == "wp1"


def test_waypoint_distance():
    wp = {"pose": [3.0, 4.0, 0.0]}
    assert waypoint_distance((0.0, 0.0), wp) == 5.0


def test_nearest_route_distance():
    waypoints = [{"pose": [0.0, 0.0]}, {"pose": [3.0, 4.0]}]
    assert nearest_route_distance((0.0, 0.0), waypoints) == 0.0


def test_route_guide_continue_forward(store_map, routes):
    route = route_for_product({"id": "fanta_orange"}, routes)
    shelf = {"id": "shelf_a", "name": "饮料货架"}
    guide = RouteGuide(store_map, route, shelf, default_radius_m=0.8)
    event = guide.update((0.0, 0.0), None, {"status": "ok"})
    assert event["action"] == "continue_forward"


def test_route_guide_waypoint_reached(store_map, routes):
    route = route_for_product({"id": "fanta_orange"}, routes)
    shelf = {"id": "shelf_a", "name": "饮料货架"}
    guide = RouteGuide(store_map, route, shelf, default_radius_m=0.8)
    # Start at entrance (0,0), wp1 is also at (0,0) so we trigger it immediately
    # index starts at 1 (wp2) because len(waypoints) > 1
    event = guide.update((0.0, 0.0), None, {"status": "ok"})
    assert event["action"] == "continue_forward"  # wp2 at (2,0) is still far
    # Move to prepare zone (between prepare_radius 1.4 and trigger_radius 0.8)
    # wp2 has no turn_hint so action is "approach_waypoint"
    event2 = guide.update((1.1, 0.0), None, {"status": "ok"})
    assert event2["action"] == "approach_waypoint"
    # Reach wp2 trigger radius
    event3 = guide.update((1.25, 0.0), None, {"status": "ok"})
    assert event3["action"] == "arrived_shelf"


def test_route_guide_localization_unavailable(store_map, routes):
    route = route_for_product({"id": "fanta_orange"}, routes)
    guide = RouteGuide(store_map, route, {"id": "shelf_a"})
    event = guide.update(None, None, {"status": "unavailable"})
    # "unavailable" in localization_status triggers "localization_low"
    assert event["action"] == "localization_low"
