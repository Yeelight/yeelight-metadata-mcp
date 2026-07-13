#!/bin/bash
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$PROJECT_DIR/.venv"
PID_FILE="$PROJECT_DIR/uvicorn.pid"

APP_NAME="streamable_http_app"
PORT="${METADATA_MCP_PORT:-9010}"
RUNTIME_ENV="${METADATA_MCP_RUNTIME_ENV:-${APP_MCP_RUNTIME_ENV:-prod}}"
if [ -n "$METADATA_MCP_BIND_HOST" ]; then
    HOST="$METADATA_MCP_BIND_HOST"
elif [ -n "$APP_MCP_BIND_HOST" ]; then
    HOST="$APP_MCP_BIND_HOST"
elif [ "$RUNTIME_ENV" = "local" ] || [ "$RUNTIME_ENV" = "test" ]; then
    HOST="127.0.0.1"
else
    HOST="0.0.0.0"
fi
WORKERS="${METADATA_MCP_WORKERS:-4}"

start() {
    UVICORN_CMD="$VENV_DIR/bin/uvicorn main:$APP_NAME --host $HOST --port $PORT --workers $WORKERS"
    if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
        echo "服务已在运行，PID $(cat "$PID_FILE")"
        exit 1
    fi
    cd "$PROJECT_DIR" || exit 1
    source "$VENV_DIR/bin/activate"
    $UVICORN_CMD
}

stop() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if kill -0 "$PID" 2>/dev/null; then
            kill TERM "$PID"
            echo "服务已停止"
        else
            echo "PID 文件存在，但进程未运行"
        fi
        rm -f "$PID_FILE"
    else
        echo "未找到 PID 文件，服务可能未运行"
    fi
}

status() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if kill -0 "$PID" 2>/dev/null; then
            echo "服务运行中，PID $PID"
        else
            echo "PID 文件存在，但进程未运行"
        fi
    else
        echo "服务未运行"
    fi
}

restart() {
    stop
    sleep 1
    start
}

case "$1" in
    start)
        start
        ;;
    stop)
        stop
        ;;
    restart)
        restart
        ;;
    status)
        status
        ;;
    *)
        echo "用法: $0 {start|stop|restart|status}"
        exit 1
        ;;
esac
