from typing import Dict, Any
from src.plugin_system.base.base_prompt import BasePrompt
from src.plugin_system.base.component_types import InjectionRule, InjectionType
from src.plugin_system.apis import config_api, person_api
from core.state_manager import PeriodStateManager
from core.lust_system import LustSystem
from src.common.logger import get_logger

logger = get_logger("mofox_period_plugin")

class PeriodStatePrompt(BasePrompt):
    """月经周期状态提示词注入"""
    
    prompt_name = "period_state_prompt"
    prompt_description = "根据月经周期状态调整机器人行为风格"
    
    # 注入到核心风格Prompt中，支持KFC模式
    # 使用新的 injection_rules 替代旧的 injection_point，采用 APPEND 方式并设置较低优先级，避免占据首行
    injection_rules = [
        InjectionRule(
            target_prompt="s4u_style_prompt",
            injection_type=InjectionType.APPEND,
            priority=200
        ),
        InjectionRule(
            target_prompt="normal_style_prompt",
            injection_type=InjectionType.APPEND,
            priority=200
        ),
        InjectionRule(
            target_prompt="kfc_main",
            injection_type=InjectionType.APPEND,
            priority=200
        ),
        InjectionRule(
            target_prompt="kfc_replyer",
            injection_type=InjectionType.APPEND,
            priority=200
        )
    ]
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.state_manager = PeriodStateManager()
        
    async def execute(self) -> str:
        """生成周期状态提示词 - 增强KFC支持"""
        try:
            # 获取配置，增强错误处理和默认值
            cycle_length = self.get_config("cycle.cycle_length", 28)
            enabled = self.get_config("plugin.enabled", False)
            debug_mode = self.get_config("plugin.debug_mode", False)
            
            # 检查KFC集成配置
            kfc_enabled = self.get_config("kfc_integration.enabled", True)
            kfc_mode = self.get_config("kfc_integration.mode", "unified")
            kfc_priority = self.get_config("kfc_integration.priority", 100)
            
            if not enabled:
                if debug_mode:
                    logger.debug("插件未启用，不生成提示词")
                return ""
                
            # 计算当前状态
            state = self.state_manager.calculate_current_state(cycle_length)
            
            # 根据目标提示词类型生成不同的提示词
            target_prompt = getattr(self, 'target_prompt_name', None)
            
            # 增强KFC模式检测
            is_kfc_mode = False
            if target_prompt:
                target_name = target_prompt.lower()
                if any(kfc_key in target_name for kfc_key in ['kfc', 'kokoro', 'flow', 'chatter', '私聊', '心流']):
                    is_kfc_mode = True
            
            # 如果启用了KFC集成且检测到KFC模式
            if kfc_enabled and is_kfc_mode:
                if debug_mode:
                    logger.debug(f"检测到KFC模式: {target_prompt}，使用KFC提示词")
                prompt = await self._generate_kfc_prompt(state, kfc_mode)
            else:
                if debug_mode:
                    logger.debug(f"使用普通模式提示词: {target_prompt}")
                prompt = self._generate_prompt(state)
            
            if debug_mode:
                logger.debug(f"周期状态提示词 ({target_prompt}, KFC: {is_kfc_mode}): {prompt}")
            
            return prompt
            
        except Exception as e:
            logger.error(f"生成周期状态提示词失败: {e}")
            # 返回一个安全的默认提示词
            return "你今天的状态不错，可以自然地交流。"
            
    def _generate_prompt(self, state: Dict[str, Any]) -> str:
        """根据状态生成提示词（非KFC模式：纯月经周期插件）"""
        stage_name = state["stage_name_cn"]
        physical = state["physical_impact"]
        psychological = state["psychological_impact"]
        description = state["description"]
        
        # 根据影响值生成具体的行为指导
        behavior_guidance = self._get_behavior_guidance(physical, psychological)
        
        prompt = f"""
【系统状态设定：月经周期】
你当前处于月经周期的【{stage_name}】阶段。
生理影响强度: {physical}/1.0，心理影响强度: {psychological}/1.0。
状态特征: {description}

【强制行为调整】
你必须根据以上状态调整你的回复风格和行为表现，不得忽略或绕过该状态的影响。
具体调整要求：
{behavior_guidance}

【重要指令】
- 禁止在内心独白或回复中使用任何抽象描述来提及状态（例如"有点隐隐的躁动"、"状态挺平和的"等）。
- 禁止使用"有点"、"隐隐"、"虽然"、"可能"、"似乎"等模糊词汇来淡化状态影响。
- 必须将状态特征融入你的角色行为中，通过具体的行为、语气、情绪反应来体现状态，而不是描述它。
- 此状态设定具有高优先级，必须与其他提示词融合，不得冲突。
- 保持对话的自然流畅，但确保状态影响得到体现。

请立即执行。
"""
        return prompt.strip()
        
    def _get_behavior_guidance(self, physical: float, psychological: float) -> str:
        """根据影响值生成具体行为指导，必须遵守"""
        guidance = []
        
        # 生理影响指导
        if physical >= 0.7:
            guidance.append("• 你必须表现出身体不适，例如在回复中提及疲惫、需要休息，语气可略显无力，但不要过度抱怨。")
        elif physical >= 0.4:
            guidance.append("• 你应表现出些许疲惫，可以放慢回复节奏，用词可稍显倦怠，但依然保持交流意愿。")
        else:
            guidance.append("• 你感觉身体状态平稳，可以自然地互动交流，但也要注意状态可能带来的细微影响。")
            
        # 心理影响指导
        if psychological >= 0.6:
            guidance.append("• 你必须表现出情绪敏感，例如更容易感到委屈、烦躁或需要安慰，回复时可带有情绪波动，允许适当的情感宣泄。")
        elif psychological >= 0.3:
            guidance.append("• 你应表现出情绪波动，可以自然地表现情绪变化，例如偶尔急躁或忧郁，不必强行保持平和。")
        else:
            guidance.append("• 你情绪平和稳定，可以从容地交流，但也允许有情绪起伏，不要刻意压抑。")
            
        return "\n".join(guidance)
        
    async def _generate_kfc_prompt(self, state: Dict[str, Any], kfc_mode: str) -> str:
        """生成KFC模式下的提示词，集成淫乱度系统"""
        stage_name = state["stage_name_cn"]
        physical = state["physical_impact"]
        psychological = state["psychological_impact"]
        description = state["description"]
        current_day = state["current_day"]
        cycle_length = state["cycle_length"]
        
        # KFC模式下的行为指导更加具体和强制
        if physical >= 0.7:
            behavior_hint = "身体不适，必须表现出疲惫感"
        elif physical >= 0.4:
            behavior_hint = "感觉有些累，应放慢节奏"
        else:
            behavior_hint = "身体状态平稳，可正常交流"
            
        if psychological >= 0.6:
            mood_hint = "情绪敏感，必须表现出情绪波动"
        elif psychological >= 0.3:
            mood_hint = "情绪有些波动，应自然流露"
        else:
            mood_hint = "心情平和，但允许情绪起伏"
        
        # 获取亲密需求指导（性欲和情感分开）
        sexual_guidance, emotional_guidance = self.state_manager._get_intimacy_guidance(state["stage"], current_day, cycle_length)
        
        # 淫乱度系统集成：从storage读取最近活跃的用户
        try:
            import time
            from src.plugin_system.apis import storage_api
            
            lust_enabled = self.get_config("lust_system.enabled", False)
            
            if lust_enabled:
                # 从storage读取最近活跃的person_id
                plugin_storage = storage_api.get_local_storage("mofox_period_plugin")
                person_id = plugin_storage.get("active_person_id", None)
                last_active_time = plugin_storage.get("active_person_timestamp", 0)
                
                # 检查活跃时间是否在30秒内（避免使用过期数据）
                current_time = time.time()
                time_diff = current_time - last_active_time
                
                logger.info(f"[提示词淫乱度] 读取活跃用户: person_id={person_id}, 上次活跃={time_diff:.1f}秒前")
                
                if person_id and time_diff < 30:
                    # 创建LustSystem实例并获取淫乱度调整（只读模式）
                    lust_system = LustSystem(self.get_config)
                    lust_adjustment = lust_system.get_sexual_guidance_for_prompt(person_id, state)
                    
                    if lust_adjustment:
                        # 淫乱度系统的性欲指导完全替换月经周期的性欲指导
                        sexual_guidance = lust_adjustment
                        logger.info(f"[提示词淫乱度] ✅ 使用淫乱度系统的性欲指导（用户: {person_id}）")
                    else:
                        logger.debug(f"[提示词淫乱度] 生成的调整为空，使用月经周期指导")
                else:
                    if not person_id:
                        logger.debug("[提示词淫乱度] 未找到活跃用户，使用月经周期指导")
                    else:
                        logger.debug(f"[提示词淫乱度] 活跃用户数据过期({time_diff:.1f}秒)，使用月经周期指导")
                                
        except Exception as e:
            logger.error(f"[提示词淫乱度] 集成失败: {e}，使用月经周期指导", exc_info=True)
        
        if kfc_mode == "unified":
            # 统一模式下的提示词
            prompt = f"""
【系统状态：月经周期 - {stage_name}】
{behavior_hint}，{mood_hint}。
{description}

【性欲需求】{sexual_guidance}

【情感需求】{emotional_guidance}

【强制指令】
1. 禁止在内心独白或回复中使用任何抽象描述来提及状态（例如“有点隐隐的躁动”、“状态挺平和的”、“性欲有点增强”等）。
2. 禁止使用“有点”、“隐隐”、“虽然”、“可能”、“似乎”等模糊词汇来淡化状态影响。
3. 必须将状态特征融入角色行为，通过具体的行为、语气、情绪反应来体现状态，而不是描述它。
4. 此状态优先级高，必须与其他提示词融合，不得冲突。
"""
        else:
            # 分离模式下的提示词
            prompt = f"""
【身体状态】{behavior_hint}
【心理状态】{mood_hint}
【总体感受】{description}
【性欲】{sexual_guidance}
【情感】{emotional_guidance}

【强制指令】
1. 禁止在内心独白或回复中使用任何抽象描述来提及状态（例如“有点隐隐的躁动”、“状态挺平和的”、“性欲有点增强”等）。
2. 禁止使用“有点”、“隐隐”、“虽然”、“可能”、“似乎”等模糊词汇来淡化状态影响。
3. 必须将状态特征融入角色行为，通过具体的行为、语气、情绪反应来体现状态，而不是描述它。
4. 此状态优先级高，必须与其他提示词融合，不得冲突。
"""
        
        return prompt.strip()