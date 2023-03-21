# (C) Copyright 2022 ECMWF.
#
# This software is licensed under the terms of the Apache Licence Version 2.0
# which can be obtained at http://www.apache.org/licenses/LICENSE-2.0.
# In applying this licence, ECMWF does not waive the privileges and immunities
# granted to it by virtue of its status as an intergovernmental organisation
# nor does it submit to any jurisdiction.
#

import logging
import math
import os
from abc import abstractmethod
from collections import defaultdict

from climetlab.core.index import Index, MaskIndex, MultiIndex
from climetlab.decorators import alias_argument
from climetlab.indexing.database import (
    FILEPARTS_KEY_NAMES,
    MORE_KEY_NAMES,
    MORE_KEY_NAMES_WITH_UNDERSCORE,
    STATISTICS_KEY_NAMES,
)
from climetlab.readers.grib.codes import GribField
from climetlab.readers.grib.fieldset import FieldSetMixin
from climetlab.utils import progress_bar
from climetlab.utils.availability import Availability

LOG = logging.getLogger(__name__)


@alias_argument("levelist", ["level"])
@alias_argument("param", ["variable", "parameter"])
@alias_argument("number", ["realization", "realisation"])
@alias_argument("class", "klass")
def normalize_grib_kwargs(**kwargs):
    return kwargs


class FieldSet(FieldSetMixin, Index):
    _availability = None

    def __init__(self, *args, **kwargs):
        if self.availability_path is not None and os.path.exists(
            self.availability_path
        ):
            self._availability = Availability(self.availability_path)

        Index.__init__(self, *args, **kwargs)

    @classmethod
    def new_mask_index(self, *args, **kwargs):
        return MaskFieldSet(*args, **kwargs)

    @property
    def availability_path(self):
        return None

    def _all_coords(self, args):
        assert all(isinstance(k, str) for k in args), (k, type(k))

        dic = defaultdict(dict)
        for f in self:
            for k in args:
                v = f.metadata(k)
                dic[k][v] = True
        dic = {k: tuple(values.keys()) for k, values in dic.items()}
        return dic

    def _custom_availability(self, ignore_keys=None, filter_keys=lambda k: True):
        def dicts():
            for i in progress_bar(
                iterable=range(len(self)), desc="Building availability"
            ):
                dic = self.get_metadata(i)

                for k in list(dic.keys()):
                    if not filter_keys(k):
                        dic.pop(k)
                        continue
                    if ignore_keys and k in ignore_keys:
                        dic.pop(k)
                        continue
                    if dic[k] is None:
                        dic.pop(k)
                        continue

                yield dic

        from climetlab.utils.availability import Availability

        return Availability(dicts())

    @property
    def availability(self):
        if self._availability is not None:
            return self._availability
        LOG.debug("Building availability")

        self._availability = self._custom_availability(
            ignore_keys=FILEPARTS_KEY_NAMES
            + STATISTICS_KEY_NAMES
            + MORE_KEY_NAMES_WITH_UNDERSCORE
            + MORE_KEY_NAMES
        )
        return self.availability

    def is_full_hypercube(self):
        non_empty_coords = {
            k: v
            for k, v in self.availability._tree.unique_values().items()
            if len(v) > 1
        }
        expected_size = math.prod([len(v) for k, v in non_empty_coords.items()])
        return len(self) == expected_size

    def normalize_selection(self, *args, **kwargs):
        kwargs = super().normalize_selection(*args, **kwargs)
        kwargs = normalize_grib_kwargs(**kwargs)
        return kwargs

    def normalize_order_by(self, *args, **kwargs):
        kwargs = super().normalize_order_by(*args, **kwargs)
        kwargs = normalize_grib_kwargs(**kwargs)
        return kwargs


class MaskFieldSet(FieldSet, MaskIndex):
    def __init__(self, *args, **kwargs):
        MaskIndex.__init__(self, *args, **kwargs)


class MultiFieldSet(FieldSet, MultiIndex):
    def __init__(self, *args, **kwargs):
        MultiIndex.__init__(self, *args, **kwargs)


class FieldSetInFiles(FieldSet):
    # Remote Fieldsets (with urls) are also here,
    # as the actual fieldset is accessed on a file in cache.
    # This class changes the interface (_getitem__ and __len__)
    # into the interface (part and number_of_parts).
    def _getitem(self, n):
        part = self.part(n)
        return GribField(part.path, part.offset, part.length)

    def __len__(self):
        return self.number_of_parts()

    @abstractmethod
    def part(self, n):
        self._not_implemented()

    @abstractmethod
    def number_of_parts(self):
        self._not_implemented()
