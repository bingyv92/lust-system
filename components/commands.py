import re
import time
from datetime import datetime
from typing import Tuple, Dict, Any, Optional, ClassVar
from src.plugin_system import PlusCommand, CommandArgs, ChatType
from core.state_manager import get_state_manager, get_last_period_date, set_last_period_date, set_anchor_day
from src.common.logger import get_logger
from core.lust_system import LustSystem

logger = get_logger("mofox_period_plugin")

class PeriodStatusCommand(PlusCommand):
    """查询当前月经周期状态命令"""
    
    command_name = "period_status"
    command_description = "查询当前月经周期状态"
    command_aliases: ClassVar[list[str]] = ["period", "月经状态", "周期状态"]
    chat_type_allow = ChatType.PRIVATE  # 只在私聊中使用
    intercept_message = True  # 拦截消息，不进入后续聊天流程
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.state_manager = get_state_manager(get_config_func=self.get_config)
        
    async def execute(self, args: CommandArgs) -> Tuple[bool, Optional[str], bool]:
        """执行状态查询"""
        try:
            # 检查插件是否启用
            if not self.get_config("plugin.enabled", False):
                await self.send_text("❌ 月经周期插件未启用")
                return True, "插件未启用", True
                
            # 计算当前状态
            state = self.state_manager.calculate_current_state()
            
            # 获取并显示上次月经日期
            last_period_date = get_last_period_date()
            
            # 生成状态报告
            report = self._generate_status_report(state, last_period_date)
            await self.send_text(report)
            
            return True, "发送周期状态报告", True
            
        except Exception as e:
            logger.error(f"查询周期状态失败: {e}")
            await self.send_text("❌ 查询状态失败，请检查配置")
            return False, f"查询失败: {e}", True
            
    def _generate_status_report(self, state: Dict[str, Any], last_period_date: str) -> str:
        """生成状态报告（使用等级系统）"""
        stage_emoji = {
            "menstrual": "🩸",
            "follicular": "🌱",
            "ovulation": "🥚",
            "luteal": "🍂"
        }
        
        emoji = stage_emoji.get(state["stage"], "❓")
        
        # 获取等级和痛经信息
        physical_level = state.get('physical_level', 3)
        psychological_level = state.get('psychological_level', 3)
        dysmenorrhea_level = state.get('dysmenorrhea_level', 0)
        
        # 痛经信息
        dysmenorrhea_info = ""
        if dysmenorrhea_level > 0:
            dysmenorrhea_info = f"\n🩹 痛经等级: {dysmenorrhea_level}/6"
        
        report = f"""
{emoji} 月经周期状态报告
━━━━━━━━━━━━━━━━━━
📅 当前阶段: {state['stage_name_cn']} (第{state.get('day_in_phase', 1)}天)
🔢 周期第 {state['current_day']} 天 / 总{state['cycle_length']} 天
📆 上次月经日期: {last_period_date}

💊 生理等级: {physical_level}/10
💭 心理等级: {psychological_level}/10{dysmenorrhea_info}

📝 状态描述:
{state['description']}
━━━━━━━━━━━━━━━━━━
💡 提示: 这些状态会影响我的回复风格和行为表现
💡 可使用 /set_period YYYY-MM-DD 修改上次月经日期
        """.strip()
        
        return report

class SetPeriodCommand(PlusCommand):
    """设置上次月经开始日期命令"""
    
    command_name = "set_period"
    command_description = "设置上次月经开始日期 (格式: /set_period YYYY-MM-DD)"
    command_aliases: ClassVar[list[str]] = ["设置月经日期"]
    chat_type_allow = ChatType.PRIVATE  # 只在私聊中使用
    intercept_message = True  # 拦截消息，不进入后续聊天流程
    
    async def execute(self, args: CommandArgs) -> Tuple[bool, Optional[str], bool]:
        """执行设置月经日期"""
        try:
            # 从参数中获取日期
            if args.is_empty():
                await self.send_text("❌ 格式错误，请使用: /set_period YYYY-MM-DD")
                return True, "格式错误", True
            
            date_str = args.get_first()
            
            # 验证日期格式
            if not re.match(r'^\d{4}-\d{2}-\d{2}$', date_str):
                await self.send_text("❌ 日期格式无效，请使用 YYYY-MM-DD 格式")
                return True, "日期格式无效", True
            
            if set_last_period_date(date_str):
                await self.send_text(f"✅ 上次月经开始日期已更新为: {date_str}")
                return True, f"设置月经日期: {date_str}", True
            else:
                await self.send_text("❌ 日期格式无效，请使用 YYYY-MM-DD 格式")
                return True, "日期格式无效", True
                
        except Exception as e:
            logger.error(f"设置月经日期失败: {e}")
            await self.send_text("❌ 设置失败，请检查输入")
            return False, f"设置失败: {e}", True


