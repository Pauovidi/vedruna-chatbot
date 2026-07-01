from __future__ import annotations

from abc import ABC, abstractmethod

from core.llm.schemas import IncomingMessage


class ChannelAdapter(ABC):
    channel: str

    @abstractmethod
    def normalize(self, payload: dict[str, object]) -> IncomingMessage:
        raise NotImplementedError
