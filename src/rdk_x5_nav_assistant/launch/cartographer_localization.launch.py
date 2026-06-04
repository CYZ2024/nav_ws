#!/usr/bin/env python3
"""Cartographer pure localization mode — uses pre-built .pbstream map.

Launch this after mapping is complete and map.pbstream has been saved.
Cartographer will localize against the existing submaps using scan matching.
"""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description() -> LaunchDescription:
    pkg_share = get_package_share_directory("rdk_x5_nav_assistant")

    use_sim_time = LaunchConfiguration("use_sim_time", default="false")
    config_dir = os.path.join(pkg_share, "config", "cartographer")
    config_basename = LaunchConfiguration("configuration_basename", default="cartographer_2d_localization.lua")
    load_state_filename = LaunchConfiguration("load_state_filename", default="")

    resolution = LaunchConfiguration("resolution", default="0.05")
    publish_period_sec = LaunchConfiguration("publish_period_sec", default="1.0")

    return LaunchDescription([
        DeclareLaunchArgument(
            "use_sim_time",
            default_value="false",
            description="Use simulation clock if true",
        ),
        DeclareLaunchArgument(
            "configuration_basename",
            default_value="cartographer_2d.lua",
            description="Name of the Cartographer lua config file",
        ),
        DeclareLaunchArgument(
            "load_state_filename",
            default_value="",
            description="Path to saved .pbstream map for localization mode (REQUIRED)",
        ),
        DeclareLaunchArgument(
            "resolution",
            default_value="0.05",
            description="Occupancy grid resolution in meters",
        ),
        DeclareLaunchArgument(
            "publish_period_sec",
            default_value="1.0",
            description="OccupancyGrid publishing period",
        ),

        # Cartographer localization node (pure_localization = true via TRAJECTORY_BUILDER_2D.pure_localization)
        Node(
            package="cartographer_ros",
            executable="cartographer_node",
            name="cartographer_node",
            output="screen",
            parameters=[{"use_sim_time": use_sim_time}],
            arguments=[
                "-configuration_directory", config_dir,
                "-configuration_basename", config_basename,
                "-load_state_filename", load_state_filename,
            ],
        ),

        # Occupancy grid publisher (reconstructs map from submaps)
        Node(
            package="cartographer_ros",
            executable="cartographer_occupancy_grid_node",
            name="cartographer_occupancy_grid_node",
            output="screen",
            parameters=[{"use_sim_time": use_sim_time}],
            arguments=[
                "-resolution", resolution,
                "-publish_period_sec", publish_period_sec,
            ],
        ),
    ])
