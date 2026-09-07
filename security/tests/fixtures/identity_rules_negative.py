def secure_cookie(response: object, secure_configuration: bool) -> None:
    response.set_cookie("pm_session", "synthetic", secure=secure_configuration)
