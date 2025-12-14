import time
from typing import Dict, Any
from src.plugin_system import BaseEventHandler, EventType
from src.plugin_system.base.base_event import HandlerResult
from src.plugin_system.apis.permission_api import permission_api
from src.common.logger import get_logger
from core.lust_system import LustSystem

logger = get_logger("mofox_period_plugin")

class LustScoringHandler(BaseEventHandler):
    """淫乱度评分处理器 - 仅对master用户的私聊消息进行LLM评分"""

    handler_name = "lust_scoring_handler"
    handler_description = "对master用户的私聊消息进行淫乱度评分，更新高潮值"
    init_subscribe = [EventType.ON_MESSAGE]
    weight = 50

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.lust_system = LustSystem(self.get_config)

    async def execute(self, params: Dict[str, Any]) -> HandlerResult:
        """处理消息事件"""
        try:
            # 1. 检查系统是否启用
            if not self.get_config("lust_system.enabled", True):
                return HandlerResult(success=True, continue_process=True)

            # 2. 获取消息对象
            message = params.get("message")
            if not message:
                return HandlerResult(success=True, continue_process=True)

            # 3. 判断是否为私聊（group_id为空或None表示私聊）
            is_private = not (hasattr(message, 'group_id') and message.group_id)
            if not is_private:
                return HandlerResult(success=True, continue_process=True)

            # 4. 获取用户信息
            if not message.user_info:
                return HandlerResult(success=True, continue_process=True)
            
            user_id = str(message.user_info.user_id)
            platform = message.chat_info.platform if message.chat_info else "qq"

            # 5. 检查master权限
            has_permission = await permission_api.check_permission(
                platform, 
                user_id, 
                "plugin.mofox_period.lust_system"
            )
            if not has_permission:
                return HandlerResult(success=True, continue_process=True)

            # 6. 获取消息文本
            text = (message.processed_plain_text or "").strip()
            if not text:
                return HandlerResult(success=True, continue_process=True)

            # 7. 获取月经周期状态并计算淫乱度
            from core.state_manager import PeriodStateManager
            from src.plugin_system.apis import person_api
            
            state_manager = PeriodStateManager()
            cycle_length = self.get_config("cycle.cycle_length", 28)
            period_state = state_manager.calculate_current_state(cycle_length)
            lust_level = self.lust_system.calculate_lust_level(period_state)

            # 8. 生成person_id作为user_key
            person_id = person_api.get_person_id(platform, int(user_id))

            # 9. LLM评分（使用淫乱度加成）
            score = await self.lust_system.score_message_with_llm(text, lust_level)
            
            # 10. 更新淫乱度数据（确保淫乱度和最大高潮次数同步）
            self.lust_system.update_lust_from_period_state(person_id, period_state)
            
            # 11. 处理评分，更新高潮值
            user_data = self.lust_system.process_score(person_id, score)
            
            # 12. 记录当前活跃用户（供Prompt使用）
            from src.plugin_system.apis import storage_api
            plugin_storage = storage_api.get_local_storage("mofox_period_plugin")
            plugin_storage.set("active_person_id", person_id)
            plugin_storage.set("active_person_timestamp", time.time())

            # 13. 输出调试信息
            if self.get_config("plugin.debug_mode", False):
                logger.info(
                    f"[淫乱度评分] person_id={person_id}, 评分={score:.1f}, "
                    f"淫乱度={lust_level:.2f}, "
                    f"高潮值={user_data.get('orgasm_value', 0):.1f}, "
                    f"阶段={user_data.get('current_stage', '未知')}, "
                    f"剩余={user_data.get('remaining_orgasms', 0)}/{user_data.get('max_orgasms', 0)}"
                )

            return HandlerResult(success=True, continue_process=True)

        except Exception as e:
            logger.error(f"[淫乱度Handler] 执行失败: {e}", exc_info=True)
            return HandlerResult(success=False, continue_process=True, message=str(e))