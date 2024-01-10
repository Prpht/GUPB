import dataclasses
from datetime import datetime
from gc import get_referents
from os import makedirs, path
import sys
from time import time
from types import ModuleType, FunctionType
from typing import Optional, Any

from gupb.model.characters import Action


BLACKLIST = type, ModuleType, FunctionType


def getsize(obj: Any) -> int:
    """sum size of object & members."""
    if isinstance(obj, BLACKLIST):
        raise TypeError("getsize() does not take argument of type: " + str(type(obj)))
    seen_ids = set()
    size = 0
    objects = [obj]
    while objects:
        need_referents = []
        for obj in objects:
            if not isinstance(obj, BLACKLIST) and id(obj) not in seen_ids:
                seen_ids.add(id(obj))
                size += sys.getsizeof(obj)
                need_referents.append(obj)
        objects = get_referents(*need_referents)
    return size


@dataclasses.dataclass
class AbstractProfilerRecord:
    @staticmethod
    def _parse_field(field: Any) -> str:
        return repr(field) if field is None else ''

    def __str__(self):
        order = dataclasses.fields(self)
        return ",".join([self._parse_field(dataclasses.asdict(self)[k.name]) for k in order])

    @classmethod
    def header(cls):
        # https://stackoverflow.com/questions/73203466/is-the-order-of-dataclasses-fields-guaranteed
        return ",".join(x.name for x in dataclasses.fields(cls))


@dataclasses.dataclass
class DecisionRecord(AbstractProfilerRecord):
    epoch: int
    step: int
    controller: str
    decision_time: float
    memory_before: float
    memory_after: float
    action: Optional[Action]
    exception: Optional[Exception]


class ProfilerContainer:
    def __init__(self, dirname: str = "results", filename: Optional[str] = None, batch_size: int = 1000):
        self.dirname = dirname
        self.filename = filename
        self.registered = False
        self.epoch = 0
        self.step = 0
        self.batch_size = batch_size
        self.batch = []

    def _open_file(self):
        makedirs(self.dirname, exist_ok=True)
        if self.filename is None:
            self.filename = datetime.now().strftime("profiling__%Y_%m_%d_%H_%M_%s.csv")
        self.filename = path.join(self.dirname, self.filename)
        self.file = open(self.filename, "w")
        self.file.write(DecisionRecord.header())

    def _register(self):
        if self.registered:
            return
        self.registered = True
        self._open_file()

    def update_epoch(self):
        self.epoch += 1
        self.step = 0

    def update_step(self):
        self.step += 1

    def close(self):
        if not self.registered:
            return
        self._write_to_disk()
        self.file.close()

    def _write_to_disk(self):
        for row in self.batch:
            self.file.write(str(row))
        self.batch = []

    def _log(self, row):
        self.batch.append(row)
        if len(self.batch) > self.batch_size:
            self._write_to_disk()

    def profile_me(self, _func=None):
        def decorator(func):
            def wrapper(*args, **kwargs):
                self._register()

                obj = args[0]

                memory_start = getsize(obj)
                start = time()

                try:
                    res = func(*args, **kwargs)
                except Exception as e:
                    end = time()
                    memory_end = getsize(obj)

                    self._log(
                        DecisionRecord(
                            epoch=self.epoch,
                            step=self.step,
                            controller=obj.name,
                            decision_time=end - start,
                            memory_before=memory_start,
                            memory_after=memory_end,
                            action=None,
                            exception=e,
                        )
                    )
                    raise e

                end = time()
                memory_end = getsize(obj)

                self._log(
                    DecisionRecord(
                        epoch=self.epoch,
                        step=self.step,
                        controller=obj.name,
                        decision_time=end - start,
                        memory_before=memory_start,
                        memory_after=memory_end,
                        action=res,
                        exception=None,
                    )
                )

                return res

            return wrapper

        return decorator(_func) if _func else decorator


PROFILER_SINGLETON = ProfilerContainer()


def pandas_profile(_func=None):
    return PROFILER_SINGLETON.profile_me(_func)
