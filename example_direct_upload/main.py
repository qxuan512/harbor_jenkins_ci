#!/usr/bin/env python3
"""
IoT 驱动示例主程序
这是一个简单的示例，展示如何构建IoT驱动程序
"""

import os
import sys
import time
import json
import logging
from datetime import datetime

# 配置日志
def setup_logging():
    """配置日志记录"""
    log_level = os.getenv('LOG_LEVEL', 'INFO')
    logging.basicConfig(
        level=getattr(logging, log_level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('/var/log/iot-driver/driver.log'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    return logging.getLogger('iot-driver')

class IoTDriver:
    """IoT 驱动主类"""
    
    def __init__(self):
        self.logger = setup_logging()
        self.driver_name = os.getenv('IOT_DRIVER_NAME', 'unknown-driver')
        self.driver_version = os.getenv('IOT_DRIVER_VERSION', '1.0.0')
        self.running = False
        
    def initialize(self):
        """初始化驱动"""
        self.logger.info(f"初始化 IoT 驱动: {self.driver_name} v{self.driver_version}")
        
        # 模拟设备连接初始化
        self.logger.info("正在连接到IoT设备...")
        time.sleep(2)  # 模拟连接延迟
        self.logger.info("✅ 设备连接成功")
        
        # 加载配置
        self.load_config()
        
    def load_config(self):
        """加载配置文件"""
        config_file = '/app/config.json'
        if os.path.exists(config_file):
            try:
                with open(config_file, 'r') as f:
                    config = json.load(f)
                self.logger.info(f"配置加载成功: {config}")
            except Exception as e:
                self.logger.warning(f"配置加载失败: {e}")
        else:
            self.logger.info("未找到配置文件，使用默认配置")
    
    def collect_data(self):
        """数据采集主循环"""
        self.logger.info("开始数据采集...")
        self.running = True
        
        while self.running:
            try:
                # 模拟数据采集
                timestamp = datetime.now().isoformat()
                data = {
                    'timestamp': timestamp,
                    'driver': self.driver_name,
                    'temperature': 25.5 + (time.time() % 10),  # 模拟温度数据
                    'humidity': 65.0 + (time.time() % 5),      # 模拟湿度数据
                    'status': 'active'
                }
                
                # 输出数据 (在实际应用中，这里会发送到IoT平台)
                self.logger.info(f"📊 采集数据: {json.dumps(data, indent=2)}")
                
                # 等待下次采集
                time.sleep(10)  # 每10秒采集一次
                
            except KeyboardInterrupt:
                self.logger.info("收到停止信号")
                self.running = False
            except Exception as e:
                self.logger.error(f"数据采集错误: {e}")
                time.sleep(5)  # 错误后等待5秒重试
    
    def stop(self):
        """停止驱动"""
        self.logger.info("正在停止IoT驱动...")
        self.running = False
        self.logger.info("IoT驱动已停止")

def main():
    """主函数"""
    print("🚀 启动 IoT 驱动程序")
    
    # 创建驱动实例
    driver = IoTDriver()
    
    try:
        # 初始化
        driver.initialize()
        
        # 开始数据采集
        driver.collect_data()
        
    except Exception as e:
        driver.logger.error(f"驱动运行错误: {e}")
        sys.exit(1)
    finally:
        driver.stop()

if __name__ == "__main__":
    main() 