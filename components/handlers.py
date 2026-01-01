from src.plugin_system import BaseEventHandler, EventType
from core.state_manager import get_last_period_date
from src.common.logger import get_logger

logger = get_logger("mofox_period_plugin")

class PeriodStateUpdateHandler(BaseEventHandler):
    """周期状态更新处理器"""
    
    handler_name = "period_state_updater"
    handler_description = "定期更新月经周期状态"
    init_subscribe = [EventType.ON_START]  # 启动时初始化
    
    async def execute(self, kwargs: dict | None) -> tuple[bool, bool, str | None]:
        """初始化状态管理器"""
        try:
            # 在启动时预计算一次状态，确保提示词正确生成
            enabled = self.get_config("plugin.enabled", False)
            
            if enabled:
                # 获取或初始化上次月经日期
                last_period_date = get_last_period_date()
                logger.info(f"月经周期状态管理器初始化完成，上次月经日期: {last_period_date}")
                
        except Exception as e:
            logger.error(f"周期状态管理器初始化失败: {e}")
            
        return (True, True, None)