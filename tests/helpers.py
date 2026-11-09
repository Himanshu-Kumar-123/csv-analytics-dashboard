from __future__ import annotations

import io
from typing import Any

from flask.testing import FlaskClient


def upload_csv(
    client: FlaskClient,
    headers: dict[str, str],
    content: bytes | str,
    filename: str = "data.csv",
    name: str | None = None,
) -> Any:
    if isinstance(content, str):
        content = content.encode("utf-8")
    data: dict[str, Any] = {"file": (io.BytesIO(content), filename)}
    if name is not None:
        data["name"] = name
    return client.post(
        "/api/v1/datasets", data=data, headers=headers, content_type="multipart/form-data"
    )


SIMPLE_CSV = (
    "id,name,city,score,joined\n"
    "1,Asha,Delhi,88.5,2023-01-05\n"
    "2,Ravi,Pune,72.0,2023-02-11\n"
    "3,Meera,Delhi,,2023-03-20\n"
    "4,John,Mumbai,91.25,2023-04-02\n"
    "5,Asha,Delhi,88.5,2023-01-05\n"
)
