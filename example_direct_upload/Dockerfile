# IoT 驱动示例 Dockerfile
FROM ubuntu:20.04

# 设置非交互模式安装
ENV DEBIAN_FRONTEND=noninteractive

# 安装基础依赖
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    wget \
    curl \
    vim \
    && rm -rf /var/lib/apt/lists/*

# 设置工作目录
WORKDIR /app

# 复制驱动文件
COPY . /app/

# 安装 Python 依赖
RUN if [ -f requirements.txt ]; then pip3 install -r requirements.txt; fi

# 创建日志目录
RUN mkdir -p /var/log/iot-driver

# 设置环境变量
ENV IOT_DRIVER_NAME="example-driver"
ENV IOT_DRIVER_VERSION="1.0.0"
ENV LOG_LEVEL="INFO"

# 暴露端口 (根据需要修改)
EXPOSE 8080

# 设置启动命令
CMD ["python3", "main.py"] 