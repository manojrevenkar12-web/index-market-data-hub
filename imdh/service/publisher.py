"""Where publications go after the outbox: memory for tests, Pub/Sub on GCP. Same call, either way."""
from __future__ import annotations

import json
from abc import ABC, abstractmethod


class Publisher(ABC):
    @abstractmethod
    def publish(self, event: dict) -> None: ...


class MemoryPublisher(Publisher):
    def __init__(self):
        self.sent: list[dict] = []

    def publish(self, event: dict) -> None:
        self.sent.append(event)


class PubSubPublisher(Publisher):
    """Ordered by index: the ordering key keeps v1 before its correction v2 for each index."""

    def __init__(self, topic: str):
        from google.cloud import pubsub_v1  # imported here so tests and local runs need no GCP library

        self.client = pubsub_v1.PublisherClient(
            publisher_options=pubsub_v1.types.PublisherOptions(enable_message_ordering=True))
        self.topic = topic

    def publish(self, event: dict) -> None:
        data = json.dumps(event, separators=(",", ":")).encode()
        self.client.publish(self.topic, data, ordering_key=event.get("index", ""), kind=event["kind"]).result()
