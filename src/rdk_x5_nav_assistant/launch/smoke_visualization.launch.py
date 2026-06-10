#!/usr/bin/env python3
"""Visualization bridges for the smoke mapping workflow."""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration
from launch_xml.launch_description_sources import XMLLaunchDescriptionSource
from launch_ros.substitutions import FindPackageShare
from launch.substitutions import PathJoinSubstitution


def generate_launch_description() -> LaunchDescription:
    use_foxglove = LaunchConfiguration("use_foxglove", default="true")
    use_rosbridge = LaunchConfiguration("use_rosbridge", default="true")
    foxglove_port = LaunchConfiguration("foxglove_port", default="8765")
    rosbridge_port = LaunchConfiguration("rosbridge_port", default="9090")
    address = LaunchConfiguration("address", default="0.0.0.0")

    foxglove_launch = IncludeLaunchDescription(
        XMLLaunchDescriptionSource(
            PathJoinSubstitution([
                FindPackageShare("foxglove_bridge"),
                "launch",
                "foxglove_bridge_launch.xml",
            ])
        ),
        launch_arguments={
            "port": foxglove_port,
            "address": address,
        }.items(),
        condition=IfCondition(use_foxglove),
    )

    rosbridge_launch = IncludeLaunchDescription(
        XMLLaunchDescriptionSource(
            PathJoinSubstitution([
                FindPackageShare("rosbridge_server"),
                "launch",
                "rosbridge_websocket_launch.xml",
            ])
        ),
        launch_arguments={
            "port": rosbridge_port,
            "address": address,
        }.items(),
        condition=IfCondition(use_rosbridge),
    )

    return LaunchDescription([
        DeclareLaunchArgument("use_foxglove", default_value="true"),
        DeclareLaunchArgument("use_rosbridge", default_value="true"),
        DeclareLaunchArgument("foxglove_port", default_value="8765"),
        DeclareLaunchArgument("rosbridge_port", default_value="9090"),
        DeclareLaunchArgument("address", default_value="0.0.0.0"),
        foxglove_launch,
        rosbridge_launch,
    ])