class SetAnchorDayCommand(PlusCommand):
    """设置锚点日期命令（双周期锚定模型）"""
    
    command_name = "set_anchor"
    command_description = "设置月经周期锚点日期 (格式: /set_anchor 1-31)"
    command_aliases: ClassVar[list[str]] = ["设置锚点", "锚点日期"]
    chat_type_allow = ChatType.PRIVATE  # 只在私聊中使用
    intercept_message = True  # 拦截消息，不进入后续聊天流程
    
    async def execute(self, args: CommandArgs) -> Tuple[bool, Optional[str], bool]:
        """执行设置锚点日期"""
        try:
            # 从参数中获取日期
            if args.is_empty():
                await self.send_text("❌ 格式错误，请使用: /set_anchor 1-31 (例如: /set_anchor 15)")
                return True, "格式错误", True
            
            day_str = args.get_first()
            
            # 验证是否为整数
            try:
                day = int(day_str)
            except ValueError:
                await self.send_text("❌ 日期必须是1-31之间的整数")
                return True, "日期格式无效", True
            
            if set_anchor_day(day, force_regenerate=True):
                await self.send_text(f"""✅ 锚点日期已更新为每月 {day} 号
                
🔄 双周期数据已重新生成
💡 请使用 /月经状态 查看新的周期信息""")
                return True, f"设置锚点日期: {day}", True
            else:
                await self.send_text("❌ 日期无效，请使用1-31之间的整数")
                return True, "日期无效", True
                
        except Exception as e:
            logger.error(f"设置锚点日期失败: {e}")
            await self.send_text("❌ 设置失败，请检查输入")
            return False, f"设置失败: {e}", True


class RegenerateCycleCommand(PlusCommand):
    """强制重新生成双周期命令"""
    
    command_name = "regenerate_cycle"
    command_description = "强制重新生成双周期数据"
    command_aliases: ClassVar[list[str]] = ["重新生成周期", "刷新周期"]
    chat_type_allow = ChatType.PRIVATE  # 只在私聊中使用
    intercept_message = True  # 拦截消息，不进入后续聊天流程
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.state_manager = get_state_manager(get_config_func=self.get_config)
        
    async def execute(self, args: CommandArgs) -> Tuple[bool, Optional[str], bool]:
        """执行强制重新生成"""
        try:
            # 强制重新生成双周期
            self.state_manager.force_regenerate_cycle()
            
            # 获取新的周期状态
            state = self.state_manager.calculate_current_state(force_recalc=True)
            
            await self.send_text(f"""✅ 双周期数据已重新生成
            
📅 新周期信息:
• 当前阶段: {state['stage_name_cn']} (第{state.get('day_in_phase', 1)}天)
• 周期第 {state['current_day']} 天 / 总{state['cycle_length']} 天
• 周期编号: 第{state.get('cycle_num', 1)}周期

💡 请使用 /月经状态 查看完整信息""")
            
            return True, "强制重新生成双周期", True
            
        except Exception as e:
            logger.error(f"重新生成双周期失败: {e}")
            await self.send_text("❌ 重新生成失败，请稍后重试")
            return False, f"重新生成失败: {e}", True
