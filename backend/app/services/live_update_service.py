"""Small in-memory event hub for live Server-Sent Events updates."""

import json
from collections import defaultdict
from queue import Queue


subscribers: dict[int, set[Queue]] = defaultdict(set)


def subscribe(user_id: int) -> Queue:
    queue: Queue = Queue()
    subscribers[user_id].add(queue)
    return queue


def unsubscribe(user_id: int, queue: Queue) -> None:
    subscribers[user_id].discard(queue)
    if not subscribers[user_id]:
        subscribers.pop(user_id, None)


def publish(user_id: int, event_type: str, payload: dict) -> None:
    message = json.dumps({"type": event_type, "data": payload}, default=str)
    for queue in list(subscribers.get(user_id, ())):
        queue.put(message)
