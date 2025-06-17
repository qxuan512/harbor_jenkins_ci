#!/usr/bin/env python3
"""
Jenkins Pipeline 远程触发脚本
用于从外部程序触发 Jenkins 构建任务
"""

import requests
import json
import base64
import sys
import time
from urllib.parse import urljoin


class JenkinsTrigger:
    def __init__(self, jenkins_url, username, api_token):
        """
        初始化 Jenkins 触发器

        Args:
            jenkins_url: Jenkins 服务器地址，如 'http://jenkins.example.com:8080'
            username: Jenkins 用户名
            api_token: Jenkins API Token (不是密码)
        """
        self.jenkins_url = jenkins_url.rstrip("/")
        self.username = username
        self.api_token = api_token
        self.auth = (username, api_token)

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
            if parameters:
                # 带参数的构建
                url = f"{self.jenkins_url}/job/{job_name}/buildWithParameters"
                response = requests.post(url, auth=self.auth, data=parameters)
            else:
                # 不带参数的构建
                url = f"{self.jenkins_url}/job/{job_name}/build"
                response = requests.post(url, auth=self.auth)

            if response.status_code == 201:
                # 获取队列 URL
                queue_url = response.headers.get("Location")
                print(f"✅ 构建已加入队列: {queue_url}")

                # 等待并获取构建号
                build_number = self.wait_for_build_start(queue_url)

                return {
                    "success": True,
                    "message": "构建触发成功",
                    "queue_url": queue_url,
                    "build_number": build_number,
                    "build_url": f"{self.jenkins_url}/job/{job_name}/{build_number}/",
                }
            else:
                return {
                    "success": False,
                    "message": f"构建触发失败: HTTP {response.status_code}",
                    "details": response.text,
                }

        except requests.exceptions.RequestException as e:
            return {"success": False, "message": f"网络请求失败: {str(e)}"}

    def wait_for_build_start(self, queue_url, max_wait=60):
        """
        等待构建从队列开始执行

        Args:
            queue_url: 队列 URL
            max_wait: 最大等待时间（秒）

        Returns:
            int: 构建号，如果超时返回 None
        """
        if not queue_url:
            return None

        print("⏳ 等待构建开始...")

        for i in range(max_wait):
            try:
                response = requests.get(queue_url + "api/json", auth=self.auth)
                if response.status_code == 200:
                    data = response.json()

                    # 检查是否已经开始构建
                    if "executable" in data and data["executable"]:
                        build_number = data["executable"]["number"]
                        print(f"🚀 构建已开始，构建号: {build_number}")
                        return build_number

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
            url = f"{self.jenkins_url}/job/{job_name}/{build_number}/api/json"
            response = requests.get(url, auth=self.auth)

            if response.status_code == 200:
                data = response.json()
                return {
                    "success": True,
                    "building": data.get("building", False),
                    "result": data.get("result"),
                    "duration": data.get("duration", 0),
                    "url": data.get("url"),
                }
            else:
                return {
                    "success": False,
                    "message": f"获取构建状态失败: HTTP {response.status_code}",
                }

        except requests.exceptions.RequestException as e:
            return {"success": False, "message": f"网络请求失败: {str(e)}"}


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

    # 创建触发器实例
    trigger = JenkinsTrigger(
        jenkins_url=JENKINS_CONFIG["url"],
        username=JENKINS_CONFIG["username"],
        api_token=JENKINS_CONFIG["api_token"],
    )

    print("🚀 开始触发 Jenkins 构建...")
    print(f"任务名称: {JOB_NAME}")
    print(f"构建参数: {json.dumps(BUILD_PARAMS, indent=2, ensure_ascii=False)}")

    # 触发构建
    result = trigger.trigger_build(JOB_NAME, BUILD_PARAMS)

    if result["success"]:
        print(f"✅ {result['message']}")
        print(f"🔗 构建链接: {result.get('build_url', '暂未获取')}")

        # 如果有构建号，可以继续监控构建状态
        build_number = result.get("build_number")
        if build_number:
            print(f"\n📊 监控构建状态 (构建号: {build_number})...")

            # 简单的状态监控循环
            for i in range(30):  # 最多监控30次
                status = trigger.get_build_status(JOB_NAME, build_number)

                if status["success"]:
                    if status["building"]:
                        print(f"⏳ 构建进行中... ({i+1}/30)")
                        time.sleep(10)  # 每10秒检查一次
                    else:
                        result = status["result"]
                        if result == "SUCCESS":
                            print("🎉 构建成功完成!")
                        elif result == "FAILURE":
                            print("❌ 构建失败!")
                        else:
                            print(f"⚠️  构建结束，状态: {result}")
                        break
                else:
                    print(f"❌ 获取构建状态失败: {status['message']}")
                    break
    else:
        print(f"❌ {result['message']}")
        if "details" in result:
            print(f"详细信息: {result['details']}")
        sys.exit(1)


if __name__ == "__main__":
    main()
