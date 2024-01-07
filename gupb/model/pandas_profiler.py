from time import time
from datetime import datetime
from dataclasses import dataclass
from typing import Optional
from types import ModuleType, FunctionType
from .characters import Action
from os import makedirs, path
from gc import get_referents

import sys

BLACKLIST = type, ModuleType, FunctionType


def getsize(obj):
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


@dataclass
class DecisionRecord:
    epoch: int
    step: int
    controller: str
    decision_time: float
    memory_before: float
    memory_after: float
    action: Optional[Action]
    exception: Optional[Exception]

    def __str__(self):
        return (
            f"{self.epoch},{self.step},{self.controller},"
            + f"{self.decision_time},{self.memory_before},{self.memory_after},"
            + f"{self.action.name if self.action is not None else ''},"
            + f"{repr(self.exception) if self.exception is not None else ''}\n"
        )

    @staticmethod
    def header():
        return (
            "epoch,step,controller_name,decision_time,memory_before,memory_after,"
            + "action_name,exception_returned\n"
        )


class ProfilerContainer:
    def __init__(self, dirname="results", filename=None, batch_size=1000):
        self.dirname = dirname
        self.filename = filename
        self.registered = False
        self.epoch = 0
        self.step = 0
        self.batch_size = batch_size
        self.batch = []

    def __open_file(self):
        makedirs(self.dirname, exist_ok=True)
        if self.filename is None:
            self.filename = datetime.now().strftime("profiling__%Y_%m_%d_%H_%M_%s.csv")
        self.filename = path.join(self.dirname, self.filename)
        self.file = open(self.filename, "w")
        self.file.write(DecisionRecord.header())

    def __register(self):
        if self.registered:
            return
        self.registered = True
        self.__open_file()

    def update_epoch(self):
        self.epoch += 1
        self.step = 0

    def update_step(self):
        self.step += 1

    def close(self):
        if not self.registered:
            return
        self.__write_to_disk()
        self.file.close()

    def __write_to_disk(self):
        for row in self.batch:
            self.file.write(str(row))
        self.batch = []

    def __log(self, row):
        self.batch.append(row)
        if len(self.batch) > self.batch_size:
            self.__write_to_disk()

    def profile_me(self, _func=None):
        def decorator(func):
            def wrapper(*args, **kwargs):
                self.__register()

                obj = args[0]

                memory_start = getsize(obj)
                start = time()

                try:
                    res = func(*args, **kwargs)
                except Exception as e:
                    end = time()
                    memory_end = getsize(obj)

                    self.__log(
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

                self.__log(
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
