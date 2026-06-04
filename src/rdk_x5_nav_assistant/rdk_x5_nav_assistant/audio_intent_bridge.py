#!/usr/bin/env python3
"""Bridge RDK smart-audio command words into assistant user intents."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

import rclpy
from rclpy.node import Node
from std_msgs.msg import String

try:
    from audio_msg.msg import SmartAudioData
except Exception:  # pragma: no cover - depends on TROS audio packages.
    SmartAudioData = None

from .catalog import detect_command


def intent_payload_from_text(text: str, source: str = "audio") -> str:
    text = text.strip()
    payload: Dict[str, Any] = {"text": text, "source": source}
    command = detect_command(text)
    if command:
        payload["command"] = command
    return json.dumps(payload, ensure_ascii=False)


class AudioIntentBridge(Node):
    def __init__(self) -> None:
        super().__init__("audio_intent_bridge")
        self.declare_parameter("audio_topic", "/audio_smart")
        self.declare_parameter("asr_topic", "/audio_asr")
        self.declare_parameter("user_intent_topic", "/assistant/user_intent")
        self.declare_parameter("publish_raw_text_topic", "/assistant/asr_text")
        self.declare_parameter("repeat_interval_s", 1.0)

        self.intent_pub = self.create_publisher(String, self.get_parameter("user_intent_topic").value, 10)
        self.raw_text_pub = self.create_publisher(String, self.get_parameter("publish_raw_text_topic").value, 10)
        self.last_text = ""
        self.last_text_time = 0.0

        if SmartAudioData is None:
            self.get_logger().warn("audio_msg is unavailable; /audio_smart command-word subscription is disabled")
        else:
            self.create_subscription(
                SmartAudioData,
                self.get_parameter("audio_topic").value,
                self._on_audio,
                10,
            )
        self.create_subscription(String, self.get_parameter("asr_topic").value, self._on_asr_text, 10)
        self.get_logger().info("Audio intent bridge is ready")

    def _on_audio(self, msg: Any) -> None:
        frame_type = getattr(getattr(msg, "frame_type", None), "value", None)
        cmd_word = str(getattr(msg, "cmd_word", "") or "").strip()
        if not cmd_word:
            return
        if frame_type not in (None, 3, 6):
            return
        if not self._text_allowed(cmd_word):
            return

        raw = String()
        raw.data = cmd_word
        self.raw_text_pub.publish(raw)

        out = String()
        out.data = intent_payload_from_text(cmd_word)
        self.intent_pub.publish(out)
        self.get_logger().info(f"ASR command -> user intent: {cmd_word}")

    def _on_asr_text(self, msg: String) -> None:
        text = msg.data.strip()
        if not text or not self._text_allowed(text):
            return
        raw = String()
        raw.data = text
        self.raw_text_pub.publish(raw)

        out = String()
        out.data = intent_payload_from_text(text, source="asr")
        self.intent_pub.publish(out)
        self.get_logger().info(f"ASR text -> user intent: {text}")

    def _text_allowed(self, text: str) -> bool:
        now = self.get_clock().now().nanoseconds / 1e9
        repeat_interval = float(self.get_parameter("repeat_interval_s").value)
        if text == self.last_text and now - self.last_text_time < repeat_interval:
            return False
        self.last_text = text
        self.last_text_time = now
        return True


def main(args: Optional[List[str]] = None) -> None:
    rclpy.init(args=args)
    node = AudioIntentBridge()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
