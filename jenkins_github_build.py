#!/usr/bin/env python3

import jenkins
import json
import os
import re
import sys
import time
import argparse
import requests
from datetime import datetime
from typing import Dict, Optional, Union, List, Any

# Constants
DEFAULT_TIMEOUT = 300
DEFAULT_QUEUE_TIMEOUT = 120
DEFAULT_BUILD_TIMEOUT = 1800
POLL_INTERVAL = 3


class JenkinsGitHubBuilder:
    def __init__(self, jenkins_url: str, username: str, api_token: str) -> None:
        """Initialize Jenkins GitHub Builder"""
        self.jenkins_url = jenkins_url
        self.username = username
        self.api_token = api_token

        try:
            self.server = jenkins.Jenkins(
                jenkins_url, username=username, password=api_token
            )
            user = self.server.get_whoami()
            version = self.server.get_version()
            print(f"✅ Connection successful: {user['fullName']} @ Jenkins {version}")
        except Exception as e:
            print(f"❌ Jenkins connection failed: {e}")
            raise

    def trigger_github_build(
        self,
        job_name: str,
        git_repository_url: str,
        git_branch: str = "main",
        git_credentials_id: str = "",
        app_name: str = "my-app",
        app_version: str = "1.0.0",
        build_context: str = ".",
        dockerfile_path: str = "Dockerfile",
        image_tag_strategy: str = "version-build",
        build_platforms: str = "linux/amd64",
        build_unique_id: str = "",
        enable_cache: bool = True,
        build_args: str = "",
    ) -> Dict[str, Any]:
        """Trigger GitHub repository build"""
        try:
            if not self.server.job_exists(job_name):
                return {
                    "success": False,
                    "message": f'Jenkins job "{job_name}" does not exist',
                }

            print(f"🚀 Starting build job: {job_name}")
            print(f"🔗 Git Repository: {git_repository_url}")
            print(f"🌿 Git Branch: {git_branch}")
            print(f"📱 App: {app_name}:{app_version}")
            print(f"🏗️  Platforms: {build_platforms}")

            build_params = {
                "GIT_REPOSITORY_URL": git_repository_url,
                "GIT_BRANCH": git_branch,
                "APP_NAME": app_name,
                "APP_VERSION": app_version,
                "BUILD_CONTEXT": build_context,
                "DOCKERFILE_PATH": dockerfile_path,
                "IMAGE_TAG_STRATEGY": image_tag_strategy,
                "BUILD_PLATFORMS": build_platforms,
                "ENABLE_CACHE": enable_cache,
            }

            if git_credentials_id:
                build_params["GIT_CREDENTIALS_ID"] = git_credentials_id
                print(f"🔐 Using Git credentials: {git_credentials_id}")

            if build_unique_id:
                build_params["BUILD_UNIQUE_ID"] = build_unique_id

            if build_args:
                build_params["BUILD_ARGS"] = build_args

            print(f"📋 Build parameters:")
            for key, value in build_params.items():
                print(f"   {key}: {value}")

            queue_item_number = self.server.build_job(job_name, build_params)
            print(f"✅ Build queued successfully")
            print(f"📋 Queue item number: {queue_item_number}")

            actual_build_number = self.wait_for_build_start_by_queue(queue_item_number)

            if actual_build_number:
                build_info = self.server.get_build_info(job_name, actual_build_number)
                return {
                    "success": True,
                    "message": "Build triggered successfully",
                    "build_number": actual_build_number,
                    "queue_item_number": queue_item_number,
                    "build_url": build_info["url"],
                    "git_repository": git_repository_url,
                    "git_branch": git_branch,
                }
            else:
                return {
                    "success": False,
                    "message": "Timeout waiting for build to start",
                    "queue_item_number": queue_item_number,
                }

        except Exception as e:
            return {"success": False, "message": f"Build trigger failed: {str(e)}"}

    def wait_for_build_start_by_queue(
        self, queue_item_number: int, max_wait: int = DEFAULT_QUEUE_TIMEOUT
    ) -> Optional[int]:
        """Wait for build to start via queue API"""
        print(f"⏳ Waiting for build to start (Queue item: {queue_item_number})...")

        for i in range(max_wait):
            try:
                queue_info = self.get_queue_item_info(queue_item_number)

                if not queue_info["success"]:
                    if queue_info.get("status_code") == 404:
                        print(f"⚠️  Queue item removed, build might be completed")
                        return None
                    time.sleep(2)
                    continue

                queue_data = queue_info["data"]

                if "executable" not in queue_data or queue_data["executable"] is None:
                    if i % 10 == 0:
                        print(f"  📋 Build still in queue... ({i+1}/{max_wait}s)")
                    time.sleep(1)
                    continue
                else:
                    executable = queue_data["executable"]
                    build_number = executable.get("number")

                    if build_number:
                        print(f"🚀 Build started, build number: {build_number}")
                        return build_number

            except Exception as e:
                print(f"⚠️  Error checking queue: {e}")
                time.sleep(2)

        print(f"⚠️  Timeout waiting for build to start")
        return None

    def get_queue_item_info(self, queue_item_number):
        """Get queue item information"""
        try:
            queue_api_url = (
                f"{self.jenkins_url}/queue/item/{queue_item_number}/api/json"
            )
            response = requests.get(
                queue_api_url, auth=(self.username, self.api_token), timeout=10
            )

            if response.status_code == 200:
                return {"success": True, "data": response.json()}
            elif response.status_code == 404:
                return {
                    "success": False,
                    "error": "Queue item removed",
                    "status_code": 404,
                }
            else:
                return {"success": False, "error": f"HTTP {response.status_code}"}

        except Exception as e:
            return {"success": False, "error": f"Failed to get queue info: {str(e)}"}

    def monitor_build(self, job_name, build_number, verbose=True):
        """Monitor build progress and show real-time logs"""
        print(f"\n📊 Monitoring build: {job_name} #{build_number}")
        print(f"🔗 Build link: {self.jenkins_url}/job/{job_name}/{build_number}/")
        print("-" * 80)

        last_log_position = 0
        build_complete = False
        build_result = None

        while not build_complete:
            try:
                status = self.get_build_status(job_name, build_number)

                if not status["success"]:
                    print(f"❌ Failed to get build status: {status['message']}")
                    break

                if not status["building"]:
                    build_complete = True
                    build_result = status["result"]

                try:
                    console_output = self.server.get_build_console_output(
                        job_name, build_number
                    )
                    new_output = console_output[last_log_position:]
                    if new_output:
                        self._process_console_output(new_output, verbose)
                        last_log_position = len(console_output)
                except Exception as log_e:
                    if verbose:
                        print(f"⚠️  Failed to get logs: {log_e}")

                if not build_complete:
                    time.sleep(POLL_INTERVAL)

            except Exception as e:
                print(f"❌ Error during monitoring: {e}")
                time.sleep(POLL_INTERVAL)

        print("\n" + "=" * 80)
        if build_result == "SUCCESS":
            print(f"🎉 Build completed successfully!")
        else:
            print(f"💥 Build failed! Result: {build_result}")

        return build_result == "SUCCESS"

    def get_build_status(self, job_name: str, build_number: int) -> Dict[str, Any]:
        """Get build status"""
        try:
            build_info = self.server.get_build_info(job_name, build_number)
            return {
                "success": True,
                "building": build_info.get("building", False),
                "result": build_info.get("result"),
                "duration": build_info.get("duration", 0),
                "url": build_info.get("url"),
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"Failed to get build status: {str(e)}",
            }

    def _process_console_output(self, output, verbose=False):
        """Process console output"""
        if not output.strip():
            return

        lines = output.split("\n")
        for line in lines:
            if not line.strip():
                continue

            cleaned_line = self._clean_ansi_sequences(line)

            if any(
                pattern in cleaned_line.lower()
                for pattern in [
                    "building",
                    "pushing",
                    "error:",
                    "warning:",
                    "starting",
                    "completed",
                    "success",
                ]
            ):
                print(f"📝 {cleaned_line.strip()}")
            elif verbose and any(
                pattern in cleaned_line
                for pattern in [
                    "Step ",
                    "Successfully",
                    "FROM ",
                    "RUN ",
                    "COPY ",
                    "Git",
                    "📋",
                    "🔗",
                    "✅",
                    "❌",
                    "🚀",
                ]
            ):
                print(f"   {cleaned_line.strip()}")

    def _clean_ansi_sequences(self, text):
        """Clean ANSI escape sequences"""
        import re

        ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
        return ansi_escape.sub("", text)

    def list_jobs(self) -> List[str]:
        """List all jobs"""
        try:
            jobs = self.server.get_jobs()
            return [job["name"] for job in jobs]
        except Exception as e:
            print(f"Failed to get job list: {e}")
            return []

    def trigger_and_wait(
        self,
        job_name: str,
        git_repository_url: str,
        git_branch: str = "main",
        git_credentials_id: str = "",
        app_name: str = "my-app",
        app_version: str = "1.0.0",
        build_context: str = ".",
        dockerfile_path: str = "Dockerfile",
        image_tag_strategy: str = "version-build",
        build_platforms: str = "linux/amd64",
        build_unique_id: str = "",
        enable_cache: bool = True,
        build_args: str = "",
        monitor: bool = True,
    ) -> Dict[str, Any]:
        """Trigger build and wait for completion"""
        result = self.trigger_github_build(
            job_name=job_name,
            git_repository_url=git_repository_url,
            git_branch=git_branch,
            git_credentials_id=git_credentials_id,
            app_name=app_name,
            app_version=app_version,
            build_context=build_context,
            dockerfile_path=dockerfile_path,
            image_tag_strategy=image_tag_strategy,
            build_platforms=build_platforms,
            build_unique_id=build_unique_id,
            enable_cache=enable_cache,
            build_args=build_args,
        )

        if not result["success"]:
            return result

        build_number = result.get("build_number")
        if not build_number:
            return {"success": False, "error": "Failed to get build number"}

        print(f"🔗 Build link: {result.get('build_url', 'N/A')}")

        if monitor:
            success = self.monitor_build(job_name, build_number, verbose=True)

            try:
                build_info = self.server.get_build_info(job_name, build_number)
                return {
                    "success": success,
                    "status": build_info.get("result"),
                    "message": "Build successful" if success else "Build failed",
                    "build_number": build_number,
                    "duration": build_info.get("duration", 0) / 1000,
                    "url": build_info.get("url"),
                }
            except Exception as e:
                return {"success": False, "error": f"Failed to get build info: {e}"}
        else:
            return result


