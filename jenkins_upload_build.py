#!/usr/bin/env python3

import jenkins
import json
import sys
import time
import os
import requests
import argparse
from pathlib import Path
import zipfile


class JenkinsUploadBuilder:
    def __init__(self, jenkins_url, username, api_token):
        """
        初始化 Jenkins 文件上传构建器
        """
        try:
            self.server = jenkins.Jenkins(
                jenkins_url, username=username, password=api_token
            )
            self.jenkins_url = jenkins_url
            self.username = username
            self.api_token = api_token

            # 测试连接
            user = self.server.get_whoami()
            version = self.server.get_version()
            print(f"✅ 连接成功: {user['fullName']} @ Jenkins {version}")
        except Exception as e:
            print(f"❌ Jenkins 连接失败: {e}")
            raise

    def create_build_archive(self, source_path):
        """创建构建归档文件"""
        source_path = Path(source_path)

        if not source_path.exists():
            raise FileNotFoundError(f"源目录不存在: {source_path}")

        if not source_path.is_dir():
            raise ValueError(f"源路径必须是目录: {source_path}")

        # 自动生成归档文件名
        archive_path = f"{source_path.name}.zip"

        print(f"📦 正在创建构建归档: {source_path} -> {archive_path}")

        # 创建 ZIP 归档
        with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            for file_path in source_path.rglob("*"):
                if file_path.is_file():
                    # 计算相对路径
                    arcname = file_path.relative_to(source_path.parent)
                    zipf.write(file_path, arcname)

        print(
            f"✅ 归档创建完成: {archive_path} ({Path(archive_path).stat().st_size} bytes)"
        )
        return archive_path

    def upload_and_build(self, job_name, file_path, parameters=None):
        """上传文件并触发 Jenkins 构建"""
        try:
            # 检查任务是否存在
            if not self.server.job_exists(job_name):
                return {
                    "success": False,
                    "message": f'Jenkins 任务 "{job_name}" 不存在',
                }

            # 检查文件是否存在
            file_path = Path(file_path)
            if not file_path.exists():
                return {
                    "success": False,
                    "message": f"上传文件不存在: {file_path}",
                }

            print(f"🚀 开始触发构建任务: {job_name}")
            print(f"📁 上传文件: {file_path} ({file_path.stat().st_size} bytes)")

            # 准备上传数据
            files = {
                "BUILD_ARCHIVE": (
                    file_path.name,
                    open(file_path, "rb"),
                    "application/octet-stream",
                )
            }

            # 添加其他参数
            data = {}
            if parameters:
                print(
                    f"📋 构建参数: {json.dumps(parameters, indent=2, ensure_ascii=False)}"
                )
                data.update(parameters)

            # 构建请求 URL
            build_url = f"{self.jenkins_url}/job/{job_name}/buildWithParameters"

            # 发送 POST 请求
            print(f"📤 正在上传文件并触发构建...")

            response = requests.post(
                build_url,
                auth=(self.username, self.api_token),
                files=files,
                data=data,
                timeout=300,  # 5分钟超时
            )

            # 关闭文件
            files["BUILD_ARCHIVE"][1].close()

            if response.status_code in [200, 201]:
                print("✅ 文件上传并触发构建成功")

                # 等待构建开始
                build_number = self.wait_for_build_start(job_name)

                if build_number:
                    build_info = self.server.get_build_info(job_name, build_number)
                    return {
                        "success": True,
                        "message": "构建触发成功",
                        "build_number": build_number,
                        "build_url": build_info["url"],
                        "uploaded_file": str(file_path),
                    }
                else:
                    return {
                        "success": True,
                        "message": "构建已触发，但未能获取构建号",
                        "uploaded_file": str(file_path),
                    }
            else:
                return {
                    "success": False,
                    "message": f"HTTP 请求失败: {response.status_code} - {response.text}",
                }

        except requests.exceptions.Timeout:
            return {"success": False, "message": "上传超时，请检查网络连接或文件大小"}
        except Exception as e:
            return {"success": False, "message": f"上传失败: {str(e)}"}

    def wait_for_build_start(self, job_name, max_wait=60):
        """等待构建从队列开始执行"""
        print("⏳ 等待构建开始...")

        last_build_number = None
        try:
            # 获取当前最后一个构建号
            job_info = self.server.get_job_info(job_name)
            if job_info.get("lastBuild"):
                last_build_number = job_info["lastBuild"]["number"]
        except:
            pass

        for i in range(max_wait):
            try:
                job_info = self.server.get_job_info(job_name)

                if job_info.get("lastBuild"):
                    current_build_number = job_info["lastBuild"]["number"]

                    # 检查是否有新的构建
                    if (
                        last_build_number is None
                        or current_build_number > last_build_number
                    ):
                        # 检查最新构建是否正在进行
                        build_info = self.server.get_build_info(
                            job_name, current_build_number
                        )
                        if build_info.get("building", False):
                            print(f"🚀 构建已开始，构建号: {current_build_number}")
                            return current_build_number

                time.sleep(1)

            except Exception as e:
                print(f"等待构建开始时出错: {e}")

        print(f"⚠️  等待构建开始超时 ({max_wait}秒)")
        return None

    def get_build_status(self, job_name, build_number):
        """获取构建状态"""
        try:
            build_info = self.server.get_build_info(job_name, build_number)
            return {
                "success": True,
                "building": build_info.get("building", False),
                "result": build_info.get("result"),
                "duration": build_info.get("duration", 0),
                "url": build_info.get("url"),
                "timestamp": build_info.get("timestamp"),
                "description": build_info.get("description", ""),
            }

        except Exception as e:
            return {"success": False, "message": f"获取构建状态失败: {str(e)}"}

    def monitor_build(self, job_name, build_number, verbose=True):
        """监控构建进度并显示实时日志"""
        print(f"\n📊 监控构建: {job_name} #{build_number}")
        print(f"🔗 构建链接: {self.jenkins_url}/job/{job_name}/{build_number}/")
        print(
            f"📊 控制台输出: {self.jenkins_url}/job/{job_name}/{build_number}/console"
        )
        print("-" * 80)

        last_log_position = 0
        build_complete = False
        build_result = None
        # 添加去重记录
        displayed_info = set()

        while not build_complete:
            try:
                # 获取构建状态
                status = self.get_build_status(job_name, build_number)

                if not status["success"]:
                    print(f"❌ 获取构建状态失败: {status['message']}")
                    break

                # 检查构建是否完成
                if not status["building"]:
                    build_complete = True
                    build_result = status["result"]

                # 获取控制台输出
                try:
                    console_output = self.server.get_build_console_output(
                        job_name, build_number
                    )

                    # 只显示新的日志内容
                    new_output = console_output[last_log_position:]
                    if new_output:
                        self._process_console_output(
                            new_output, verbose, displayed_info
                        )
                        last_log_position = len(console_output)

                except Exception as log_e:
                    if verbose:
                        print(f"⚠️  获取日志失败: {log_e}")

                if not build_complete:
                    time.sleep(3)  # 每3秒检查一次

            except Exception as e:
                print(f"❌ 监控过程中出错: {e}")
                time.sleep(3)

        # 构建完成
        print("\n" + "=" * 80)
        if build_result == "SUCCESS":
            print(f"🎉 构建成功完成！")
            self._show_build_summary(job_name, build_number, True)
        else:
            print(f"💥 构建失败！结果: {build_result}")
            self._show_build_summary(job_name, build_number, False)

        return build_result == "SUCCESS"

    def _process_console_output(self, output, verbose=False, displayed_info=None):
        """处理控制台输出"""
        if not output.strip():
            return

        if displayed_info is None:
            displayed_info = set()

        lines = output.split("\n")

        for line in lines:
            if not line.strip():
                continue

            # 清理ANSI转义序列
            cleaned_line = self._clean_ansi_sequences(line)

            # 重要信息标记
            if any(
                marker in cleaned_line
                for marker in [
                    "[STAGE_START]",
                    "[STAGE_END]",
                    "[BUILD_SUCCESS]",
                    "[BUILD_INFO]",
                ]
            ):
                if "[STAGE_START]" in cleaned_line:
                    stage_name = cleaned_line.split("[STAGE_START]")[-1].strip()
                    print(f"🔧 开始阶段: {stage_name}")
                elif "[STAGE_END]" in cleaned_line:
                    stage_name = cleaned_line.split("[STAGE_END]")[-1].strip()
                    print(f"✅ 完成阶段: {stage_name}")
                elif "[BUILD_SUCCESS]" in cleaned_line:
                    content = cleaned_line.split("[BUILD_SUCCESS]")[-1].strip()
                    print(f"🎉 {content}")
                elif "[BUILD_INFO]" in cleaned_line:
                    content = cleaned_line.split("[BUILD_INFO]")[-1].strip()
                    print(f"📋 {content}")
                continue

            # 检测Jenkins Pipeline阶段
            if "[Pipeline] stage" in cleaned_line and "}" in cleaned_line:
                # 提取阶段名称
                if "(" in cleaned_line and ")" in cleaned_line:
                    stage_name = cleaned_line.split("(")[-1].split(")")[0]
                    print(f"🔧 Pipeline阶段: {stage_name}")
                continue

            # 检测镜像相关的关键信息
            if any(
                keyword in cleaned_line
                for keyword in [
                    "仓库地址:",
                    "项目:",
                    "镜像:",
                    "镜像已推送到:",
                    "registry.",
                    "harbor.",
                    "/test-project/",
                    "digest:",
                    "sha256:",
                ]
            ):
                if "仓库地址:" in cleaned_line:
                    registry = cleaned_line.split("仓库地址:")[-1].strip()
                    info_key = f"registry:{registry}"
                    if info_key not in displayed_info:
                        print(f"🏢 仓库地址: {registry}")
                        displayed_info.add(info_key)
                elif "项目:" in cleaned_line:
                    project = cleaned_line.split("项目:")[-1].strip()
                    info_key = f"project:{project}"
                    if info_key not in displayed_info:
                        print(f"📁 项目名称: {project}")
                        displayed_info.add(info_key)
                elif "镜像:" in cleaned_line and "镜像已推送到:" not in cleaned_line:
                    image = cleaned_line.split("镜像:")[-1].strip()
                    info_key = f"image_tag:{image}"
                    if info_key not in displayed_info:
                        print(f"🐳 镜像标签: {image}")
                        displayed_info.add(info_key)
                elif "镜像已推送到:" in cleaned_line:
                    image_url = cleaned_line.split("镜像已推送到:")[-1].strip()
                    info_key = f"image_url:{image_url}"
                    if info_key not in displayed_info:
                        print(f"🎯 镜像地址: {image_url}")
                        displayed_info.add(info_key)
                elif "digest:" in cleaned_line or "sha256:" in cleaned_line:
                    digest_info = cleaned_line.strip()
                    info_key = f"digest:{digest_info}"
                    if info_key not in displayed_info:
                        print(f"🔐 镜像摘要: {digest_info}")
                        displayed_info.add(info_key)
                else:
                    print(f"📦 {cleaned_line.strip()}")
                continue

            # 检测重要的构建步骤
            if any(
                pattern in cleaned_line.lower()
                for pattern in [
                    "building docker image",
                    "pushing to registry",
                    "build succeeded",
                    "build failed",
                    "构建成功",
                    "构建失败",
                    "镜像推送验证",
                    "清理构建环境",
                    "error:",
                    "warning:",
                    "✅",
                    "❌",
                    "🐳",
                    "📤",
                    "🎉",
                    "🧹",
                ]
            ):
                print(f"📝 {cleaned_line.strip()}")
            elif verbose:
                # 详细模式显示更多信息
                if any(
                    pattern in cleaned_line
                    for pattern in [
                        "Step ",
                        "Successfully built",
                        "Successfully tagged",
                        "Sending build context",
                        "sha256:",
                        "digest:",
                        "latest:",
                        "FROM ",
                        "RUN ",
                        "COPY ",
                        "WORKDIR ",
                        "EXPOSE ",
                        "CMD ",
                    ]
                ):
                    print(f"   {cleaned_line.strip()}")

    def _clean_ansi_sequences(self, text):
        """清理ANSI转义序列"""
        import re

        ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
        return ansi_escape.sub("", text)

    def _show_build_summary(self, job_name, build_number, success):
        """显示构建摘要"""
        try:
            build_info = self.server.get_build_info(job_name, build_number)

            print(f"\n📋 构建摘要:")
            print(f"   构建号: #{build_number}")
            print(f"   状态: {'✅ 成功' if success else '❌ 失败'}")
            print(f"   持续时间: {build_info.get('duration', 0) / 1000:.1f} 秒")
            print(
                f"   开始时间: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(build_info.get('timestamp', 0) / 1000))}"
            )
            print(f"   构建链接: {build_info.get('url', '')}")

            # 尝试获取构建产物信息
            try:
                artifacts = build_info.get("artifacts", [])
                if artifacts:
                    print(f"\n📦 构建产物:")
                    for artifact in artifacts:
                        print(
                            f"   - {artifact['fileName']} ({artifact['relativePath']})"
                        )
            except:
                pass

        except Exception as e:
            print(f"⚠️  无法获取详细构建信息: {e}")

    def _extract_image_info(self, console_output):
        """从构建日志中提取镜像信息"""
        if not console_output:
            return {}

        image_info = {}
        lines = console_output.split("\n")

        for line in lines:
            cleaned_line = self._clean_ansi_sequences(line).strip()

            # 提取仓库地址
            if "仓库地址:" in cleaned_line:
                registry = cleaned_line.split("仓库地址:")[-1].strip()
                image_info["registry"] = registry

            # 提取项目名称
            elif "项目:" in cleaned_line:
                project = cleaned_line.split("项目:")[-1].strip()
                image_info["project"] = project

            # 提取镜像标签
            elif "镜像:" in cleaned_line and "镜像已推送到:" not in cleaned_line:
                image_tag = cleaned_line.split("镜像:")[-1].strip()
                image_info["image_tag"] = image_tag

            # 提取完整镜像地址
            elif "镜像已推送到:" in cleaned_line:
                full_url = cleaned_line.split("镜像已推送到:")[-1].strip()
                image_info["full_image_url"] = full_url

            # 提取镜像摘要
            elif "digest:" in cleaned_line or "sha256:" in cleaned_line:
                if "digest" not in image_info:  # 只保存第一个找到的digest
                    image_info["digest"] = cleaned_line.strip()

        return image_info

    def list_jobs(self):
        """列出所有任务"""
        try:
            jobs = self.server.get_jobs()
            return [job["name"] for job in jobs]
        except Exception as e:
            print(f"获取任务列表失败: {e}")
            return []

    def get_current_build_number(self, job_name):
        """
        获取当前最后一次构建号

        Args:
            job_name: 任务名称

        Returns:
            int: 构建号，如果没有构建则返回 None
        """
        try:
            job_info = self.server.get_job_info(job_name)
            if job_info.get("lastBuild"):
                return job_info["lastBuild"]["number"]
            return None
        except Exception as e:
            print(f"获取构建号失败: {e}")
            return None

    def is_job_in_queue(self, job_name):
        """
        检查任务是否在队列中（pending 状态）

        Args:
            job_name: 任务名称

        Returns:
            bool: True 如果在队列中，False 如果不在
        """
        try:
            queue_info = self.server.get_queue_info()
            if queue_info:
                for queue_job_info in queue_info:
                    if queue_job_info["task"]["name"] == job_name:
                        return True
            return False
        except Exception as e:
            print(f"检查队列状态失败: {e}")
            return False

    def wait_for_build_start_improved(
        self, job_name, expected_build_number, max_wait=60
    ):
        """
        改进的等待构建开始方法（解决 pending 期问题）

        Args:
            job_name: 任务名称
            expected_build_number: 期望的构建号
            max_wait: 最大等待时间（秒）

        Returns:
            int: 构建号，如果超时返回 None
        """
        print(f"⏳ 等待构建开始 (期望构建号: {expected_build_number})...")

        for i in range(max_wait):
            # 首先检查是否还在队列中
            if self.is_job_in_queue(job_name):
                print(f"  📋 构建仍在队列中... ({i+1}/{max_wait}s)")
                time.sleep(1)
                continue

            # 检查是否已经开始构建
            current_build_number = self.get_current_build_number(job_name)
            if current_build_number and current_build_number >= expected_build_number:
                # 检查最新构建是否正在进行
                try:
                    build_info = self.server.get_build_info(
                        job_name, current_build_number
                    )
                    if build_info.get("building", False):
                        print(f"🚀 构建已开始，构建号: {current_build_number}")
                        return current_build_number
                except:
                    pass

            time.sleep(1)

        print(f"⚠️  等待构建开始超时 ({max_wait}秒)")
        return None

    def wait_for_build_complete(
        self, job_name, build_number, max_wait=1800, show_logs=True
    ):
        """
        等待构建完成并获取结果

        Args:
            job_name: 任务名称
            build_number: 构建号
            max_wait: 最大等待时间（秒，默认30分钟）
            show_logs: 是否显示实时日志

        Returns:
            dict: 构建结果信息
        """
        if show_logs:
            # 使用实时日志监控
            success = self.monitor_build(job_name, build_number, verbose=True)

            try:
                build_info = self.server.get_build_info(job_name, build_number)
                result = build_info.get("result")
                duration = build_info.get("duration", 0) / 1000

                return {
                    "success": success,
                    "result": result,
                    "duration": duration,
                    "url": build_info.get("url"),
                    "timestamp": build_info.get("timestamp"),
                    "description": build_info.get("description", ""),
                    "build_number": build_number,
                }
            except Exception as e:
                return {
                    "success": False,
                    "error": f"获取构建信息失败: {e}",
                    "build_number": build_number,
                }
        else:
            # 原有的简单轮询方式
            print(f"📊 等待构建完成: {job_name} #{build_number}")

            start_time = time.time()

            while time.time() - start_time < max_wait:
                try:
                    build_info = self.server.get_build_info(job_name, build_number)

                    # 检查是否还在构建中
                    if not build_info.get("building", False):
                        # 构建已完成
                        result = build_info.get("result")
                        duration = build_info.get("duration", 0) / 1000

                        return {
                            "success": True,
                            "result": result,
                            "duration": duration,
                            "url": build_info.get("url"),
                            "timestamp": build_info.get("timestamp"),
                            "description": build_info.get("description", ""),
                            "build_number": build_number,
                        }
                    else:
                        # 还在构建中，显示进度
                        duration = (
                            build_info.get("duration", 0) / 1000
                            if build_info.get("duration", 0) > 0
                            else time.time() - start_time
                        )
                        print(f"  ⏳ 构建进行中... (已运行 {duration:.0f} 秒)")

                except Exception as e:
                    print(f"  ⚠️  获取构建状态出错: {e}")

                time.sleep(10)  # 每10秒检查一次

            return {
                "success": False,
                "error": f"构建等待超时 ({max_wait}秒)",
                "build_number": build_number,
            }

    def get_build_status_only(self, job_name):
        """
        仅获取最后一次构建的状态（不触发新构建）
        解决 pending 期问题

        Args:
            job_name: 任务名称

        Returns:
            dict: 构建状态信息
        """
        try:
            # 检查是否在队列中
            if self.is_job_in_queue(job_name):
                return {
                    "success": True,
                    "status": "PENDING",
                    "message": "pending期,排队构建中",
                }

            # 获取最后一次构建号
            last_build_number = self.get_current_build_number(job_name)
            if not last_build_number:
                return {"success": False, "error": "没有找到构建记录"}

            # 获取构建信息
            build_info = self.server.get_build_info(job_name, last_build_number)
            build_result = build_info.get("result")

            if build_result == "SUCCESS":
                return {
                    "success": True,
                    "status": "SUCCESS",
                    "message": "构建成功",
                    "build_number": last_build_number,
                    "url": build_info.get("url"),
                    "duration": build_info.get("duration", 0) / 1000,
                }
            elif build_result == "FAILURE":
                return {
                    "success": True,
                    "status": "FAILURE",
                    "message": "构建失败",
                    "build_number": last_build_number,
                    "url": build_info.get("url"),
                    "duration": build_info.get("duration", 0) / 1000,
                }
            elif build_result is None:
                return {
                    "success": True,
                    "status": "BUILDING",
                    "message": "构建中,请稍后获取测试结果",
                    "build_number": last_build_number,
                    "url": build_info.get("url"),
                }
            else:
                return {
                    "success": True,
                    "status": build_result,
                    "message": f"构建状态: {build_result}",
                    "build_number": last_build_number,
                    "url": build_info.get("url"),
                    "duration": build_info.get("duration", 0) / 1000,
                }

        except Exception as e:
            return {"success": False, "error": f"获取构建状态失败: {str(e)}"}

    def get_console_output(self, job_name, build_number):
        """
        获取构建的控制台输出日志

        Args:
            job_name: 任务名称
            build_number: 构建号

        Returns:
            str: 控制台输出内容
        """
        try:
            return self.server.get_build_console_output(job_name, build_number)
        except Exception as e:
            return f"获取控制台输出失败: {e}"

    def trigger_build_and_wait_result(
        self, job_name, parameters=None, wait_timeout=1800
    ):
        """
        触发构建并等待完成，返回构建结果
        解决 pending 期问题的完整接口

        Args:
            job_name: 任务名称
            parameters: 构建参数
            wait_timeout: 等待超时时间（秒）

        Returns:
            dict: 包含构建结果的字典
        """
        try:
            # 检查任务是否存在
            if not self.server.job_exists(job_name):
                return {"success": False, "error": f'Jenkins 任务 "{job_name}" 不存在'}

            print(f"🚀 开始触发构建任务: {job_name}")

            # 获取触发前的构建号
            current_build_number = self.get_current_build_number(job_name)
            expected_build_number = (current_build_number or 0) + 1

            print(f"📋 当前最后构建号: {current_build_number}")
            print(f"📋 期望新构建号: {expected_build_number}")

            # 触发构建
            if parameters:
                print(
                    f"📋 构建参数: {json.dumps(parameters, indent=2, ensure_ascii=False)}"
                )
                queue_item_number = self.server.build_job(job_name, parameters)
            else:
                queue_item_number = self.server.build_job(job_name)

            print(f"✅ 构建已加入队列，队列项编号: {queue_item_number}")

            # 等待构建开始（解决 pending 期问题）
            actual_build_number = self.wait_for_build_start_improved(
                job_name, expected_build_number
            )

            if not actual_build_number:
                return {"success": False, "error": "等待构建开始超时"}

            print(
                f"🔗 构建链接: {self.jenkins_url}/job/{job_name}/{actual_build_number}/"
            )

            # 等待构建完成
            result = self.wait_for_build_complete(
                job_name, actual_build_number, wait_timeout, show_logs=True
            )

            if result["success"]:
                build_result = result["result"]
                duration = result["duration"]

                # 获取构建日志
                console_output = self.get_console_output(job_name, actual_build_number)

                if build_result == "SUCCESS":
                    print(f"🎉 构建成功完成! (耗时 {duration:.0f} 秒)")
                    return {
                        "success": True,
                        "status": "SUCCESS",
                        "message": "构建成功",
                        "build_number": actual_build_number,
                        "duration": duration,
                        "url": result["url"],
                        "console_output": console_output,
                    }
                elif build_result == "FAILURE":
                    print(f"❌ 构建失败! (耗时 {duration:.0f} 秒)")
                    return {
                        "success": False,
                        "status": "FAILURE",
                        "message": "构建失败",
                        "build_number": actual_build_number,
                        "duration": duration,
                        "url": result["url"],
                        "console_output": console_output,
                    }
                elif build_result == "ABORTED":
                    print(f"⚠️  构建被中止! (耗时 {duration:.0f} 秒)")
                    return {
                        "success": False,
                        "status": "ABORTED",
                        "message": "构建被中止",
                        "build_number": actual_build_number,
                        "duration": duration,
                        "url": result["url"],
                        "console_output": console_output,
                    }
                else:
                    return {
                        "success": False,
                        "status": build_result or "UNKNOWN",
                        "message": f"构建结束，状态: {build_result}",
                        "build_number": actual_build_number,
                        "duration": duration,
                        "url": result["url"],
                        "console_output": console_output,
                    }
            else:
                return {
                    "success": False,
                    "error": result.get("error", "构建失败"),
                    "build_number": actual_build_number,
                }

        except Exception as e:
            return {"success": False, "error": f"构建过程出错: {str(e)}"}


