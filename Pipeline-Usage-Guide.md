# Jenkins Pipeline 使用指南

## 概述

这个 Pipeline 允许您从外部程序触发构建，上传代码文件夹，构建 Docker 镜像并推送到 Harbor 仓库。

## 文件说明

- `Jenkinsfile-upload-build` - 主要的 Pipeline 脚本
- `kaniko-builder-harbor.yaml` - Kaniko 构建器的 Kubernetes Pod 配置
- `trigger_build.py` - 外部程序触发构建的 Python 脚本
- `example_direct_upload/` - 示例应用代码文件夹

## 前置条件

### 1. Harbor 仓库配置

确保您的 Harbor 仓库已经配置完成：

- 仓库地址: `registry.test.shifu.dev`
- 项目名称: `test-project`
- 用户权限: 确保有推送镜像的权限

### 2. Jenkins 凭据配置

在 Jenkins 中创建以下凭据：

#### Harbor Docker Registry 凭据

```bash
kubectl create secret docker-registry harbor-credentials \
  --docker-server=registry.test.shifu.dev \
  --docker-username=admin \
  --docker-password=HarborTest123 \
  --docker-email=qxuan512@gmail.com \
  --namespace=copilot
```

#### Jenkins 凭据管理

在 Jenkins 中添加以下凭据：

1. **Docker Registry 凭据** (ID: `harbor-credentials`)
   - 类型: Username with password
   - 用户名: `admin`
   - 密码: `HarborTest123`

2. **GitHub 凭据** (ID: `github`)
   - 类型: Username with password 或 SSH Key
   - 用于从 GitHub 检出代码

### 3. Kubernetes 配置

确保 Jenkins 运行在 Kubernetes 集群中，并且有权限创建 Pod。

## Pipeline 参数说明

| 参数名 | 默认值 | 描述 |
|--------|--------|------|
| `APP_NAME` | `iot-driver` | 应用名称，将作为镜像名称的一部分 |
| `APP_VERSION` | `1.0.0` | 应用版本号 |
| `BUILD_CONTEXT` | `example_direct_upload` | 构建上下文目录 |
| `IMAGE_TAG_STRATEGY` | `version-build` | 镜像标签策略 |

### 镜像标签策略

- `version-build`: `{版本号}-{构建号}` (如: `1.0.0-123`)
- `timestamp`: `{版本号}-{时间戳}` (如: `1.0.0-20231201-143022`)
- `latest`: 使用 `latest` 标签

## 使用方法

### 1. 在 Jenkins 中创建 Pipeline 任务

1. 登录 Jenkins
2. 创建新的 Pipeline 任务
3. 在 Pipeline 配置中选择 "Pipeline script from SCM"
4. 配置 Git 仓库信息
5. 指定脚本路径为 `Jenkinsfile-upload-build`

### 2. 手动触发构建

在 Jenkins Web 界面中：

1. 进入您的 Pipeline 任务
2. 点击 "Build with Parameters"
3. 设置所需参数
4. 点击 "Build"

### 3. 通过 API 触发构建

我们提供了两个版本的触发脚本：

#### 方式 A: 使用 python-jenkins 库（推荐）

**安装依赖：**

```bash
pip install -r requirements-jenkins.txt
```

**使用 `trigger_build_improved.py` 脚本：**

```python
# 修改配置
JENKINS_CONFIG = {
    'url': 'http://localhost:8081',
    'username': 'admin',
    'api_token': 'your-api-token'
}

JOB_NAME = 'test'

# 运行脚本
python3 trigger_build_improved.py
```

**优势：**

- 基于官方的 python-jenkins 库，更稳定可靠
- 自动处理认证和错误处理
- 提供更丰富的功能（任务列表、构建监控等）
- 代码更简洁易维护

#### 方式 B: 使用原生 requests（备选）

**使用 `trigger_build.py` 脚本：**

```python
# 修改配置
JENKINS_CONFIG = {
    'url': 'http://localhost:8081',
    'username': 'admin',
    'api_token': 'your-api-token'
}

JOB_NAME = 'test'

# 运行脚本
python3 trigger_build.py
```

### 4. 构建流程

Pipeline 执行以下步骤：

1. **清理工作空间** - 清理之前的构建文件
2. **获取源代码** - 从 Git 仓库检出代码
3. **构建准备** - 验证构建环境和参数
4. **构建并推送镜像** - 使用 Kaniko 构建 Docker 镜像并推送到 Harbor
5. **验证镜像推送** - 确认镜像成功推送

## 镜像构建结果

构建成功后，镜像将被推送到：

- `registry.test.shifu.dev/test-project/{APP_NAME}:{镜像标签}`
- `registry.test.shifu.dev/test-project/{APP_NAME}:latest`

例如：

- `registry.test.shifu.dev/test-project/iot-driver:1.0.0-123`
- `registry.test.shifu.dev/test-project/iot-driver:latest`

## 自定义代码文件夹

要构建不同的应用，只需：

1. 将您的代码文件夹放在仓库根目录
2. 确保文件夹包含 `Dockerfile`
3. 在触发构建时设置 `BUILD_CONTEXT` 参数为您的文件夹名

## 故障排除

### 常见问题

1. **凭据错误**
   - 检查 Harbor 用户名密码是否正确
   - 确认 Jenkins 凭据配置正确

2. **Kaniko 构建失败**
   - 检查 Dockerfile 语法
   - 确认构建上下文路径正确

3. **推送失败**
   - 确认 Harbor 项目存在
   - 检查网络连接

### 日志查看

- Jenkins 构建日志：在构建页面查看 Console Output
- Kaniko 日志：在 Kubernetes 中查看 Pod 日志

## 安全建议

1. 使用 Jenkins 凭据管理敏感信息
2. 限制 Harbor 用户权限，只允许推送到特定项目
3. 定期轮换 API Token 和密码
4. 使用 HTTPS 连接 Jenkins 和 Harbor

## 扩展功能

可以进一步扩展 Pipeline：

- 添加代码质量检查 (SonarQube)
- 集成安全扫描 (如 Trivy)
- 添加自动化测试
- 集成通知系统 (邮件、Slack、企业微信等)
- 添加部署阶段