def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description="Jenkins GitHub Repository Build Tool")

    # Jenkins connection
    parser.add_argument("--jenkins-url", default="http://localhost:8080")
    parser.add_argument("--username", default="admin")
    parser.add_argument("--api-token", default="11b2624bb2ab06d44424d657f387f40aeb")

    # Git repository
    parser.add_argument("--git-repo", required=True, help="GitHub repository URL")
    parser.add_argument("--git-branch", default="main")
    parser.add_argument("--git-credentials", default="")

    # Build configuration
    parser.add_argument("--job-name", default="github-build")
    parser.add_argument("--app-name", default="my-app")
    parser.add_argument("--app-version", default="1.0.0")
    parser.add_argument("--build-context", default=".")
    parser.add_argument("--dockerfile", default="Dockerfile")

    # Image configuration
    parser.add_argument(
        "--tag-strategy",
        default="version-build",
        choices=["version-build", "timestamp", "latest", "git-commit"],
    )
    parser.add_argument("--platforms", default="linux/amd64")
    parser.add_argument("--multi-arch", action="store_true")

    # Advanced options
    parser.add_argument("--build-unique-id", default="")
    parser.add_argument("--disable-cache", action="store_true")
    parser.add_argument("--build-args", default="")

    # Execution options
    parser.add_argument("--no-monitor", action="store_true")
    parser.add_argument("--list-jobs", action="store_true")
    parser.add_argument("--test-connection", action="store_true")

    return parser.parse_args()


