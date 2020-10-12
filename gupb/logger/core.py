import json
import logging

from dataclasses_json import DataClassJsonMixin

json_logger = logging.getLogger('json')


class LoggingMixin(DataClassJsonMixin):
    def log(self, level: int) -> None:
        json_logger.log(level=level, msg=json.dumps(self.to_dict()), extra={'event_type': self.__class__.__name__})
