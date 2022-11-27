from abc import ABC, abstractmethod

from beiboot.types import Beiboot


class AbstractConnectionProvider(ABC):
    def __init__(self, beiboot: Beiboot) -> None:
        self.beiboot = beiboot

    @abstractmethod
    def establish(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def terminate(self) -> None:
        raise NotImplementedError
