from typing import Dict, Any
import tomli
from pathlib import Path
from src.plugin_system.base.base_prompt import BasePrompt
from src.plugin_system.base.component_types import InjectionRule, InjectionType
from src.plugin_system.apis import config_api, person_api
from core.state_manager import PeriodStateManager
from core.lust_system import LustSystem
from src.common.logger import get_logger

logger = get_logger("mofox_period_plugin")

def get_bot_kfc_mode() -> str:
    """
    从Bot config读取KFC工作模式
    返回: "unified" 或 "split"
    """
    try:
        # Bot config路径（相对于插件目录）
        bot_config_path = Path(__file__).parent.parent.parent.parent / "config" / "bot_config.toml"
        
        if not bot_config_path.exists():
            logger.warning(f"Bot config文件不存在: {bot_config_path}，使用默认split模式")
            return "split"
        
        with open(bot_config_path, "rb") as f:
            bot_config = tomli.load(f)
        
        # 读取 [kokoro_flow_chatter] mode
        kfc_mode = bot_config.get("kokoro_flow_chatter", {}).get("mode", "split")
        logger.info(f"[KFC模式] 从Bot config读取: {kfc_mode}")
        return kfc_mode
        
    except Exception as e:
        logger.error(f"读取Bot config失败: {e}，使用默认split模式")
        return "split"

