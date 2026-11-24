from fastapi import HTTPException, status


class LimitReached(HTTPException):
    def __init__(self, key: str, limit: int):
        super().__init__(
            status.HTTP_402_PAYMENT_REQUIRED,
            detail={"code": "limit_reached", "limit": key, "max": limit,
                    "message": f"Plan limit reached ({key}={limit}). Upgrade your plan to add more."},
        )


def not_found(what: str = "Resource") -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, f"{what} not found")


def forbidden(msg: str = "Not allowed") -> HTTPException:
    return HTTPException(status.HTTP_403_FORBIDDEN, msg)


def bad_request(msg: str) -> HTTPException:
    return HTTPException(status.HTTP_400_BAD_REQUEST, msg)