def main():
    """Main function"""
    args = parse_arguments()

    print("🚀 Jenkins GitHub Repository Build Tool")
    print("=" * 50)

    try:
        builder = JenkinsGitHubBuilder(
            jenkins_url=args.jenkins_url,
            username=args.username,
            api_token=args.api_token,
        )

        if args.list_jobs:
            print(f"\n📋 Available Jenkins jobs:")
            jobs = builder.list_jobs()
            for i, job in enumerate(jobs, 1):
                print(f"  {i:2d}. {job}")
            return True

        if args.test_connection:
            print(f"\n✅ Jenkins connection test successful")
            return True

        platforms = args.platforms
        if args.multi_arch:
            platforms = "linux/amd64,linux/arm64"

        print(f"\n🔧 Configuration:")
        print(f"Git Repository: {args.git_repo}")
        print(f"Git Branch: {args.git_branch}")
        print(f"App Name: {args.app_name}")
        print(f"Build Platforms: {platforms}")

        result = builder.trigger_and_wait(
            job_name=args.job_name,
            git_repository_url=args.git_repo,
            git_branch=args.git_branch,
            git_credentials_id=args.git_credentials,
            app_name=args.app_name,
            app_version=args.app_version,
            build_context=args.build_context,
            dockerfile_path=args.dockerfile,
            image_tag_strategy=args.tag_strategy,
            build_platforms=platforms,
            build_unique_id=args.build_unique_id,
            enable_cache=not args.disable_cache,
            build_args=args.build_args,
            monitor=not args.no_monitor,
        )

        if result["success"]:
            print(f"\n🎉 Build completed successfully!")
            print(f"📋 Build Number: {result.get('build_number')}")
            print(f"⏱️  Duration: {result.get('duration', 0):.1f}s")
            return True
        else:
            print(f"\n❌ Build failed: {result.get('message', 'Unknown error')}")
            return False

    except Exception as e:
        print(f"\n❌ Error: {e}")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
