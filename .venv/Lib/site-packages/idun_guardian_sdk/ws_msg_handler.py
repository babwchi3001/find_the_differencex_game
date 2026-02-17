from typing import Type, TypeVar, Callable, Generic, Dict, List

from .event import Event

E = TypeVar("E", bound=Event)
Handler = Callable[[E], None]


class WsMsgHandler(Generic[E]):
    def __init__(self):
        self._listeners: Dict[Type[E], List[Handler[E]]] = {}

    def subscribe(self, event_type: Type[E], listener: Handler[E]) -> None:
        self._listeners[event_type] = listener

    def publish(self, event: E) -> None:
        event_type = type(event)
        if event_type not in self._listeners:
            raise ValueError(f"No listeners subscribed for event type: {event_type}")
        self._listeners[event_type](event)
