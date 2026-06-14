#!/usr/bin/env python3
"""Nav2 obstacle/costmap smoke test using a saved static map."""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description() -> LaunchDescription:
    pkg_share = get_package_share_directory("rdk_x5_nav_assistant")

    default_map = "/home/sunrise/Project/nav_ws/maps/workbench_20260614_173722.yaml"
    nav2_params = os.path.join(pkg_share, "config", "nav2", "nav2_params.yaml")
    vp100_params = os.path.join(pkg_share, "config", "vp100.yaml")

    use_sim_time = LaunchConfiguration("use_sim_time", default="false")
    use_lidar = LaunchConfiguration("use_lidar", default="true")
    use_tf = LaunchConfiguration("use_tf", default="true")
    use_nav2 = LaunchConfiguration("use_nav2", default="true")
    map_yaml = LaunchConfiguration("map", default=default_map)

    filter_center_deg = LaunchConfiguration("filter_center_deg", default="180.0")
    filter_width_deg = LaunchConfiguration("filter_width_deg", default="90.0")

    robot_x = LaunchConfiguration("robot_x", default="0.0")
    robot_y = LaunchConfiguration("robot_y", default="0.0")
    robot_z = LaunchConfiguration("robot_z", default="0.0")
    robot_yaw = LaunchConfiguration("robot_yaw", default="0.0")
    laser_x = LaunchConfiguration("laser_x", default="0.25")
    laser_y = LaunchConfiguration("laser_y", default="0.0")
    laser_z = LaunchConfiguration("laser_z", default="0.25")

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
                "input_scan_topic": "/scan",
                "filtered_scan_topic": "/scan_filtered",
                "blocked_scan_topic": "/scan_blocked",
                "filter_enabled": True,
                "filter_center_deg": filter_center_deg,
                "filter_width_deg": filter_width_deg,
                "replacement": "nan",
            }
        ],
    )

    initial_pose_tf = Node(
        package="rdk_x5_nav_assistant",
        executable="initial_pose_tf",
        name="initial_pose_tf",
        output="screen",
        parameters=[
            {
                "map_frame": "map",
                "robot_frame": "base_footprint",
                "initial_pose_topic": "/initialpose",
                "x": robot_x,
                "y": robot_y,
                "yaw": robot_yaw,
            }
        ],
        condition=IfCondition(use_tf),
    )

    base_tf = Node(
        package="tf2_ros",
        executable="static_transform_publisher",
        name="base_tf_publisher",
        arguments=["0", "0", "0.1", "0", "0", "0", "base_footprint", "base_link"],
        condition=IfCondition(use_tf),
    )

    laser_tf = Node(
        package="tf2_ros",
        executable="static_transform_publisher",
        name="laser_tf_publisher",
        arguments=[laser_x, laser_y, laser_z, "0", "0", "0", "base_link", "laser_link"],
        condition=IfCondition(use_tf),
    )

    nav2_bringup_dir = get_package_share_directory("nav2_bringup")
    nav2_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(nav2_bringup_dir, "launch", "bringup_launch.py")
        ),
        launch_arguments={
            "map": map_yaml,
            "use_sim_time": use_sim_time,
            "params_file": nav2_params,
            "autostart": "true",
            "use_composition": "False",
            "slam": "False",
        }.items(),
        condition=IfCondition(use_nav2),
    )

    return LaunchDescription([
        DeclareLaunchArgument("use_sim_time", default_value="false"),
        DeclareLaunchArgument("use_lidar", default_value="true"),
        DeclareLaunchArgument("use_tf", default_value="true"),
        DeclareLaunchArgument("use_nav2", default_value="true"),
        DeclareLaunchArgument("map", default_value=default_map),
        DeclareLaunchArgument("filter_center_deg", default_value="180.0"),
        DeclareLaunchArgument("filter_width_deg", default_value="90.0"),
        DeclareLaunchArgument("robot_x", default_value="0.0"),
        DeclareLaunchArgument("robot_y", default_value="0.0"),
        DeclareLaunchArgument("robot_z", default_value="0.0"),
        DeclareLaunchArgument("robot_yaw", default_value="0.0"),
        DeclareLaunchArgument("laser_x", default_value="0.25"),
        DeclareLaunchArgument("laser_y", default_value="0.0"),
        DeclareLaunchArgument("laser_z", default_value="0.25"),
        vp100_node,
        scan_filter,
        initial_pose_tf,
        base_tf,
        laser_tf,
        nav2_launch,
    ])