class LustStatusCommand(PlusCommand):
    """查询淫乱度状态命令"""
    
    command_name = "lust_status"
    command_description = "查询当前淫乱度、高潮值、阶段等信息"
    command_aliases: ClassVar[list[str]] = ["lust", "淫乱度状态", "高潮值"]
    chat_type_allow = ChatType.PRIVATE  # 只在私聊中使用
    intercept_message = True  # 拦截消息，不进入后续聊天流程
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.lust_system = LustSystem(self.get_config)
        
    async def execute(self, args: CommandArgs) -> Tuple[bool, Optional[str], bool]:
        """执行状态查询"""
        try:
            # 1. 检查淫乱度系统是否启用
            if not self.get_config("lust_system.enabled", False):
                await self.send_text("❌ 淫乱度系统未启用")
                return True, "系统未启用", True
            
            # 2. 获取用户ID
            user_id = self._get_user_id()
            if not user_id:
                await self.send_text("❌ 无法识别用户")
                return True, "用户ID缺失", True
            
            # 3. 获取月经周期状态和淫乱度
            period_state, lust_level = self._get_period_and_lust()
            if not period_state:
                await self.send_text("❌ 无法获取月经周期状态")
                return False, "周期状态获取失败", True
            
            # 4. 获取用户淫乱度数据（只读，不修改）
            data = self._get_user_data_for_display(str(user_id), period_state)
            
            # 5. 生成并发送报告
            report = self._generate_status_report(data, lust_level, period_state)
            await self.send_text(report)
            
            return True, "发送淫乱度状态报告", True
            
        except Exception as e:
            logger.error(f"查询淫乱度状态失败: {e}", exc_info=True)
            await self.send_text(f"❌ 查询失败: {str(e)}")
            return False, f"查询失败: {e}", True
    
    def _get_user_id(self) -> Optional[str]:
        """获取人格ID（淫乱度作用在AI人格上，不是用户上）
        
        从storage读取活跃的person_id，而不是自己计算。
        这确保命令系统和消息处理器使用完全相同的person_id。
        """
        try:
            from src.plugin_system.apis import storage_api
            import time
            
            if not self.message or not self.message.user_info:
                return None
            
            # 从storage读取最近活跃的person_id
            plugin_storage = storage_api.get_local_storage("mofox_period_plugin")
            person_id = plugin_storage.get("active_person_id", None)
            last_active_time = plugin_storage.get("active_person_timestamp", 0)
            
            # 检查是否有效（60秒内活跃过）
            if person_id and (time.time() - last_active_time) < 60:
                return person_id
            else:
                logger.warning(f"[淫乱度查询] 未找到活跃的person_id（上次活跃: {time.time() - last_active_time:.0f}秒前）")
                return None
                
        except Exception as e:
            logger.error(f"获取person_id失败: {e}")
            return None
    
    def _get_period_and_lust(self) -> Tuple[Optional[Dict[str, Any]], float]:
        """获取月经周期状态和淫乱度"""
        try:
            state_manager = get_state_manager(get_config_func=self.get_config)
            period_state = state_manager.calculate_current_state()
            lust_level = self.lust_system.calculate_lust_level(period_state)
            return period_state, lust_level
        except Exception as e:
            logger.error(f"获取周期状态失败: {e}", exc_info=True)
            return None, 0.0
    
    def _get_user_data_for_display(self, user_id: str, period_state: Dict[str, Any]) -> Dict[str, Any]:
        """获取用于显示的用户数据（只读）"""
        data = self.lust_system.get_user_data_readonly(user_id, period_state)
        
        # 调试日志：显示查询到的关键数据
        logger.info(f"[查询命令] 用户{user_id}: "
                   f"淫乱度={data.get('lust_level', 0):.2f}, "
                   f"高潮值={data.get('orgasm_value', 0):.1f}, "
                   f"剩余={data.get('remaining_orgasms', 0)}/{data.get('max_orgasms', 0)}, "
                   f"阶段={data.get('current_stage', 'unknown')}")
        
        return data
    
    def _generate_status_report(self, data: Dict[str, Any], lust_level: float, period_state: Dict[str, Any]) -> str:
        """生成淫乱度状态报告"""
        stage_emoji = {
            "被动未开始": "😴",
            "主动未开始": "😊",
            "前戏": "😳",
            "正戏": "😍",
            "高潮": "🥵",
            "高潮余韵期": "😌",
            "体力恢复期": "😪",
            "冷却": "🥶"
        }
        
        current_stage = data.get("current_stage", "被动未开始")
        emoji = stage_emoji.get(current_stage, "❓")
        
        # 格式化时间
        last_updated = self._format_time(data.get("last_updated", 0))
        
        # 格式化高潮值（限制小数位）
        orgasm_value = data.get("orgasm_value", 0)
        orgasm_value_str = f"{orgasm_value:.1f}" if orgasm_value < 100 else f"{orgasm_value:.0f}"
        
        report = f"""
{emoji} 淫乱度状态报告
━━━━━━━━━━━━━━━━━━
📊 淫乱度: {lust_level:.2f}/1.0
🔥 高潮值: {orgasm_value_str}
🎯 当前阶段: {current_stage}
💦 剩余高潮次数: {data.get('remaining_orgasms', 0)} / {data.get('max_orgasms', 0)}
⏱️ 上次更新: {last_updated}

📈 连续低评分次数: {data.get('consecutive_low_scores', 0)}
🌀 衰减倍率: {data.get('termination_decay_multiplier', 1.0):.1f}x

📅 月经周期阶段: {period_state.get('stage_name_cn', '未知')}
📆 周期第 {period_state.get('current_day', 1)} 天
━━━━━━━━━━━━━━━━━━
💡 提示: 淫乱度影响性欲表现，高潮值累积可触发高潮
💡 可使用 /lust_end 主动结束当前会话
        """.strip()
        
        return report
    
    def _format_time(self, timestamp: float) -> str:
        """格式化时间戳"""
        if not timestamp or timestamp == 0:
            return "从未"
        try:
            dt = datetime.fromtimestamp(timestamp)
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except (ValueError, OSError):
            return "无效时间"


