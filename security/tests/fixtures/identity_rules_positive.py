AUTHENTICATION_DISABLED = True


def unsafe_cookie(response: object) -> None:
    response.set_cookie("pm_session", "synthetic", secure=False)
