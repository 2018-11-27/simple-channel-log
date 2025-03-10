# simple-channel-log

[![Release](https://img.shields.io/github/release/2018-11-27/simple-channel-log.svg?style=flat-square")](https://github.com/2018-11-27/simple-channel-log/releases/latest)
[![Python Version](https://img.shields.io/badge/python-2.7+/3.6+-blue.svg)](https://github.com/2018-11-27/simple-channel-log)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](https://opensource.org/licenses/MIT)
[![Downloads](https://pepy.tech/badge/simple-channel-log)](https://pepy.tech/project/simple-channel-log)

轻量高效的日志库，支持多级别日志记录、日志轮转、流水日志追踪及埋点日志功能，深度集成 Flask 和 Requests 框架。

## 主要特性

- 📅 支持按时间轮转日志（天/小时/分钟等）
- 📊 提供多级别日志记录（DEBUG/INFO/WARNING/ERROR/CRITICAL）
- 🌐 内置Flask中间件记录请求/响应流水日志（Journallog-in）
- 📡 集成Requests会话记录外部调用流水日志（Journallog-out）
- 🔍 智能处理长字符串截断（超过1000字符自动标记）
- 📁 自动创建分级日志目录结构
- 💻 支持终端输出与文件存储分离控制

## 安装

```bash
pip install simple_channel_log
```

## 快速入门

### 基础配置

```python
# coding:utf-8
import simple_channel_log as log

# 初始化日志配置
log.__init__("<your_appname>", logdir="/app/logs")

# 初始化后可直接调用日志方法，日志将记录到参数 `logdir` 指定的目录中
log.debug("调试信息", extra_field="value")
log.info("业务日志", user_id=123)
log.warning("异常预警", error_code=500)
log.error("系统错误", stack_trace="...")

# 埋点日志
log.trace(
    user_id=123,
    action="purchase",
    item_count=2
)
```

### Flask 流水日志

```python
# coding:utf-8
import simple_channel_log as log

# 初始化日志配置
log.__init__(..., enable_journallog_in=True)
```

设置 `enable_journallog_in=True` 表示启用 Flask 流水日志，将自动记录每个接口的调用信息。

若要在日志中记录接口编码，你需要将接口编码传递给请求对象 `flask.request`：

```python
# coding:utf-8
from flask import request

@app.get("/index")
def index():
    request.method_code = "<method_code>"  # 将接口编码传递给请求对象
    return jsonify({"msg": "ok"})
```

如果调用方已经将接口编码传递到请求头 `request.headers["Method-Code"]`，则会自动获取。

### Requests 外部调用追踪

```python
# coding:utf-8
import simple_channel_log as log

# 初始化日志配置
log.__init__(..., enable_journallog_out=True)
```

设置 `enable_journallog_out=True` 表示启用 Requests 外部调用追踪，将自动记录每个请求的调用信息。

若要在日志中记录接口编码，你需要将接口编码传递到请求头：

```python
# coding:utf-8
import requests

requests.get(..., headers={"Method-Code": "<method_code>"})
```

## 详细配置

### 初始化参数

| 参数名                   | 类型   | 默认值      | 说明                            |
|-----------------------|------|----------|-------------------------------|
| appname               | str  | 必填       | 应用名称，以服务编码开头                  |
| logdir                | str  | 系统相关默认路径 | 日志存储根目录                       |
| when                  | str  | 'D'      | 轮转周期：W(周)/D(天)/H(时)/M(分)/S(秒) |
| interval              | int  | 1        | 轮转频率                          |
| backup_count          | int  | 7        | 历史日志保留数量（0=永久）                |
| output_to_terminal    | bool | False    | 启用后日志将同时输出到控制台                |
| enable_journallog_in  | bool | False    | 启用Flask请求流水日志                 |
| enable_journallog_out | bool | False    | 启用Requests外部调用日志              |
