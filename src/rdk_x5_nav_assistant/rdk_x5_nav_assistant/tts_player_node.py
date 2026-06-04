#!/usr/bin/env python3
"""Play /tts_text through the local speaker using an available TTS backend."""

from __future__ import annotations

import shutil
import subprocess
import threading
from queue import Queue
from typing import List, Optional

import rclpy
from rclpy.node import Node
from std_msgs.msg import String


class TtsCommandBuilder:
    def __init__(self, backend: str = "auto", voice: str = "zh", speed: int = 150) -> None:
        self.backend = backend
        self.voice = voice
        self.speed = speed

    def resolve(self) -> Optional[str]:
        if self.backend != "auto":
            return self.backend if shutil.which(self.backend) else None
        for candidate in ("espeak-ng", "spd-say", "flite", "festival"):
            if shutil.which(candidate):
                return candidate
        return None

    def build(self, text: str) -> Optional[List[str]]:
        backend = self.resolve()
        if backend is None:
            return None
        if backend == "espeak-ng":
            return [backend, "-v", self.voice, "-s", str(self.speed), text]
        if backend == "spd-say":
            return [backend, text]
        if backend == "flite":
            return [backend, "-t", text]
        if backend == "festival":
            return [backend, "--tts"]
        return [backend, text]


class TtsPlayerNode(Node):
    def __init__(self) -> None:
        super().__init__("tts_player_node")
        self.declare_parameter("tts_topic", "/tts_text")
        self.declare_parameter("backend", "auto")
        self.declare_parameter("voice", "zh")
        self.declare_parameter("speed", 150)
        self.declare_parameter("enabled", True)

        self.builder = TtsCommandBuilder(
            str(self.get_parameter("backend").value),
            str(self.get_parameter("voice").value),
            int(self.get_parameter("speed").value),
        )
        self.queue: Queue[str] = Queue(maxsize=8)
        self.worker = threading.Thread(target=self._worker, daemon=True)
        self.worker.start()

        backend = self.builder.resolve()
        if backend is None:
            self.get_logger().warn(
                "No local TTS command found. Install one, for example: sudo apt install espeak-ng"
            )
        else:
            self.get_logger().info(f"TTS player backend: {backend}")

        self.create_subscription(String, self.get_parameter("tts_topic").value, self._on_tts, 10)

    def _on_tts(self, msg: String) -> None:
        if not bool(self.get_parameter("enabled").value):
            return
        text = msg.data.strip()
        if not text:
            return
        if self.queue.full():
            try:
                self.queue.get_nowait()
            except Exception:
                pass
        self.queue.put(text)

    def _worker(self) -> None:
        while True:
            text = self.queue.get()
            command = self.builder.build(text)
            if command is None:
                self.get_logger().warn(f"TTS skipped, no backend available: {text}")
                continue
            try:
                if command[0] == "festival":
                    subprocess.run(command, input=text.encode("utf-8"), check=False)
                else:
                    subprocess.run(command, check=False)
            except Exception as exc:
                self.get_logger().warn(f"TTS playback failed: {exc}")


def main(args: Optional[List[str]] = None) -> None:
    rclpy.init(args=args)
    node = TtsPlayerNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
