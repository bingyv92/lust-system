import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from typing import List, Tuple, Type, Dict, Any, Optional
from datetime import datetime, timedelta
from src.plugin_system import (
    BasePlugin, register_plugin, ComponentInfo, ConfigField,
    BasePrompt, PlusCommand, ChatType
)
from src.plugin_system import BaseEventHandler, EventType
from src.plugin_system.base.base_event import HandlerResult
from src.plugin_system.apis import storage_api
from src.common.logger import get_logger

# 导入新模块中的类
from core.state_manager import PeriodStateManager
from components.prompts import PeriodStatePrompt
from components.commands import PeriodStatusCommand, SetPeriodCommand, LustStatusCommand, LustEndCommand
from components.handlers import PeriodStateUpdateHandler
from components.lust_scoring_handler import LustScoringHandler
from config_schema import CONFIG_SCHEMA

logger = get_logger("mofox_period_plugin")

# 获取插件的本地存储实例
plugin_storage = storage_api.get_local_storage("mofox_period_plugin")

def get_last_period_date() -> str:
    """获取上次月经开始日期，如果没有设置过则设为安装当天"""
    last_period_date = plugin_storage.get("last_period_date", None)
    if last_period_date is None:
        # 首次使用，设置为今天
        today_str = datetime.now().strftime("%Y-%m-%d")
        plugin_storage.set("last_period_date", today_str)
        logger.info(f"首次安装，设置上次月经开始日期为: {today_str}")
        return today_str
    return last_period_date

def set_last_period_date(date_str: str) -> bool:
    """设置上次月经开始日期"""
    try:
        # 验证日期格式
        datetime.strptime(date_str, "%Y-%m-%d")
        plugin_storage.set("last_period_date", date_str)
        logger.info(f"更新上次月经开始日期为: {date_str}")
        return True
    except ValueError:
        logger.error(f"无效的日期格式: {date_str}")
        return False

@register_plugin
class MofoxPeriodPlugin(BasePlugin):
    """月经周期状态插件"""
    
    plugin_name = "mofox_period_plugin"
    enable_plugin = True
    dependencies = []
    python_dependencies = []
    config_file_name = "config.toml"
    
    # 配置Schema定义 - 从 config_schema.py 导入
    config_schema = CONFIG_SCHEMA
    
    def get_plugin_components(self) -> List[Tuple[ComponentInfo, Type]]:
        """注册插件组件"""
        components = []
        
        # 总是注册状态更新处理器
        components.append((PeriodStateUpdateHandler.get_handler_info(), PeriodStateUpdateHandler))
        
        # 根据配置决定是否注册其他组件
        if self.get_config("plugin.enabled", False):
            components.append((PeriodStatePrompt.get_prompt_info(), PeriodStatePrompt))
            components.append((PeriodStatusCommand.get_plus_command_info(), PeriodStatusCommand))
            components.append((SetPeriodCommand.get_plus_command_info(), SetPeriodCommand))
            # 如果淫乱度系统启用，注册相关组件
            if self.get_config("lust_system.enabled", True):
                components.append((LustScoringHandler.get_handler_info(), LustScoringHandler))
                components.append((LustStatusCommand.get_plus_command_info(), LustStatusCommand))
                components.append((LustEndCommand.get_plus_command_info(), LustEndCommand))
            
        return components
    
    def __init__(self, *args, **kwargs):
        """插件初始化，增强错误处理和配置兼容"""
        super().__init__(*args, **kwargs)
        self._ensure_config_compatibility()
    
    def _ensure_config_compatibility(self):
        """确保配置向后兼容"""
        try:
            # 检查并升级配置版本
            current_version = self.get_config("plugin.config_version", "1.0.0")
            if current_version == "1.0.0":
                logger.info("检测到旧版本配置，正在升级...")
                
                # 设置新版本号
                self.set_config("plugin.config_version", "1.1.0")
                
                # 确保KFC集成配置存在
                if not self.has_config("kfc_integration.enabled"):
                    self.set_config("kfc_integration.enabled", True)
                    logger.info("添加KFC集成配置")
                
                if not self.has_config("kfc_integration.mode"):
                    self.set_config("kfc_integration.mode", "unified")
                    logger.info("添加KFC模式配置")
                
                if not self.has_config("kfc_integration.priority"):
                    self.set_config("kfc_integration.priority", 100)
                    logger.info("添加KFC优先级配置")
                
                # 确保其他新配置项存在
                if not self.has_config("plugin.debug_mode"):
                    self.set_config("plugin.debug_mode", False)
                    logger.info("添加调试模式配置")
                
                if not self.has_config("cycle.auto_detect"):
                    self.set_config("cycle.auto_detect", True)
                    logger.info("添加自动检测配置")
                
                if not self.has_config("backup.auto_backup"):
                    self.set_config("backup.auto_backup", True)
                    logger.info("添加自动备份配置")
                
                if not self.has_config("backup.backup_days"):
                    self.set_config("backup.backup_days", 30)
                    logger.info("添加备份天数配置")
                
                logger.info("配置升级完成")
            
            # 验证关键配置项
            self._validate_critical_configs()
            
        except Exception as e:
            logger.error(f"配置兼容性检查失败: {e}")
    
    def _validate_critical_configs(self):
        """验证关键配置项的有效性"""
        try:
            # 验证周期长度
            cycle_length = self.get_config("cycle.cycle_length", 28)
            if not isinstance(cycle_length, int) or cycle_length < 20 or cycle_length > 40:
                logger.warning(f"周期长度配置无效: {cycle_length}，使用默认值28")
                self.set_config("cycle.cycle_length", 28)
            
            # 验证影响强度值
            for stage in ["menstrual", "follicular", "ovulation", "luteal"]:
                for impact_type in ["physical", "psychological"]:
                    key = f"impacts.{stage}_{impact_type}"
                    value = self.get_config(key, 0.5)
                    if not isinstance(value, (int, float)) or value < 0 or value > 1:
                        logger.warning(f"影响强度配置无效: {key}={value}，使用默认值0.5")
                        self.set_config(key, 0.5)
            
            # 验证KFC模式
            kfc_mode = self.get_config("kfc_integration.mode", "unified")
            if kfc_mode not in ["unified", "split"]:
                logger.warning(f"KFC模式配置无效: {kfc_mode}，使用默认值unified")
                self.set_config("kfc_integration.mode", "unified")
            
            # 验证优先级
            priority = self.get_config("kfc_integration.priority", 100)
            if not isinstance(priority, int) or priority < 0 or priority > 1000:
                logger.warning(f"KFC优先级配置无效: {priority}，使用默认值100")
                self.set_config("kfc_integration.priority", 100)
            
            logger.info("关键配置验证完成")
            
        except Exception as e:
            logger.error(f"配置验证失败: {e}")