from __future__ import annotations

from abc import ABC, abstractmethod

from ..schemas import AIEnhanceRequest


class BaseAIEnhanceProvider(ABC):
    provider_name = "base"

    @abstractmethod
    def enhance(self, request: AIEnhanceRequest):
        raise NotImplementedError
