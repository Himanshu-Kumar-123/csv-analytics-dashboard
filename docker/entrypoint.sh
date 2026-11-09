#!/bin/sh
set -eu

: "${APP_INSTANCE_PATH:=/data}"
mkdir -p "$APP_INSTANCE_PATH"

# Generate and persist a secret key on first start if none was provided.
if [ -z "${SECRET_KEY:-}" ]; then
    key_file="$APP_INSTANCE_PATH/.secret_key"
    if [ ! -s "$key_file" ]; then
        (umask 077 && python -c "import secrets; print(secrets.token_hex(32))" > "$key_file")
    fi
    SECRET_KEY="$(cat "$key_file")"
    export SECRET_KEY
fi

flask --app wsgi db upgrade

exec "$@"
