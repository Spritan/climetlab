# (C) Copyright 2020 ECMWF.
#
# This software is licensed under the terms of the Apache Licence Version 2.0
# which can be obtained at http://www.apache.org/licenses/LICENSE-2.0.
# In applying this licence, ECMWF does not waive the privileges and immunities
# granted to it by virtue of its status as an intergovernmental organisation
# nor does it submit to any jurisdiction.
#

import logging

from ..datasets import load_dataset
from ..sources import load_source
from . import Source

LOG = logging.getLogger(__name__)


class LoadAction:
    def execute(self, v, data, last, inherit):
        if not isinstance(v, list):
            v = [v]
        for one in v:
            name = one.pop("name")
            if inherit:
                last.update(one)
                one = last
            print(f"Using data from: {name}, {one}")
            source = self.load(name, **one)
            assert len(source), f"No data for {(name, one)}"
            data.append(source)


class LoadSource(LoadAction):
    def load(self, *args, **kwargs):
        return load_source(*args, **kwargs)


class LoadDataset(LoadAction):
    def load(self, *args, **kwargs):
        return load_dataset(*args, **kwargs)


class Inherit:
    def execute(self, *args, **kwargs):
        pass


class LoadConstants(LoadSource):
    def execute(self, v, data, last, inherit):
        super().execute(
            {
                "name": "constants",
                "source_or_dataset": data[0],
                "param": v,
            },
            data,
            last,
            inherit,
        )


ACTIONS = {
    "inherit": Inherit,
    "source": LoadSource,
    "dataset": LoadDataset,
    "constants": LoadConstants,
}


class Loader(Source):
    def __init__(self, config):
        from climetlab.utils import load_json_or_yaml

        if isinstance(config, str):
            config = load_json_or_yaml(config)
        self.config = config

    def mutate(self):
        data = []
        inherit = False
        last = {}
        for k, v in self.config.items():
            if k == "inherit":
                inherit = v

            ACTIONS[k]().execute(v, data, last, inherit)

        result = data[0]
        for d in data[1:]:
            result = result + d

        return result


source = Loader
