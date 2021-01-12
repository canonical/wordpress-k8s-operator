# This file is part of the PostgreSQL k8s Charm for Juju.
# Copyright 2020 Canonical Ltd.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3, as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranties of
# MERCHANTABILITY, SATISFACTORY QUALITY, or FITNESS FOR A PARTICULAR
# PURPOSE.  See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

# TODO: Most of all of this module should move into the Operator Framework core

import collections.abc
import subprocess
from typing import Any, Iterable, Dict, MutableMapping, Protocol

import ops
import yaml


class _Codec(Protocol):
    def encode(self, value: Any) -> str:
        raise NotImplementedError("encode")

    def decode(self, key: str, value: str) -> Any:
        raise NotImplementedError("decode")


class _ObjectABCMeta(type(ops.framework.Object), type(collections.abc.MutableMapping)):
    """This metaclass can go once the Operator Framework drops Python 3.5 support.

    Per ops.framework._Metaclass docstring.
    """

    pass


class _PeerData(ops.framework.Object, collections.abc.MutableMapping, metaclass=_ObjectABCMeta):
    """A bag of data shared between peer units.

    Only the leader can set data. All peer units can read.
    """

    def __init__(self, parent: ops.framework.Object, key: str, _store: MutableMapping, _codec: _Codec):
        super().__init__(parent, key)
        self._store = _store
        self._codec = _codec
        self._prefix = self.handle.path

    def _prefixed_key(self, key: str) -> str:
        return self._prefix + "/" + key

    def __getitem__(self, key: str) -> Any:
        if not isinstance(key, str):
            raise TypeError(f"key must be a string, got {repr(key)} {type(key)}")
        raw = self._store[self._prefixed_key(key)]
        return self._codec.decode(key, raw)

    def __setitem__(self, key: str, value: Any) -> None:
        if not isinstance(key, str):
            raise TypeError(f"key must be a string, got {repr(key)} {type(key)}")
        if not self.model.unit.is_leader():
            raise RuntimeError("non-leader attempting to set peer data")
        self._store[self._prefixed_key(key)] = self._codec.encode(value)

    def __delitem__(self, key: str) -> None:
        if not isinstance(key, str):
            raise TypeError(f"key must be a string, got {repr(key)} {type(key)}")
        if not self.model.unit.is_leader():
            raise RuntimeError("non-leader attempting to set peer data")
        del self._store[self._prefixed_key(key)]

    def __iter__(self) -> Iterable[str]:
        return iter(self._store)

    def __len__(self) -> int:
        return len(self._store)


class LegacyLeaderData(_PeerData):
    """Raw Juju Leadership settings, a bag of data shared between peers.

    Only the leader can set data. All peer units can read.

    Behavior matches the Juju leader-get and leader-set tools; keys and
    values must be strings, Setting an value to the empty string is the
    same as deleting the entry, and accessing a missing entry will
    return an empty string.

    This class provides access to legacy Juju Leadership data, and namespace
    collisions may occur if multiple components attempt to use the same key.
    """

    def __init__(self, parent, key=""):
        super().__init__(parent, key, LeadershipSettings(), _RawCodec())

    def _prefixed_key(self, key: str) -> str:
        return key


class RawLeaderData(_PeerData):
    """Raw Juju Leadership settings, a bag of data shared between peers.

    Only the leader can set data. All peer units can read.

    Behavior matches the Juju leader-get and leader-set tools; keys and
    values must be strings, Setting an value to the empty string is the
    same as deleting the entry, and accessing a missing entry will
    return an empty string.

    Keys are automatically prefixed to avoid namespace collisions in the
    Juju Leadership settings.
    """

    def __init__(self, parent, key=""):
        super().__init__(parent, key, LeadershipSettings(), _RawCodec())


class RichLeaderData(_PeerData):
    """Encoded Juju Leadership settings, a bag of data shared between peers.

    Only the leader can set data. All peer units can read.

    Operates as a standard Python MutableMapping. Keys must be strings.
    Values may be anything that the yaml library can marshal.

    Keys are automatically prefixed to avoid namespace collisions in the
    Juju Leadership settings.
    """

    def __init__(self, parent, key=""):
        super().__init__(parent, key, LeadershipSettings(), _YAMLCodec())


class _YAMLCodec(object):
    def encode(self, value: Any) -> str:
        return yaml.safe_dump(value)

    def decode(self, key: str, value: str) -> Any:
        if not value:
            # Key never existed or was deleted. If set to
            # empty string or none, value will contain
            # the YAML representation.
            raise KeyError(key)
        return yaml.safe_load(value)


class _RawCodec(object):
    def encode(self, value: Any) -> str:
        if not isinstance(value, str):
            raise TypeError(f"{self.__class__.__name__} only supports str values, got {type(value)}")
        return value

    def decode(self, value: str) -> Any:
        return value


class LeadershipSettings(collections.abc.MutableMapping):
    """Juju Leadership Settings data.

    This class provides direct access to the Juju Leadership Settings,
    a bag of data shared between peer units. Only the leader can set
    items. Keys all share the same namespace, so beware of collisions.

    This MutableMapping implements Juju behavior. Only strings are
    supported as keys and values. Deleting an entry is the same as
    setting it to the empty string. Attempting to read a missing
    key will return the empty string (this class will never raise
    a KeyError).
    """

    __cls_cache = None

    @property
    def _cache_loaded(self) -> bool:
        return self.__class__.__cls_cache is not None

    @property
    def _cache(self) -> Dict[str, str]:
        # There might be multiple instances of LeadershipSettings, but
        # the backend is shared, so the cache needs to be a class
        # attribute.
        cls = self.__class__
        if cls.__cls_cache is None:
            cmd = ["leader-get", "--format=yaml"]
            cls.__cls_cache = yaml.safe_load(subprocess.check_output(cmd).decode("UTF-8")) or {}
        return cls.__cls_cache

    def __getitem__(self, key: str) -> str:
        return self._cache.get(key, "")

    def __setitem__(self, key: str, value: str):
        if "=" in key:
            # Leave other validation to the leader-set tool
            raise RuntimeError(f"LeadershipSettings keys may not contain '=', got {key}")
        if value is None:
            value = ""
        cmd = ["leader-set", f"{key}={value}"]
        subprocess.check_call(cmd)
        if self._cache_loaded:
            if value == "":
                del self._cache[key]
            else:
                self._cache[key] = value

    def __delitem__(self, key: str):
        self[key] = ""

    def __iter__(self) -> Iterable[str]:
        return iter(self._cache)

    def __len__(self) -> int:
        return len(self._cache)
