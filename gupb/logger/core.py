import atexit
import json
import os
import pathlib
from datetime import datetime

from dataclasses_json import DataClassJsonMixin

from gupb.logger.primitives import LogSeverity

_LOG_FILE_DESCRIPTOR = None


def set_up_logger(log_directory: str) -> None:
    time = datetime.now().strftime('%Y_%m_%d_%H_%M_%S')
    logging_path = pathlib.Path(log_directory) / f'gupb__{time}.json'
    logging_path.parent.mkdir(parents=True, exist_ok=True)
    logging_path.parent.chmod(0o777)
    global _LOG_FILE_DESCRIPTOR
    _LOG_FILE_DESCRIPTOR = open(logging_path.as_posix(), "w")


def log(severity: LogSeverity, value: DataClassJsonMixin) -> None:
    global _LOG_FILE_DESCRIPTOR
    if _LOG_FILE_DESCRIPTOR is None:
        raise RuntimeError("Logger was not initialized")
    serialized_log = _serialize_log(severity=severity, value=value)
    _LOG_FILE_DESCRIPTOR.write(f"{serialized_log}{os.linesep}")


def _serialize_log(severity: LogSeverity, value: DataClassJsonMixin) -> str:
    log_content = {
        "time_stamp": datetime.now().isoformat(),
        "severity": severity.value,
        "type": value.__class__.__name__,
        "value": value.to_dict()
    }
    return json.dumps(log_content)


@atexit.register
def _dispose_logger() -> None:
    global _LOG_FILE_DESCRIPTOR
    if _LOG_FILE_DESCRIPTOR is not None:
        _LOG_FILE_DESCRIPTOR.close()

