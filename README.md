# Harbor Jenkins CI Pipeline

这是一个完整的 Jenkins CI/CD Pipeline 解决方案，支持：

- 从外部程序触发构建
- 代码文件夹上传构建
- Docker 镜像构建并推送到 Harbor 仓库

## 🚀 快速开始

### 文件说明

- **`Jenkinsfile-upload-build`** - 主要的 Jenkins Pipeline 脚本
- **`kaniko-builder-harbor.yaml`** - Kaniko 构建器的 Kubernetes Pod 配置
- **`example_direct_upload/`** - 示例应用代码文件夹
- **触发脚本**:
  - `trigger_build.py` - 基于 requests 的触发脚本
  - `trigger_build_improved.py` - 基于 python-jenkins 库的改进版
  - `trigger_build_with_config.py` - 支持配置文件和命令行参数
- **配置文件**:
  - `jenkins-config.example.py` - Jenkins 配置示例
  - `requirements-jenkins.txt` - Python 依赖包
- **文档**:
  - `Pipeline-Usage-Guide.md` - 详细使用指南

### Harbor 仓库配置

- **仓库地址**: `registry.test.shifu.dev`
- **项目名称**: `test-project`
- **命名空间**: `copilot`

### 使用方法

1. **创建 Jenkins Pipeline 任务**
   - 选择 "Pipeline script from SCM"
   - Git 仓库: `https://github.com/qxuan512/harbor_jenkins_ci.git`
   - 脚本路径: `Jenkinsfile-upload-build`

2. **安装依赖并配置触发脚本**

   ```bash
   pip install -r requirements-jenkins.txt
   cp jenkins-config.example.py jenkins_config.py
   # 编辑 jenkins_config.py 设置您的 Jenkins 信息
   ```

3. **触发构建**

   ```bash
   python3 trigger_build_with_config.py --job your-job-name
   ```

## 📚 详细文档

请查看 [Pipeline-Usage-Guide.md](Pipeline-Usage-Guide.md) 获取完整的使用指南。

## 🔧 技术栈

- **Jenkins**: CI/CD 平台
- **Kaniko**: 容器镜像构建工具
- **Harbor**: Docker 镜像仓库
- **Kubernetes**: 容器编排平台
- **Python**: 自动化脚本

## 🏗️ 架构

```
外部程序 -> Jenkins API -> Jenkins Pipeline -> Kaniko -> Harbor 仓库
```

## 📄 许可证

MIT License
