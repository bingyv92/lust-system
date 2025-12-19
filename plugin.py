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
from components.commands import (
    PeriodStatusCommand, SetPeriodCommand, SetAnchorDayCommand,
    RegenerateCycleCommand, LustStatusCommand, LustEndCommand
)
from components.handlers import PeriodStateUpdateHandler
from components.lust_scoring_handler import LustScoringHandler
from components.message_relief_handler import MessageReliefHandler
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
    config_schema: Dict[str, Any] = CONFIG_SCHEMA  # type: ignore
    
    def get_plugin_components(self):
        """注册插件组件"""
        components = []
        
        # 总是注册状态更新处理器
        components.append((PeriodStateUpdateHandler.get_handler_info(), PeriodStateUpdateHandler))
        
        # 根据配置决定是否注册其他组件
        if self.get_config("plugin.enabled", False):
            # 如果启用LLM缓解功能，注册消息缓解处理器
            if self.get_config("dysmenorrhea.enable_llm_relief", False):
                components.append((MessageReliefHandler.get_handler_info(), MessageReliefHandler))
            
            components.append((PeriodStatePrompt.get_prompt_info(), PeriodStatePrompt))
            components.append((PeriodStatusCommand.get_plus_command_info(), PeriodStatusCommand))
            components.append((SetPeriodCommand.get_plus_command_info(), SetPeriodCommand))
            components.append((SetAnchorDayCommand.get_plus_command_info(), SetAnchorDayCommand))
            components.append((RegenerateCycleCommand.get_plus_command_info(), RegenerateCycleCommand))
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
    
    async def on_plugin_loaded(self):
        """插件加载完成后的回调"""
        try:
            logger.info("插件已加载，开始数据完整性检查...")
            
            # 修复旧数据
            from core.lust_system import LustSystem
            from core.data_fixer import fix_all_lust_data
            
            lust_system = LustSystem(self.get_config)
            fix_all_lust_data(lust_system)
            
        except Exception as e:
            logger.error(f"插件加载后处理失败: {e}", exc_info=True)
    
    def _ensure_config_compatibility(self):
        """确保配置向后兼容"""
        try:
            # 配置会通过 config_schema 和 config.toml 自动加载
            # BasePlugin 不支持运行时修改配置，只能读取
            logger.info("配置兼容性检查完成")
            
            # 验证关键配置项
            self._validate_critical_configs()
            
        except Exception as e:
            logger.error(f"配置兼容性检查失败: {e}")
    
    def _validate_critical_configs(self):
        """验证关键配置项的有效性"""
        try:
            # 验证锚点日期（双周期锚定模型）
            anchor_day = self.get_config("cycle.anchor_day", 15)
            if not isinstance(anchor_day, int) or anchor_day < 1 or anchor_day > 31:
                logger.warning(f"锚点日期配置无效: {anchor_day}，请在config.toml中修改")
            
            # 验证等级配置值（1-10整数）
            for stage in ["menstrual", "follicular", "ovulation", "luteal"]:
                for level_type in ["physical", "psychological"]:
                    key = f"levels.{stage}_{level_type}"
                    value = self.get_config(key, 5)
                    if not isinstance(value, int) or value < 1 or value > 10:
                        logger.warning(f"等级配置无效: {key}={value}，请在config.toml中修改")
            
            # 验证KFC模式
            kfc_mode = self.get_config("kfc_integration.mode", "unified")
            if kfc_mode not in ["unified", "split"]:
                logger.warning(f"KFC模式配置无效: {kfc_mode}，请在config.toml中修改")
            
            # 验证优先级
            priority = self.get_config("kfc_integration.priority", 100)
            if not isinstance(priority, int) or priority < 0 or priority > 1000:
                logger.warning(f"KFC优先级配置无效: {priority}，请在config.toml中修改")
            
            logger.info("关键配置验证完成")
            
        except Exception as e:
            logger.error(f"配置验证失败: {e}")