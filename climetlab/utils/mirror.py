# (C) Copyright 2020 ECMWF.
#
# This software is licensed under the terms of the Apache Licence Version 2.0
# which can be obtained at http://www.apache.org/licenses/LICENSE-2.0.
# In applying this licence, ECMWF does not waive the privileges and immunities
# granted to it by virtue of its status as an intergovernmental organisation
# nor does it submit to any jurisdiction.
#
import logging
import os
import shutil
from urllib.parse import urlparse

import climetlab as cml

LOG = logging.getLogger(__name__)

global _MIRRORS


class SourceMutator:
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs

    def mutate_source(self):
        return cml.load_source(*self.args, **self.kwargs)


class Mirrors(list):
    def warn_unsupported(self):
        if len(self) <= 1:
            return
        for m in self:
            if m._prefetch:
                LOG.error("Using prefetch with multiple mirrors is not supported.")
                raise Exception(
                    "Using prefetch with multiple mirrors is not supported."
                )
        return

    def mutator(self, source, **kwargs):
        for m in self:
            if not m.contains(source, **kwargs):
                continue
            mutator = source.get_mirror_mutator(m, **kwargs)
            if mutator:
                return mutator
        return None


class BaseMirror:

    _prefetch = False

    def __enter__(self):
        self.activate(prefetch=self._prefetch)
        return self

    def __exit__(self, *args, **kwargs):
        self.deactivate()

    def prefetch(self):
        self._prefetch = True
        return self

    def activate(self, prefetch=False):
        self._prefetch = prefetch
        global _MIRRORS
        _MIRRORS.append(self)

    def deactivate(self):
        self._prefetch = False
        global _MIRRORS
        _MIRRORS.remove(self)

    def contains(self, source, **kwargs):
        if hasattr(source, "is_contained_by"):
            return source.is_contained_by(self, **kwargs)
        return False

    def build_copy_of_url(self, source, **kwargs):
        if not self._prefetch:
            LOG.debug(
                f"Mirror {self} does not build copy of {source} because prefetch=False."
            )
            return

        if self.contains(source, **kwargs):
            LOG.debug(f"Mirror {self} already contains a copy of {source}")
            return

        self._build_copy_of_url(source, **kwargs)


class Mirror(BaseMirror):
    # TODO: build mirror from json config
    pass


class DirectoryMirror(BaseMirror):
    def __init__(self, path, origin_prefix="", **kwargs):
        self.path = path
        self.origin_prefix = origin_prefix
        self.kwargs = kwargs

    def __repr__(self):
        return f"DirectoryMirror({self.path}, {self.kwargs})"

    def mutator_for_url(self, source, **kwargs):
        new_url = "file://" + self.realpath(source, **kwargs)
        if new_url != source.url:
            LOG.debug(f"Found mirrored file for {source} in {new_url}")
            return SourceMutator("url", new_url)
        return None

    def contains_url(self, source, **kwargs):
        url = source.url
        if not url.startswith(self.origin_prefix):
            return False
        path = self.realpath(source, **kwargs)
        return os.path.exists(path)

    def _build_copy_of_url(self, source, **kwargs):
        source_path = source.path
        path = self.realpath(source, **kwargs)
        LOG.info(f"Building mirror for {source}: cp {source_path} {path}")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        shutil.copy2(source_path, path)

    def realpath(self, source, **kwargs):
        keys = self._url_to_keys(source, **kwargs)
        assert isinstance(keys, (list, tuple)), type(keys)
        path = os.path.join(
            self.path,
            *keys,
        )
        return os.path.realpath(path)

    def _url_to_keys(self, source, **kwargs):
        url = source.url
        if self.origin_prefix:
            key = url[(len(self.origin_prefix) + 1) :]
            return ["url", key]

        url = urlparse(url)
        keys = [url.scheme, f"{url.netloc}/{url.path}"]
        return ["url"] + keys


def get_mirrors():
    global _MIRRORS
    _MIRRORS.warn_unsupported()
    return _MIRRORS


def _reset_mirrors(use_env_var):
    global _MIRRORS
    _MIRRORS = Mirrors()
    if not use_env_var:
        return

    env_var = os.environ.get("CLIMETLAB_MIRROR")
    if " ":
        # export CLIMETLAB_MIRROR='https://storage.ecmwf.europeanweather.cloud file:///data/mirror/https/storage.ecmwf.europeanweather.cloud' # noqa
        LOG.warning(
            "Deprecation warning:  using CLIMETLAB_MIRROR environment variable string to define a mirror is deprecated."
        )
        origin_prefix, path = env_var.split(" ")
        mirror = DirectoryMirror(path=path, origin_prefix=origin_prefix)
    else:
        mirror = DirectoryMirror(path=env_var)
    _MIRRORS.append(mirror)


_reset_mirrors(use_env_var=True)