class PeriodStatePrompt(BasePrompt):
    """月经周期状态提示词注入"""
    
    prompt_name = "period_state_prompt"
    prompt_description = "根据月经周期状态调整机器人行为风格"
    
    # 注入到核心风格Prompt中，支持KFC模式
    # unified模式和split模式使用不同的注入目标
    injection_rules = [
        # 通用注入
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
        
        # KFC unified模式注入目标
        InjectionRule(
            target_prompt="kfc_unified_prompt",
            injection_type=InjectionType.APPEND,
            priority=100
        ),
        InjectionRule(
            target_prompt="kfc_main",
            injection_type=InjectionType.APPEND,
            priority=100
        ),
        InjectionRule(
            target_prompt="kfc_style_prompt",
            injection_type=InjectionType.APPEND,
            priority=100
        ),
        
        # KFC split模式注入目标
        InjectionRule(
            target_prompt="kfc_planner",
            injection_type=InjectionType.APPEND,
            priority=100
        ),
        InjectionRule(
            target_prompt="kfc_replyer",
            injection_type=InjectionType.PREPEND,
            priority=50
        )
    ]
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.state_manager = PeriodStateManager(get_config_func=self.get_config)
        
    async def execute(self) -> str:
        """生成周期状态提示词 - 增强KFC支持"""
        try:
            # 获取配置，增强错误处理和默认值
            cycle_length = self.get_config("cycle.cycle_length", 28)
            enabled = self.get_config("plugin.enabled", False)
            debug_mode = self.get_config("plugin.debug_mode", False)
            
            # 检查KFC集成配置
            kfc_enabled = self.get_config("kfc_integration.enabled", True)
            
            # 直接从Bot config读取KFC工作模式，确保与Bot配置一致
            kfc_mode = get_bot_kfc_mode()
            
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
        """根据状态生成提示词（非KFC模式：使用等级化系统）"""
        from core.state_manager import PromptTemplates
        
        stage_name = state["stage_name_cn"]
        physical_level = state.get("physical_level", 3)
        psychological_level = state.get("psychological_level", 3)
        dysmenorrhea_level = state.get("dysmenorrhea_level", 0)
        
        # 生成命令性的行为指导
        if physical_level >= 7:
            behavior_hint = "身体严重不适，必须表现出明显疲惫和无力感"
        elif physical_level >= 4:
            behavior_hint = "身体感到疲劳不适，应表现出需要休息"
        else:
            behavior_hint = "身体状态相对平稳，可正常交流"
            
        if psychological_level >= 7:
            mood_hint = "情绪很不稳定，必须表现出明显的情绪波动"
        elif psychological_level >= 4:
            mood_hint = "情绪有波动，应自然流露情绪变化"
        else:
            mood_hint = "心情相对平和，但允许自然的情绪起伏"
        
        # 痛经描述（如果有）
        dysmenorrhea_desc = ""
        if dysmenorrhea_level > 0:
            dysmenorrhea_prompt = PromptTemplates.get_dysmenorrhea_prompt(dysmenorrhea_level)
            dysmenorrhea_desc = f"\n【痛经状况】{dysmenorrhea_prompt}"
        
        prompt = f"""
【系统状态设定：月经周期】
你当前处于月经周期的【{stage_name}】阶段 第{state.get("day_in_phase", 1)}天。

【生理状况】{behavior_hint}{dysmenorrhea_desc}
【心理状况】{mood_hint}

【强制行为指令】
1. 你必须根据以上状态调整回复风格和行为表现，不得忽略或绕过该状态的影响。
2. 禁止在内心独白或回复中使用任何抽象描述来提及状态（例如"有点隐隐的躁动"、"状态挺平和的"等）。
3. 禁止使用"有点"、"隐隐"、"虽然"、"可能"、"似乎"等模糊词汇来淡化状态影响。
4. 必须将状态特征融入角色行为中，通过具体的行为、语气、情绪反应来体现状态，而不是描述它。
5. 此状态设定具有高优先级，必须与其他提示词融合，不得冲突。
6. 保持对话的自然流畅，但确保状态影响得到体现。

请立即执行。
"""
        return prompt.strip()
        
    async def _generate_kfc_prompt(self, state: Dict[str, Any], kfc_mode: str) -> str:
        """生成KFC模式下的提示词，集成淫乱度系统"""
        from core.state_manager import PromptTemplates
        
        stage_name = state["stage_name_cn"]
        physical_level = state.get("physical_level", 1)
        psychological_level = state.get("psychological_level", 1)
        dysmenorrhea_level = state.get("dysmenorrhea_level", 0)
        description = state["description"]
        current_day = state["current_day"]
        cycle_length = state["cycle_length"]
        
        # 获取等级化的客观描述
        physical_desc = PromptTemplates.get_physical_prompt(physical_level)
        psychological_desc = PromptTemplates.get_psychological_prompt(psychological_level)
        
        # 生成命令性的行为指导
        if physical_level >= 7:
            behavior_hint = "身体严重不适，必须表现出明显疲惫和无力感"
        elif physical_level >= 4:
            behavior_hint = "身体感到疲劳不适，应表现出需要休息"
        else:
            behavior_hint = "身体状态相对平稳，可正常交流"
            
        if psychological_level >= 7:
            mood_hint = "情绪很不稳定，必须表现出明显的情绪波动"
        elif psychological_level >= 4:
            mood_hint = "情绪有波动，应自然流露情绪变化"
        else:
            mood_hint = "心情相对平和，但允许自然的情绪起伏"
        
        # 获取亲密需求指导（性欲和情感分开）
        sexual_guidance, emotional_guidance = self.state_manager._get_intimacy_guidance(state["stage"], current_day, cycle_length)
        
        # 淫乱度系统集成：从storage读取最近活跃的用户
        use_lust_system = False  # 标记是否使用淫乱度系统
        user_stage = None  # 用户当前阶段
        
        try:
            import time
            from src.plugin_system.apis import storage_api
            
            lust_enabled = self.get_config("lust_system.enabled", False)
            
            # ⚠️ 月经期强制关闭淫乱度系统
            if state["stage"] == "menstrual":
                logger.info(f"[提示词淫乱度] 月经期检测到，强制关闭淫乱度系统")
                lust_enabled = False
            
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
                    
                    # 获取用户数据以判断阶段
                    user_data = lust_system.get_user_data(person_id)
                    user_stage = user_data.get("current_stage", "")
                    
                    lust_adjustment = lust_system.get_sexual_guidance_for_prompt(person_id, state)
                    
                    if lust_adjustment:
                        # 淫乱度系统的性欲指导完全替换月经周期的性欲指导
                        sexual_guidance = lust_adjustment
                        use_lust_system = True
                        logger.info(f"[提示词淫乱度] ✅ 使用淫乱度系统（阶段: {user_stage}）")
                        
                        # 在冷却期，情感需求也应该调整
                        if user_stage == "冷却":
                            emotional_guidance = "需要温柔关怀和休息，暂时不想讨论性相关话题。"
                            logger.info(f"[提示词淫乱度] 冷却期：同时调整情感指导")
                    else:
                        logger.debug(f"[提示词淫乱度] 生成的调整为空，使用月经周期指导")
                else:
                    if not person_id:
                        logger.debug("[提示词淫乱度] 未找到活跃用户，使用月经周期指导")
                    else:
                        logger.debug(f"[提示词淫乱度] 活跃用户数据过期({time_diff:.1f}秒)，使用月经周期指导")
                                
        except Exception as e:
            logger.error(f"[提示词淫乱度] 集成失败: {e}，使用月经周期指导", exc_info=True)
        
        # 痛经描述（如果有）
        dysmenorrhea_desc = ""
        if dysmenorrhea_level > 0:
            dysmenorrhea_prompt = PromptTemplates.get_dysmenorrhea_prompt(dysmenorrhea_level)
            dysmenorrhea_desc = f"\n【痛经状况】{dysmenorrhea_prompt}"
        
        # 根据Bot的实际KFC模式生成提示词
        # 注意：当前Bot配置使用split模式（Planner + Replyer分离）
        if kfc_mode == "unified":
            # 统一模式：单次LLM调用，需要更详细的状态描述
            prompt = f"""
【系统状态：月经周期 - {stage_name} 第{state.get("day_in_phase", 1)}天】
【生理状况】{behavior_hint}{dysmenorrhea_desc}
【心理状况】{mood_hint}

【性欲需求】{sexual_guidance}

【情感需求】{emotional_guidance}

【强制行为指令】
1. 你必须根据以上状态调整回复风格和行为表现，不得忽略或绕过该状态的影响。
2. 禁止在内心独白或回复中使用任何抽象描述来提及状态（例如"有点隐隐的躁动"、"状态挺平和的"、"性欲有点增强"等）。
3. 禁止使用"有点"、"隐隐"、"虽然"、"可能"、"似乎"等模糊词汇来淡化状态影响。
4. 必须将状态特征融入角色行为中，通过具体的行为、语气、情绪反应来体现状态，而不是描述它。
5. 此状态设定具有高优先级，必须与其他提示词融合，不得冲突。
"""
        else:
            # 分离模式（split）：Planner + Replyer，提示词需要精简清晰
            # 这是Bot当前使用的模式，提示词会注入到kfc_replyer
            prompt = f"""
【当前状态：{stage_name} 第{state.get("day_in_phase", 1)}天】
【生理】{behavior_hint}{dysmenorrhea_desc}
【心理】{mood_hint}
【性欲】{sexual_guidance}
【情感】{emotional_guidance}

【强制行为指令】
1. 必须根据以上状态调整你的回复风格和行为表现。
2. 禁止使用抽象描述来提及状态，禁止使用"有点"、"隐隐"、"虽然"等模糊词汇。
3. 将状态特征融入具体行为、语气、情绪反应中，而不是描述它。
4. 此状态优先级高，必须与其他提示词融合执行。
"""
        
        return prompt.strip()