class LustEndCommand(PlusCommand):
    """主动结束淫乱度会话命令"""
    
    command_name = "lust_end"
    command_description = "主动结束当前淫乱度会话，重置高潮值"
    command_aliases: ClassVar[list[str]] = ["结束淫乱度"]
    chat_type_allow = ChatType.PRIVATE  # 只在私聊中使用
    intercept_message = True  # 拦截消息，不进入后续聊天流程
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.lust_system = LustSystem(self.get_config)
        
    async def execute(self, args: CommandArgs) -> Tuple[bool, Optional[str], bool]:
        """执行结束会话"""
        try:
            # 检查淫乱度系统是否启用
            enabled = self.get_config("lust_system.enabled", False)
            if not enabled:
                await self.send_text("❌ 淫乱度系统未启用")
                return True, "系统未启用", True
            
            # 获取人格ID（从storage读取，确保和消息处理器使用相同ID）
            try:
                from src.plugin_system.apis import storage_api
                import time
                
                if not self.message.user_info:
                    await self.send_text("❌ 无法识别用户")
                    return True, "用户信息缺失", True
                
                # 从storage读取最近活跃的person_id
                plugin_storage = storage_api.get_local_storage("mofox_period_plugin")
                person_id = plugin_storage.get("active_person_id", None)
                last_active_time = plugin_storage.get("active_person_timestamp", 0)
                
                # 检查是否有效（60秒内活跃过）
                if not person_id or (time.time() - last_active_time) >= 60:
                    await self.send_text("❌ 请先发送消息激活淫乱度系统")
                    return True, "person_id未激活", True
                    
            except Exception as e:
                logger.error(f"获取person_id失败: {e}")
                await self.send_text("❌ 系统错误")
                return True, "获取person_id失败", True
            
            # 获取当前月经周期状态
            try:
                state_manager = get_state_manager(get_config_func=self.get_config)
                period_state = state_manager.calculate_current_state()
            except Exception as e:
                logger.warning(f"获取周期状态失败，使用默认值: {e}")
                period_state = None
            
            # 重置会话（传递period_state以正确计算淫乱度）
            self.lust_system.reset_session(person_id, period_state)
            await self.send_text("✅ 淫乱度会话已重置，高潮值、阶段、连续低评分计数等已清零。")
            
            return True, "重置淫乱度会话", True
            
        except Exception as e:
            logger.error(f"结束淫乱度会话失败: {e}")
            await self.send_text("❌ 重置失败，请稍后重试")
            return False, f"重置失败: {e}", True