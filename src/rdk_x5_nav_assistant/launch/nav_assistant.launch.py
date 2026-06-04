#!/usr/bin/env python3
"""Navigation board launch: localization, navigation, task state, voice, grasp."""

from __future__ import annotations

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description() -> LaunchDescription:
    package_share = get_package_share_directory("rdk_x5_nav_assistant")

    product_catalog_path = os.path.join(package_share, "config", "product_catalog.yaml")
    store_map_path = os.path.join(package_share, "config", "store_map.yaml")
    demo_routes_path = os.path.join(package_share, "config", "demo_routes.yaml")
    safety_path = os.path.join(package_share, "config", "safety.yaml")

    declarations = [
        DeclareLaunchArgument("product_catalog_path", default_value=product_catalog_path),
        DeclareLaunchArgument("store_map_path", default_value=store_map_path),
        DeclareLaunchArgument("demo_routes_path", default_value=demo_routes_path),
        DeclareLaunchArgument("safety_path", default_value=safety_path),
        # --- Localization (on this board) ---
        DeclareLaunchArgument("rtabmap_pose_topic", default_value="/rtabmap/localization_pose"),
        DeclareLaunchArgument("rtabmap_odom_topic", default_value="/odom"),
        DeclareLaunchArgument("localization_pose_topic", default_value="/assistant/localization_pose"),
        DeclareLaunchArgument("localization_status_topic", default_value="/assistant/localization_status"),
        # --- Topics from vision board ---
        DeclareLaunchArgument("product_pose_topic", default_value="/perception/product_pose"),
        DeclareLaunchArgument("tag_event_topic", default_value="/assistant/tag_event"),
        DeclareLaunchArgument("gesture_event_topic", default_value="/assistant/gesture_event"),
        DeclareLaunchArgument("obstacle_topic", default_value="/perception/obstacle"),
        # --- Internal topics ---
        DeclareLaunchArgument("navigation_event_topic", default_value="/assistant/navigation_event"),
        DeclareLaunchArgument("grasp_event_topic", default_value="/assistant/grasp_event"),
        DeclareLaunchArgument("target_product_topic", default_value="/assistant/target_product"),
        DeclareLaunchArgument("task_state_topic", default_value="/assistant/task_state"),
        DeclareLaunchArgument("user_intent_topic", default_value="/assistant/user_intent"),
        DeclareLaunchArgument("tts_topic", default_value="/tts_text"),
        # --- Audio ---
        DeclareLaunchArgument("audio_topic", default_value="/audio_smart"),
        DeclareLaunchArgument("audio_asr_topic", default_value="/audio_asr"),
        DeclareLaunchArgument("asr_text_topic", default_value="/assistant/asr_text"),
        # --- Switches ---
        DeclareLaunchArgument("use_localization_bridge", default_value="true"),
        DeclareLaunchArgument("use_navigation_guide", default_value="true"),
        DeclareLaunchArgument("use_audio_intent_bridge", default_value="true"),
        DeclareLaunchArgument("use_tts", default_value="true"),
        DeclareLaunchArgument("use_grasp_verification", default_value="true"),
        DeclareLaunchArgument("tts_backend", default_value="auto"),
        DeclareLaunchArgument("tts_voice", default_value="zh"),
        DeclareLaunchArgument("tts_speed", default_value="150"),
    ]

    localization_bridge_node = Node(
        package="rdk_x5_nav_assistant",
        executable="localization_bridge",
        output="screen",
        parameters=[
            {
                "rtabmap_pose_topic": LaunchConfiguration("rtabmap_pose_topic"),
                "rtabmap_odom_topic": LaunchConfiguration("rtabmap_odom_topic"),
                "localization_pose_topic": LaunchConfiguration("localization_pose_topic"),
                "localization_status_topic": LaunchConfiguration("localization_status_topic"),
            }
        ],
    )

    navigation_guide_node = Node(
        package="rdk_x5_nav_assistant",
        executable="navigation_guide_node",
        output="screen",
        parameters=[
            {
                "product_catalog_path": LaunchConfiguration("product_catalog_path"),
                "store_map_path": LaunchConfiguration("store_map_path"),
                "demo_routes_path": LaunchConfiguration("demo_routes_path"),
                "target_product_topic": LaunchConfiguration("target_product_topic"),
                "localization_pose_topic": LaunchConfiguration("localization_pose_topic"),
                "localization_status_topic": LaunchConfiguration("localization_status_topic"),
                "tag_event_topic": LaunchConfiguration("tag_event_topic"),
                "navigation_event_topic": LaunchConfiguration("navigation_event_topic"),
                "tts_topic": LaunchConfiguration("tts_topic"),
            }
        ],
    )

    assistant_task_node = Node(
        package="rdk_x5_nav_assistant",
        executable="assistant_task_node",
        output="screen",
        parameters=[
            {
                "product_catalog_path": LaunchConfiguration("product_catalog_path"),
                "store_map_path": LaunchConfiguration("store_map_path"),
                "demo_routes_path": LaunchConfiguration("demo_routes_path"),
                "user_intent_topic": LaunchConfiguration("user_intent_topic"),
                "obstacle_topic": LaunchConfiguration("obstacle_topic"),
                "product_pose_topic": LaunchConfiguration("product_pose_topic"),
                "tag_event_topic": LaunchConfiguration("tag_event_topic"),
                "gesture_event_topic": LaunchConfiguration("gesture_event_topic"),
                "navigation_event_topic": LaunchConfiguration("navigation_event_topic"),
                "grasp_event_topic": LaunchConfiguration("grasp_event_topic"),
                "localization_status_topic": LaunchConfiguration("localization_status_topic"),
                "assistant_pose_topic": LaunchConfiguration("localization_pose_topic"),
                "target_product_topic": LaunchConfiguration("target_product_topic"),
                "task_state_topic": LaunchConfiguration("task_state_topic"),
                "tts_topic": LaunchConfiguration("tts_topic"),
            }
        ],
    )

    audio_intent_bridge_node = Node(
        package="rdk_x5_nav_assistant",
        executable="audio_intent_bridge",
        output="screen",
        parameters=[
            {
                "audio_topic": LaunchConfiguration("audio_topic"),
                "asr_topic": LaunchConfiguration("audio_asr_topic"),
                "user_intent_topic": LaunchConfiguration("user_intent_topic"),
                "publish_raw_text_topic": LaunchConfiguration("asr_text_topic"),
            }
        ],
    )

    tts_player_node = Node(
        package="rdk_x5_nav_assistant",
        executable="tts_player_node",
        output="screen",
        parameters=[
            {
                "tts_topic": LaunchConfiguration("tts_topic"),
                "backend": LaunchConfiguration("tts_backend"),
                "voice": LaunchConfiguration("tts_voice"),
                "speed": LaunchConfiguration("tts_speed"),
            }
        ],
    )

    grasp_verification_node = Node(
        package="rdk_x5_nav_assistant",
        executable="grasp_verification_node",
        output="screen",
        parameters=[
            {
                "product_catalog_path": LaunchConfiguration("product_catalog_path"),
                "target_product_topic": LaunchConfiguration("target_product_topic"),
                "product_pose_topic": LaunchConfiguration("product_pose_topic"),
                "tag_event_topic": LaunchConfiguration("tag_event_topic"),
                "gesture_event_topic": LaunchConfiguration("gesture_event_topic"),
                "grasp_event_topic": LaunchConfiguration("grasp_event_topic"),
            }
        ],
    )

    return LaunchDescription(
        declarations
        + [
            localization_bridge_node,
            navigation_guide_node,
            assistant_task_node,
            audio_intent_bridge_node,
            tts_player_node,
            grasp_verification_node,
        ]
    )
