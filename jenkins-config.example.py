#!/usr/bin/env python3
"""
Jenkins 配置文件示例
复制此文件为 jenkins-config.py 并修改配置
"""

# Jenkins 服务器配置
JENKINS_CONFIG = {
    "url": "http://localhost:8081",  # Jenkins 服务器地址
    "username": "admin",  # Jenkins 用户名
    "api_token": "your-api-token",  # Jenkins API Token (在用户设置中生成)
}

# 任务配置
JOB_NAME = "test"  # Jenkins Pipeline 任务名称

# 默认构建参数
DEFAULT_BUILD_PARAMS = {
    "APP_NAME": "iot-driver",
    "APP_VERSION": "1.0.1",
    "BUILD_CONTEXT": "example_direct_upload",
    "IMAGE_TAG_STRATEGY": "version-build",
}

# 如何获取 Jenkins API Token:
# 1. 登录 Jenkins
# 2. 点击右上角用户名 -> Configure
# 3. 在 API Token 部分点击 "Add new Token"
# 4. 给 Token 起个名字，点击 "Generate"
# 5. 复制生成的 Token 并替换上面的 'your-api-token'
