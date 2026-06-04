#!/usr/bin/env python3
"""Unified bringup for robot-nav: YDLIDAR X3 (vp100_ros2) + Cartographer 2D + TF + Nav2.

No chassis/odometry. Shopping cart is human-pushed.
Publishes: /scan, /map, TF tree, /shopping/nav_status, /shopping/robot_pose
Subscribes: /shopping/nav_goal, /shopping/nav_cancel
"""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PythonExpression
from launch_ros.actions import Node


def generate_launch_description() -> LaunchDescription:
    pkg_share = get_package_share_directory("rdk_x5_nav_assistant")

    # --- Arguments ---
    use_sim_time = LaunchConfiguration("use_sim_time", default="false")
    use_lidar = LaunchConfiguration("use_lidar", default="true")
    use_cartographer = LaunchConfiguration("use_cartographer", default="true")
    use_nav2 = LaunchConfiguration("use_nav2", default="true")
    use_nav_bridge = LaunchConfiguration("use_nav_bridge", default="true")
    use_tf = LaunchConfiguration("use_tf", default="true")

    # Cartographer
    cartographer_config_dir = os.path.join(pkg_share, "config", "cartographer")
    cartographer_basename = LaunchConfiguration("cartographer_basename", default="cartographer_2d.lua")
    load_state_filename = LaunchConfiguration("load_state_filename", default="")

    # Nav2
    nav2_params = os.path.join(pkg_share, "config", "nav2", "nav2_params.yaml")

    # YDLIDAR X3 LiDAR params (driven by vp100_ros2 from dev_ws)
    vp100_params = os.path.join(pkg_share, "config", "vp100.yaml")

    # --- Nodes & Includes ---

    # 1. YDLIDAR X3 LiDAR driver via vp100_ros2 (from dev_ws)
    vp100_node = Node(
        package="vp100_ros2",
        executable="vp100_ros2_node",
        name="vp100_ros2_node",
        output="screen",
        parameters=[vp100_params],
        condition=IfCondition(use_lidar),
    )

    # 2. Static TF: base_link -> laser_link
    # YDLIDAR X3 mounted on top of the shopping cart
    laser_tf = Node(
        package="tf2_ros",
        executable="static_transform_publisher",
        name="laser_tf_publisher",
        arguments=["0", "0", "0.25", "0", "0", "0", "base_link", "laser_link"],
        condition=IfCondition(use_tf),
    )

    # 3. Static TF: base_footprint -> base_link
    # base_footprint is the projection on ground, base_link is robot center
    base_tf = Node(
        package="tf2_ros",
        executable="static_transform_publisher",
        name="base_tf_publisher",
        arguments=["0", "0", "0.1", "0", "0", "0", "base_footprint", "base_link"],
        condition=IfCondition(use_tf),
    )

    # 4. Cartographer SLAM node
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
        condition=IfCondition(use_cartographer),
    )

    # 5. Cartographer occupancy grid publisher
    occupancy_grid_node = Node(
        package="cartographer_ros",
        executable="cartographer_occupancy_grid_node",
        name="cartographer_occupancy_grid_node",
        output="screen",
        parameters=[{"use_sim_time": use_sim_time}],
        arguments=["-resolution", "0.05", "-publish_period_sec", "1.0"],
        condition=IfCondition(use_cartographer),
    )

    # 6. Nav2 navigation (without AMCL — Cartographer provides localization)
    # Use navigation_launch.py instead of bringup_launch.py to avoid AMCL
    nav2_bringup_dir = get_package_share_directory("nav2_bringup")
    nav2_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(nav2_bringup_dir, "launch", "navigation_launch.py")
        ),
        launch_arguments={
            "use_sim_time": use_sim_time,
            "params_file": nav2_params,
            "autostart": "true",
        }.items(),
        condition=IfCondition(use_nav2),
    )

    # 7. Navigation goal bridge (interface to robot-ai)
    nav_bridge_node = Node(
        package="rdk_x5_nav_assistant",
        executable="nav_goal_bridge",
        name="nav_goal_bridge",
        output="screen",
        parameters=[
            {
                "nav_goal_topic": "/shopping/nav_goal",
                "nav_cancel_topic": "/shopping/nav_cancel",
                "nav_status_topic": "/shopping/nav_status",
                "robot_pose_topic": "/shopping/robot_pose",
                "map_frame": "map",
                "robot_frame": "base_footprint",
            }
        ],
        condition=IfCondition(use_nav_bridge),
    )

    return LaunchDescription([
        DeclareLaunchArgument("use_sim_time", default_value="false"),
        DeclareLaunchArgument("use_lidar", default_value="true"),
        DeclareLaunchArgument("use_cartographer", default_value="true"),
        DeclareLaunchArgument("use_nav2", default_value="true"),
        DeclareLaunchArgument("use_nav_bridge", default_value="true"),
        DeclareLaunchArgument("use_tf", default_value="true"),
        DeclareLaunchArgument("cartographer_basename", default_value="cartographer_2d.lua"),
        DeclareLaunchArgument("load_state_filename", default_value="",
                              description="Path to .pbstream for pure localization mode"),
        vp100_node,
        laser_tf,
        base_tf,
        cartographer_node,
        occupancy_grid_node,
        nav2_launch,
        nav_bridge_node,
    ])
