# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.

"""User-defined exceptions used by WordPress charm."""
import ops.model

__all__ = [
    "WordPressStatusException",
    "WordPressBlockedStatusException",
    "WordPressWaitingStatusException",
    "WordPressMaintenanceStatusException",
    "WordPressInstallError",
]


# This exception is used to signal the early termination of a reconciliation process.
# The early termination can be caused by many things like relation is not ready or config is not
# updated, and may turn the charm into waiting or block state. They are inevitable in the early
# stage of the charm's lifecycle, thus this is not an error (N818), same for all the subclasses.
class WordPressStatusException(Exception):  # noqa: N818
    """Exception to signal an early termination of the reconciliation.

    ``status`` represents the status change comes with the early termination.
    Do not instantiate this class directly, use subclass instead.
    """

    _status_class = ops.model.StatusBase

    def __init__(self, message):
        """Initialize the instance.

        Args:
            message: A message explaining the reason for given exception.

        Raises:
            TypeError: if same base class is used to instantiate base class.
        """
        # Using type is necessary to check types between subclasses and superclass.
        # pylint: disable=unidiomatic-typecheck
        if type(self) is WordPressStatusException:
            raise TypeError("Instantiating a base class: WordPressStatusException")
        super().__init__(message)
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
