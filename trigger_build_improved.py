#!/usr/bin/env python3
"""
Jenkins Pipeline 远程触发脚本 (基于 python-jenkins 库)
使用 python-jenkins 库触发 Jenkins 构建任务
"""

import jenkins
import json
import sys
import time


class JenkinsTrigger:
    def __init__(self, jenkins_url, username, api_token):
        """
        初始化 Jenkins 触发器

        Args:
            jenkins_url: Jenkins 服务器地址，如 'http://jenkins.example.com:8080'
            username: Jenkins 用户名
            api_token: Jenkins API Token (不是密码)
        """
        try:
            self.server = jenkins.Jenkins(
                jenkins_url, username=username, password=api_token
            )
            # 测试连接
            user = self.server.get_whoami()
            version = self.server.get_version()
            print(f"✅ 连接成功: {user['fullName']} @ Jenkins {version}")
        except Exception as e:
            print(f"❌ Jenkins 连接失败: {e}")
            raise

    def trigger_build(self, job_name, parameters=None):
        """
        触发 Jenkins 构建任务

        Args:
            job_name: Jenkins 任务名称
            parameters: 构建参数字典

        Returns:
            dict: 包含构建结果的字典
        """
        try:
            # 检查任务是否存在
            if not self.server.job_exists(job_name):
                return {
                    "success": False,
                    "message": f'Jenkins 任务 "{job_name}" 不存在',
                }

            print(f"🚀 开始触发构建任务: {job_name}")

            # 触发构建
            if parameters:
                print(
                    f"📋 构建参数: {json.dumps(parameters, indent=2, ensure_ascii=False)}"
                )
                queue_item_number = self.server.build_job(job_name, parameters)
            else:
                queue_item_number = self.server.build_job(job_name)

            print(f"✅ 构建已加入队列，队列项编号: {queue_item_number}")

            # 等待构建开始
            build_number = self.wait_for_build_start(job_name)

            if build_number:
                build_info = self.server.get_build_info(job_name, build_number)
                return {
                    "success": True,
                    "message": "构建触发成功",
                    "build_number": build_number,
                    "build_url": build_info["url"],
                    "queue_item_number": queue_item_number,
                }
            else:
                return {
                    "success": True,
                    "message": "构建已触发，但未能获取构建号",
                    "queue_item_number": queue_item_number,
                }

        except jenkins.JenkinsException as e:
            return {"success": False, "message": f"Jenkins 操作失败: {str(e)}"}
        except Exception as e:
            return {"success": False, "message": f"未知错误: {str(e)}"}

    def wait_for_build_start(self, job_name, max_wait=60):
        """
        等待构建从队列开始执行

        Args:
            job_name: 任务名称
            max_wait: 最大等待时间（秒）

        Returns:
            int: 构建号，如果超时返回 None
        """
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
        """
        获取构建状态

        Args:
            job_name: 任务名称
            build_number: 构建号

        Returns:
            dict: 构建状态信息
        """
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

        except jenkins.JenkinsException as e:
            return {"success": False, "message": f"获取构建状态失败: {str(e)}"}
        except Exception as e:
            return {"success": False, "message": f"未知错误: {str(e)}"}

    def get_console_output(self, job_name, build_number):
        """
        获取构建的控制台输出

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

    def list_jobs(self):
        """
        列出所有任务

        Returns:
            list: 任务列表
        """
        try:
            jobs = self.server.get_jobs()
            return [job["name"] for job in jobs]
        except Exception as e:
            print(f"获取任务列表失败: {e}")
            return []

    def monitor_build(self, job_name, build_number, show_logs=False):
        """
        监控构建进度

        Args:
            job_name: 任务名称
            build_number: 构建号
            show_logs: 是否显示实时日志
        """
        print(f"\n📊 监控构建: {job_name} #{build_number}")

        while True:
            status = self.get_build_status(job_name, build_number)

            if not status["success"]:
                print(f"❌ 获取构建状态失败: {status['message']}")
                break

            if status["building"]:
                duration = status["duration"] / 1000 if status["duration"] > 0 else 0
                print(f"⏳ 构建进行中... (已运行 {duration:.0f} 秒)")

                if show_logs:
                    # 显示最新的控制台输出 (可选)
                    pass

                time.sleep(10)  # 每10秒检查一次
            else:
                result = status["result"]
                duration = status["duration"] / 1000 if status["duration"] > 0 else 0

                if result == "SUCCESS":
                    print(f"🎉 构建成功完成! (耗时 {duration:.0f} 秒)")
                elif result == "FAILURE":
                    print(f"❌ 构建失败! (耗时 {duration:.0f} 秒)")
                elif result == "ABORTED":
                    print(f"⚠️  构建被中止! (耗时 {duration:.0f} 秒)")
                else:
                    print(f"⚠️  构建结束，状态: {result} (耗时 {duration:.0f} 秒)")

                print(f"🔗 构建链接: {status['url']}")
                break


def main():
    """示例用法"""

    # Jenkins 配置 (请根据实际情况修改)
    JENKINS_CONFIG = {
        "url": "http://localhost:8081",
        "username": "admin",
        "api_token": "your-api-token",  # 在 Jenkins 用户设置中生成
    }

    # 任务名称
    JOB_NAME = "test"

    # 构建参数
    BUILD_PARAMS = {
        "APP_NAME": "iot-driver",
        "APP_VERSION": "1.0.1",
        "BUILD_CONTEXT": "example_direct_upload",
        "IMAGE_TAG_STRATEGY": "version-build",
    }

    try:
        # 创建触发器实例
        trigger = JenkinsTrigger(
            jenkins_url=JENKINS_CONFIG["url"],
            username=JENKINS_CONFIG["username"],
            api_token=JENKINS_CONFIG["api_token"],
        )

        # 显示可用的任务列表
        print("\n📋 可用的 Jenkins 任务:")
        jobs = trigger.list_jobs()
        for job in jobs:
            print(f"  - {job}")

        if JOB_NAME not in jobs:
            print(f"\n⚠️  任务 '{JOB_NAME}' 不在可用任务列表中")
            print("请检查任务名称或确认任务已创建")
            return

        print(f"\n🚀 开始触发 Jenkins 构建...")
        print(f"任务名称: {JOB_NAME}")

        # 触发构建
        result = trigger.trigger_build(JOB_NAME, BUILD_PARAMS)

        if result["success"]:
            print(f"✅ {result['message']}")

            # 如果有构建号，监控构建状态
            build_number = result.get("build_number")
            if build_number:
                trigger.monitor_build(JOB_NAME, build_number)
            else:
                print("⚠️  未能获取构建号，无法监控构建状态")
        else:
            print(f"❌ {result['message']}")
            sys.exit(1)

    except Exception as e:
        print(f"❌ 程序执行出错: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
