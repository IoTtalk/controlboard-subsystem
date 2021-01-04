class BaseError(Exception):
    """Base error class"""
    pass


class UtilError(BaseError):
    """Base util error class"""
    pass


class EventHandlerError(BaseError):
    """Base event-handler error class"""
    pass


class CCMAPIFailError(UtilError):
    """Raised when a ccm_api returned status is not `ok`"""
    pass


class NotAuthorizedError(EventHandlerError):
    """Raised when a user proposed an unauthorized action/behavior"""
    pass


class NotFoundError(EventHandlerError):
    """
    Raised when a SA/Rule not running but accessed
        or No NA established but refresh triggered
        or A Non-existed user trying to login.
    """
    pass


class WrongSettingError(EventHandlerError):
    """ Raised when a rule is detected to be invalid """
    pass
