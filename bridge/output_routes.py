"""Output route registration."""

from __future__ import annotations


def register_output_routes(app, *, get_output, get_raw_output, get_messages=None) -> None:
    app.get("/output")(get_output)
    if get_messages is not None:
        app.get("/messages")(get_messages)
    app.get("/raw-output")(get_raw_output)
