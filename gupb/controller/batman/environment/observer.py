from typing import TypeVar, Generic


T = TypeVar("T")


class Observer(Generic[T]):
    def __init__(self) -> None:
        self.__state: T | None

    def update(self, state: T) -> None:
        self.__state = state

    def wait_for_observed(self) -> T:
        while self.__state is None:
            pass
        state = self.__state
        self.__state = None
        return state


class Observable(Generic[T]):
    def __init__(self) -> None:
        self._observers: list[Observer[T]] = []
        self.__state: T | None = None

    def attach(self, observer: Observer[T]) -> None:
        self._observers.append(observer)

    def detach(self, observer: Observer[T]) -> None:
        self._observers.remove(observer)

    @property
    def observable_state(self) -> T | None:
        return self.__state

    @observable_state.setter
    def observable_state(self, state: T) -> None:
        self.__state = state
        self._notify()

    def _notify(self) -> None:
        if self.__state is not None:
            for observer in self._observers:
                observer.update(self.__state)
