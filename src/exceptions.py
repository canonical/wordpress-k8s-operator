# Copyright 2022 Canonical Ltd.
# Licensed under the GPLv3, see LICENCE file for details.

"""User-defined exceptions used by WordPress charm."""
import ops.model

__all__ = [
    "WordPressStatusException",
    "WordPressBlockedStatusException",
    "WordPressWaitingStatusException",
    "WordPressMaintenanceStatusException",
    "WordPressInstallError",
]


class WordPressStatusException(Exception):  # noqa: N818
    """Exception to signal an early termination of the reconciliation.

    ``status`` represents the status change comes with the early termination.
    Do not instantiate this class directly, use subclass instead.
    """

    _status_class = ops.model.StatusBase

    def __init__(self, message):
        if type(self) is WordPressStatusException:
            raise TypeError("Instantiating a base class: WordPressStatusException")
        super(WordPressStatusException, self).__init__(message)
        self.status = self._status_class(message)


class WordPressBlockedStatusException(WordPressStatusException):  # noqa: N818
    """Same as :exc:`exceptions.WordPressStatusException`."""

    _status_class = ops.model.BlockedStatus


class WordPressWaitingStatusException(WordPressStatusException):  # noqa: N818
    """Same as :exc:`exceptions.WordPressStatusException`."""

    _status_class = ops.model.WaitingStatus


class WordPressMaintenanceStatusException(WordPressStatusException):  # noqa: N818
    """Same as :exc:`exceptions.WordPressStatusException`."""

    _status_class = ops.model.MaintenanceStatus


class WordPressInstallError(Exception):
    """Exception for unrecoverable errors during WordPress installation."""

    pass
