#!/usr/bin/env python3
"""Smoke-test mapping launch with adjustable LaserScan sector filtering and RViz."""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description() -> LaunchDescription:
    pkg_share = get_package_share_directory("rdk_x5_nav_assistant")

    use_sim_time = LaunchConfiguration("use_sim_time", default="false")
    use_lidar = LaunchConfiguration("use_lidar", default="true")
    use_rviz = LaunchConfiguration("use_rviz", default="true")
    use_tf = LaunchConfiguration("use_tf", default="true")

    input_scan_topic = LaunchConfiguration("input_scan_topic", default="/scan")
    filtered_scan_topic = LaunchConfiguration("filtered_scan_topic", default="/scan_filtered")
    blocked_scan_topic = LaunchConfiguration("blocked_scan_topic", default="/scan_blocked")
    filter_enabled = LaunchConfiguration("filter_enabled", default="true")
    filter_center_deg = LaunchConfiguration("filter_center_deg", default="180.0")
    filter_width_deg = LaunchConfiguration("filter_width_deg", default="90.0")
    invert_filter = LaunchConfiguration("invert_filter", default="false")

    laser_x = LaunchConfiguration("laser_x", default="0.25")
    laser_y = LaunchConfiguration("laser_y", default="0.0")
    laser_z = LaunchConfiguration("laser_z", default="0.25")

    cartographer_config_dir = os.path.join(pkg_share, "config", "cartographer")
    cartographer_basename = LaunchConfiguration("cartographer_basename", default="cartographer_2d.lua")
    vp100_params = os.path.join(pkg_share, "config", "vp100.yaml")
    rviz_config = os.path.join(pkg_share, "rviz", "smoke_mapping.rviz")

    vp100_node = Node(
        package="vp100_ros2",
        executable="vp100_ros2_node",
        name="vp100_ros2_node",
        output="screen",
        parameters=[vp100_params],
        condition=IfCondition(use_lidar),
    )

    scan_filter = Node(
        package="rdk_x5_nav_assistant",
        executable="scan_sector_filter",
        name="scan_sector_filter",
        output="screen",
        parameters=[
            {
                "input_scan_topic": input_scan_topic,
                "filtered_scan_topic": filtered_scan_topic,
                "blocked_scan_topic": blocked_scan_topic,
                "filter_enabled": filter_enabled,
                "filter_center_deg": filter_center_deg,
                "filter_width_deg": filter_width_deg,
                "invert_filter": invert_filter,
                "replacement": "nan",
            }
        ],
    )

    laser_tf = Node(
        package="tf2_ros",
        executable="static_transform_publisher",
        name="laser_tf_publisher",
        arguments=[laser_x, laser_y, laser_z, "0", "0", "0", "base_link", "laser_link"],
        condition=IfCondition(use_tf),
    )

    base_tf = Node(
        package="tf2_ros",
        executable="static_transform_publisher",
        name="base_tf_publisher",
        arguments=["0", "0", "0.1", "0", "0", "0", "base_footprint", "base_link"],
        condition=IfCondition(use_tf),
    )

    cartographer_node = Node(
        package="cartographer_ros",
        executable="cartographer_node",
        name="cartographer_node",
        output="screen",
        parameters=[{"use_sim_time": use_sim_time}],
        arguments=[
            "-configuration_directory", cartographer_config_dir,
            "-configuration_basename", cartographer_basename,
        ],
        remappings=[
            ("scan", filtered_scan_topic),
        ],
    )

    occupancy_grid_node = Node(
        package="cartographer_ros",
        executable="cartographer_occupancy_grid_node",
        name="cartographer_occupancy_grid_node",
        output="screen",
        parameters=[{"use_sim_time": use_sim_time}],
        arguments=["-resolution", "0.05", "-publish_period_sec", "1.0"],
    )

    rviz_node = Node(
        package="rviz2",
        executable="rviz2",
        name="rviz2",
        output="screen",
        arguments=["-d", rviz_config],
        condition=IfCondition(use_rviz),
    )

    return LaunchDescription([
        DeclareLaunchArgument("use_sim_time", default_value="false"),
        DeclareLaunchArgument("use_lidar", default_value="true"),
        DeclareLaunchArgument("use_rviz", default_value="true"),
        DeclareLaunchArgument("use_tf", default_value="true"),
        DeclareLaunchArgument("input_scan_topic", default_value="/scan"),
        DeclareLaunchArgument("filtered_scan_topic", default_value="/scan_filtered"),
        DeclareLaunchArgument("blocked_scan_topic", default_value="/scan_blocked"),
        DeclareLaunchArgument("filter_enabled", default_value="true"),
        DeclareLaunchArgument(
            "filter_center_deg",
            default_value="180.0",
            description="Center of the filtered sector in laser frame degrees. 180 is behind the cart.",
        ),
        DeclareLaunchArgument(
            "filter_width_deg",
            default_value="90.0",
            description="Angular width of the filtered sector in degrees.",
        ),
        DeclareLaunchArgument(
            "invert_filter",
            default_value="false",
            description="If true, keep only the sector and filter everything else.",
        ),
        DeclareLaunchArgument(
            "laser_x",
            default_value="0.25",
            description="Laser x offset from base_link in meters.",
        ),
        DeclareLaunchArgument("laser_y", default_value="0.0"),
        DeclareLaunchArgument("laser_z", default_value="0.25"),
        DeclareLaunchArgument("cartographer_basename", default_value="cartographer_2d.lua"),
        vp100_node,
        scan_filter,
        laser_tf,
        base_tf,
        cartographer_node,
        occupancy_grid_node,
        rviz_node,
    ])