def prepare_example_context():
    """准备示例构建上下文（如果不存在）"""
    source_dir = "example_direct_upload_test"
    dockerfile_content = """# 示例 Dockerfile
FROM alpine:latest

# 安装基本工具
RUN apk add --no-cache curl

# 创建应用目录
WORKDIR /app

# 复制应用文件
COPY . .

# 设置启动命令
CMD ["echo", "Hello from uploaded build context!"]
"""

    app_content = """#!/bin/sh
echo "This is a sample application"
echo "Built from uploaded context"
"""

    if not os.path.exists(source_dir):
        print(f"📁 创建示例构建上下文: {source_dir}")
        os.makedirs(source_dir)

        # 创建 Dockerfile
        with open(os.path.join(source_dir, "Dockerfile"), "w") as f:
            f.write(dockerfile_content)

        # 创建示例应用文件
        with open(os.path.join(source_dir, "app.sh"), "w") as f:
            f.write(app_content)

        print(f"✅ 示例构建上下文已创建")
        print(f"   - {source_dir}/Dockerfile")
        print(f"   - {source_dir}/app.sh")

        return True

    return False


def parse_arguments():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description="Jenkins 文件上传构建工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  # 使用默认配置
  python3 jenkins_upload_build.py
  
  # 自定义Jenkins配置
  python3 jenkins_upload_build.py --jenkins-url http://localhost:8080 --username admin --api-token YOUR_TOKEN
  
  # 自定义构建参数
  python3 jenkins_upload_build.py --job-name my-job --source-dir ./my-project --app-name my-app --app-version 2.0.0
  
  # 控制构建选项
  python3 jenkins_upload_build.py --no-monitor --no-logs --no-cleanup
        """,
    )

    # Jenkins 连接配置
    jenkins_group = parser.add_argument_group("Jenkins 连接配置")
    jenkins_group.add_argument(
        "--jenkins-url",
        default="http://localhost:8080",
        help="Jenkins 服务器 URL (默认: http://localhost:8080)",
    )
    jenkins_group.add_argument(
        "--username", default="admin", help="Jenkins 用户名 (默认: admin)"
    )
    jenkins_group.add_argument(
        "--api-token",
        default="11b2624bb2ab06d44424d657f387f40aeb",
        help="Jenkins API Token (默认: 内置token)",
    )

    # 构建任务配置
    build_group = parser.add_argument_group("构建任务配置")
    build_group.add_argument(
        "--job-name", default="test4", help="Jenkins 任务名称 (默认: test4)"
    )
    build_group.add_argument(
        "--source-dir",
        default="example_direct_upload_test",
        help="本地源代码目录 (默认: example_direct_upload_test)",
    )

    # 构建参数
    params_group = parser.add_argument_group("构建参数")
    params_group.add_argument(
        "--app-name", default="my-app", help="应用名称 (默认: my-app)"
    )
    params_group.add_argument(
        "--app-version", default="1.0.0", help="应用版本 (默认: 1.0.0)"
    )
    params_group.add_argument("--build-context", help="构建上下文 (默认: 与源目录同名)")
    params_group.add_argument(
        "--image-tag-strategy",
        default="version-build",
        choices=["version-build", "latest", "timestamp"],
        help="镜像标签策略 (默认: version-build)",
    )

    # 构建选项
    options_group = parser.add_argument_group("构建选项")
    options_group.add_argument(
        "--no-monitor", action="store_true", help="不监控构建过程"
    )
    options_group.add_argument(
        "--no-logs", action="store_true", help="不显示实时构建日志"
    )
    options_group.add_argument(
        "--no-cleanup", action="store_true", help="不自动清理临时文件"
    )
    options_group.add_argument(
        "--no-auto-create", action="store_true", help="不自动创建示例目录"
    )
    options_group.add_argument(
        "--quiet", action="store_true", help="静默模式，减少输出信息"
    )

    # 其他选项
    other_group = parser.add_argument_group("其他选项")
    other_group.add_argument(
        "--list-jobs", action="store_true", help="列出所有Jenkins任务后退出"
    )
    other_group.add_argument(
        "--test-connection", action="store_true", help="仅测试Jenkins连接后退出"
    )
    other_group.add_argument("--config-file", help="从JSON文件加载配置")
    other_group.add_argument(
        "--generate-config", action="store_true", help="生成示例配置文件并退出"
    )

    return parser.parse_args()


def load_config_from_file(config_file):
    """从配置文件加载配置"""
    try:
        with open(config_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ 加载配置文件失败: {e}")
        sys.exit(1)


def merge_config(args, file_config=None):
    """合并命令行参数和配置文件"""
    # 构建最终配置
    jenkins_config = {
        "url": args.jenkins_url,
        "username": args.username,
        "api_token": args.api_token,
    }

    job_name = args.job_name
    source_dir = args.source_dir

    build_params = {
        "APP_NAME": args.app_name,
        "APP_VERSION": args.app_version,
        "BUILD_CONTEXT": args.build_context or args.source_dir,
        "IMAGE_TAG_STRATEGY": args.image_tag_strategy,
    }

    build_options = {
        "auto_create_example": not args.no_auto_create,
        "auto_cleanup": not args.no_cleanup,
        "monitor_build": not args.no_monitor,
        "show_build_logs": not args.no_logs,
        "verbose": not args.quiet,
    }

    # 如果有配置文件，覆盖相应配置
    if file_config:
        if "jenkins" in file_config:
            jenkins_config.update(file_config["jenkins"])
        if "job_name" in file_config:
            job_name = file_config["job_name"]
        if "source_dir" in file_config:
            source_dir = file_config["source_dir"]
        if "build_params" in file_config:
            build_params.update(file_config["build_params"])
        if "build_options" in file_config:
            build_options.update(file_config["build_options"])

    return jenkins_config, job_name, source_dir, build_params, build_options


def generate_example_config():
    """生成示例配置文件"""
    config = {
        "jenkins": {
            "url": "http://localhost:8080",
            "username": "admin",
            "api_token": "your_jenkins_api_token_here",
        },
        "job_name": "test4",
        "source_dir": "example_direct_upload_test",
        "build_params": {
            "APP_NAME": "my-app",
            "APP_VERSION": "1.0.0",
            "BUILD_CONTEXT": "example_direct_upload_test",
            "IMAGE_TAG_STRATEGY": "version-build",
        },
        "build_options": {
            "auto_create_example": True,
            "auto_cleanup": True,
            "monitor_build": True,
            "show_build_logs": True,
            "verbose": True,
        },
    }

    config_file = "jenkins_build_config.json"
    try:
        with open(config_file, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        print(f"✅ 示例配置文件已生成: {config_file}")
        print(f"请编辑此文件后使用: --config-file {config_file}")
        return True
    except Exception as e:
        print(f"❌ 生成配置文件失败: {e}")
        return False


def main():
    """主函数 - 文件上传构建"""

    # 解析命令行参数
    args = parse_arguments()

    # 处理生成配置文件
    if args.generate_config:
        return generate_example_config()

    # 加载配置文件（如果指定）
    file_config = None
    if args.config_file:
        file_config = load_config_from_file(args.config_file)

    # 合并配置
    jenkins_config, job_name, source_dir, build_params, build_options = merge_config(
        args, file_config
    )

    if not args.quiet:
        print("🚀 Jenkins 文件上传构建工具")
        print("=" * 50)

        print(f"\n🔧 当前配置:")
        print(f"Jenkins URL: {jenkins_config['url']}")
        print(f"任务名称: {job_name}")
        print(f"源目录: {source_dir}")
        print(f"应用名称: {build_params['APP_NAME']}")
        print(f"应用版本: {build_params['APP_VERSION']}")

    try:
        # 创建 Jenkins 构建器
        builder = JenkinsUploadBuilder(
            jenkins_url=jenkins_config["url"],
            username=jenkins_config["username"],
            api_token=jenkins_config["api_token"],
        )

        # 处理特殊命令
        if args.list_jobs:
            print(f"\n📋 可用的 Jenkins 任务:")
            jobs = builder.list_jobs()
            for i, job in enumerate(jobs, 1):
                print(f"  {i:2d}. {job}")
            return True

        if args.test_connection:
            print(f"\n✅ Jenkins 连接测试成功")
            return True

        # 检查源目录是否存在
        if not os.path.exists(source_dir):
            if not args.quiet:
                print(f"❌ 源目录不存在: {source_dir}")

            # 自动创建示例目录
            if build_options["auto_create_example"]:
                if not args.quiet:
                    print("🔧 自动创建示例构建目录...")
                if prepare_example_context():
                    if not args.quiet:
                        print("✅ 示例目录创建成功，继续构建...")
                else:
                    if not args.quiet:
                        print("✅ 示例目录已存在，继续构建...")
                # 更新源目录为默认示例目录
                source_dir = "example_direct_upload_test"
            else:
                print(f"❌ 请确保目录 '{source_dir}' 存在并包含 Dockerfile")
                return False

        # 检查 Dockerfile 是否存在
        dockerfile_path = os.path.join(source_dir, "Dockerfile")
        if not os.path.exists(dockerfile_path):
            print(f"❌ Dockerfile 不存在: {dockerfile_path}")
            print("请确保构建目录包含 Dockerfile")
            return False

        if not args.quiet:
            print(f"📁 源目录: {source_dir}")
            print(f"📄 Dockerfile: {dockerfile_path}")

            # 显示可用任务
            print(f"\n📋 可用的 Jenkins 任务:")
            jobs = builder.list_jobs()
            for job in jobs:
                print(f"  - {job}")

            if job_name not in jobs:
                print(f"\n⚠️  任务 '{job_name}' 不在可用任务列表中")
                print("请检查任务名称或确认任务已创建")
                return False

        # 创建构建归档
        if not args.quiet:
            print(f"\n📦 正在打包构建上下文...")
        archive_path = builder.create_build_archive(source_dir)

        # 上传文件并触发构建
        if not args.quiet:
            print(f"\n🚀 上传文件并触发构建...")
        result = builder.upload_and_build(job_name, archive_path, build_params)

        # 清理临时文件
        if build_options["auto_cleanup"]:
            try:
                os.remove(archive_path)
                if not args.quiet:
                    print(f"🧹 已清理临时归档: {archive_path}")
            except:
                pass
        else:
            if not args.quiet:
                print(f"📁 保留临时归档文件: {archive_path}")

        # 处理结果
        if result["success"]:
            if not args.quiet:
                print(f"\n✅ {result['message']}")

            build_number = result.get("build_number")
            if build_number:
                if not args.quiet:
                    print(f"🔗 构建链接: {result.get('build_url', 'N/A')}")

                # 监控构建状态
                if build_options["monitor_build"]:
                    if build_options["show_build_logs"]:
                        if not args.quiet:
                            print(
                                f"\n📊 开始监控构建 #{build_number} (显示实时日志)..."
                            )
                        builder.monitor_build(
                            job_name, build_number, verbose=build_options["verbose"]
                        )
                    else:
                        if not args.quiet:
                            print(f"\n📊 开始监控构建 #{build_number} (仅显示状态)...")
                        # 使用原有的简单监控方式
                        while True:
                            status = builder.get_build_status(job_name, build_number)
                            if not status["success"]:
                                if not args.quiet:
                                    print(f"❌ 获取构建状态失败: {status['message']}")
                                break
                            if status["building"]:
                                duration = (
                                    status["duration"] / 1000
                                    if status["duration"] > 0
                                    else 0
                                )
                                if not args.quiet:
                                    print(
                                        f"⏳ 构建进行中... (已运行 {duration:.0f} 秒)"
                                    )
                                time.sleep(10)
                            else:
                                result_status = status["result"]
                                duration = (
                                    status["duration"] / 1000
                                    if status["duration"] > 0
                                    else 0
                                )
                                if not args.quiet:
                                    if result_status == "SUCCESS":
                                        print(
                                            f"🎉 构建成功完成! (耗时 {duration:.0f} 秒)"
                                        )
                                    elif result_status == "FAILURE":
                                        print(f"❌ 构建失败! (耗时 {duration:.0f} 秒)")
                                    elif result_status == "ABORTED":
                                        print(
                                            f"⚠️  构建被中止! (耗时 {duration:.0f} 秒)"
                                        )
                                    else:
                                        print(
                                            f"⚠️  构建结束，状态: {result_status} (耗时 {duration:.0f} 秒)"
                                        )
                                    print(f"🔗 构建链接: {status['url']}")
                                break
                else:
                    if not args.quiet:
                        print(f"✅ 构建已启动 #{build_number}，跳过监控")
            else:
                if not args.quiet:
                    print("⚠️  构建已触发，但无法获取构建号")
        else:
            print(f"\n❌ 构建触发失败: {result['message']}")
            return False

        return True

    except Exception as e:
        print(f"\n❌ 执行出错: {e}")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
