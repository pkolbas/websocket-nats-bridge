import logging

import uvicorn

_NAME_MAP = {"uvicorn.error": "uvicorn"}


class _Formatter(logging.Formatter):
    def format(self, record):
        name = record.name
        record.name = _NAME_MAP.get(name, name)
        result = super().format(record)
        record.name = name
        return result


def main():
    formatter = _Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)

    logging.root.handlers = [handler]
    logging.root.setLevel(logging.INFO)

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        proxy_headers=True,
        forwarded_allow_ips="*",
        log_config=None,
    )


if __name__ == "__main__":
    main()
