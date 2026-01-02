from typing import Dict, Any
import tomli
from pathlib import Path
from src.plugin_system.base.base_prompt import BasePrompt
from src.plugin_system.base.component_types import InjectionRule, InjectionType
from src.plugin_system.apis import config_api, person_api
from core.state_manager import get_state_manager, PromptTemplates
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
        self.state_manager = get_state_manager(get_config_func=self.get_config)
        # 初始化提示词模板系统（使用相同的配置函数）
        self.prompt_templates = PromptTemplates(get_config_func=self.get_config)
    
    def _load_jailbreak(self) -> str:
        """加载破甲词内容"""
        try:
            # 检查是否启用
            if not self.get_config("jailbreak.enabled", False):
                return ""
            
            # 直接从配置读取内容
            content = self.get_config("jailbreak.content", "").strip()
            
            if content:
                logger.info(f"[破甲词] 已加载，长度={len(content)}字符")
            else:
                logger.warning("[破甲词] 已启用但内容为空")
            
            return content
            
        except Exception as e:
            logger.error(f"[破甲词] 加载失败: {e}")
            return ""
        
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
            
            # ⚠️ 关键修复：通过 chat_id 反查 chat_stream 获取准确的聊天类型
            is_private_chat = await self._detect_chat_type()
            
            # 生成提示词
            if kfc_enabled and is_private_chat:
                # 私聊模式（无论 AFC 还是 KFC，包含完整性欲系统和破甲词）
                prompt = await self._generate_kfc_prompt(state, kfc_mode)
                jailbreak_enabled = self.get_config('jailbreak.enabled', False)
                has_jailbreak_in_prompt = '你的主人' in prompt or '恋人' in prompt  # 检查破甲词特征
                logger.info(f"[提示词模式] 私聊增强模式 | 破甲词配置={'启用' if jailbreak_enabled else '禁用'}, 实际注入={'是' if has_jailbreak_in_prompt else '否'}")
                logger.info(f"[提示词内容] 前100字: {prompt[:100]}...")
            else:
                # 群聊模式（无性欲，无破甲词）
                prompt = self._generate_prompt(state)
                logger.info(f"[提示词模式] 群聊标准模式 | kfc_enabled={kfc_enabled}, is_private={is_private_chat}")
            
            # 调试日志
            if debug_mode:
                chat_type = "私聊" if is_private_chat else "群聊"
                mode_name = "私聊增强模式" if (kfc_enabled and is_private_chat) else "标准模式"
                logger.debug(f"提示词生成完成: {chat_type} | {mode_name} | 长度={len(prompt)}字符")
            
            return prompt
            
        except Exception as e:
            logger.error(f"生成周期状态提示词失败: {e}")
            # 返回一个安全的默认提示词
            return "你今天的状态不错，可以自然地交流。"
    
    async def _detect_chat_type(self) -> bool:
        """检测聊天类型：True=私聊，False=群聊
        
        通过多种方法综合判断，优先级：
        1. 通过 chat_id 反查 chat_stream.group_info（最准确）
        2. 使用 params.is_group_chat 标志
        3. 解析 chat_id 字符串格式
        4. 默认群聊（安全策略）
        """
        # 初始化判断变量
        is_private_by_stream = None
        is_private_by_flag = None
        is_private_by_chat_id = None
        
        chat_id = self.params.chat_id or ''
        
        # 方法1（最准确）：通过 chat_id 反查 chat_stream
        if chat_id:
            try:
                from src.plugin_system.apis import chat_api
                chat_stream = await chat_api.get_chat_manager().get_stream(chat_id)
                if chat_stream:
                    # 直接检查 group_info 属性（标准方法）
                    is_private_by_stream = not bool(chat_stream.group_info)
                    logger.debug(f"[聊天类型判断] 方法1-chat_stream: group_info={'存在' if chat_stream.group_info else '不存在'} → is_private={is_private_by_stream}")
                else:
                    logger.warning(f"[聊天类型判断] 无法通过 chat_id={chat_id} 获取 chat_stream")
            except Exception as e:
                logger.error(f"[聊天类型判断] 反查 chat_stream 失败: {e}")
        else:
            logger.warning(f"[聊天类型判断] chat_id 为空，参数传递异常（platform={self.params.platform}）")
        
        # 方法2：使用 is_group_chat 参数标志
        is_group_flag = getattr(self.params, 'is_group_chat', None)
        if is_group_flag is not None:
            is_private_by_flag = not is_group_flag
            logger.debug(f"[聊天类型判断] 方法2-标志: is_group_chat={is_group_flag} → is_private={is_private_by_flag}")
        
        # 方法3：解析 chat_id 字符串
        if chat_id:
            if ':private' in chat_id:
                is_private_by_chat_id = True
            elif ':group' in chat_id:
                is_private_by_chat_id = False
            logger.debug(f"[聊天类型判断] 方法3-chat_id解析: {chat_id} → is_private={is_private_by_chat_id}")
        
        # 综合判断：优先级 stream > flag > chat_id > 默认群聊
        if is_private_by_stream is not None:
            is_private_chat = is_private_by_stream
            logger.info(f"[聊天类型判断] 使用方法1(chat_stream)判断结果: {'私聊' if is_private_chat else '群聊'}")
        elif is_private_by_flag is not None:
            is_private_chat = is_private_by_flag
            logger.info(f"[聊天类型判断] 使用方法2(标志)判断结果: {'私聊' if is_private_chat else '群聊'}")
        elif is_private_by_chat_id is not None:
            is_private_chat = is_private_by_chat_id
            logger.info(f"[聊天类型判断] 使用方法3(chat_id)判断结果: {'私聊' if is_private_chat else '群聊'}")
        else:
            is_private_chat = False
            logger.warning(f"[聊天类型判断] 所有方法都无法判断，默认群聊模式（安全策略）")
        
        # 详细调试日志
        target_prompt = getattr(self, 'target_prompt_name', '') or ''
        logger.info(f"[聊天类型判断] chat_id={chat_id}")
        logger.info(f"[聊天类型判断] is_group_chat标志={self.params.is_group_chat}")
        logger.info(f"[聊天类型判断] 目标提示词={target_prompt}")
        logger.info(f"[聊天类型判断] 判断结果: {'私聊' if is_private_chat else '群聊'}")
        logger.info(f"[聊天类型判断] 各方法结果 - stream:{is_private_by_stream}, flag:{is_private_by_flag}, chat_id:{is_private_by_chat_id}")
        
        return is_private_chat
    
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
            dysmenorrhea_prompt = self.prompt_templates.get_dysmenorrhea_prompt(dysmenorrhea_level)
            dysmenorrhea_desc = f"\n【痛经状况】{dysmenorrhea_prompt}"
        
        prompt = f"""
【系统状态设定：月经周期】

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
        physical_desc = self.prompt_templates.get_physical_prompt(physical_level)
        psychological_desc = self.prompt_templates.get_psychological_prompt(psychological_level)
        
        # 生成命令性的行为指导
        if physical_level >= 7:
            behavior_hint = "嗯...身体真的很不舒服...感觉好累好累，一点力气都没有..."
        elif physical_level >= 4:
            behavior_hint = "身体有点不太舒服...感觉累，想休息一下..."
        else:
            behavior_hint = "身体状态还不错，可以正常聊天～"
            
        if psychological_level >= 7:
            mood_hint = "心情...真的很不好...情绪波动特别大，很容易就..."
        elif psychological_level >= 4:
            mood_hint = "心情有点起伏...情绪不太稳定..."
        else:
            mood_hint = "心情还算平和，不过偶尔也会有点小情绪啦～"
        
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
                    
                    # 获取用户数据以判断阶段（使用只读方法，不修改存储）
                    user_data = lust_system.get_user_data_readonly(person_id, state)
                    user_stage = user_data.get("current_stage", "")
                    
                    lust_adjustment = lust_system.get_sexual_guidance_for_prompt(person_id, state)
                    
                    if lust_adjustment:
                        # 淫乱度系统的性欲指导完全替换月经周期的性欲指导
                        sexual_guidance = lust_adjustment
                        use_lust_system = True
                        logger.info(f"[提示词淫乱度] ✅ 使用淫乱度系统（阶段: {user_stage}）")
                        
                        # 在冷却期，情感需求也应该调整
                        if user_stage == "冷却":
                            emotional_guidance = "现在只想被温柔地关心和照顾，想好好休息...暂时不想聊那些..."
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
            dysmenorrhea_prompt = self.prompt_templates.get_dysmenorrhea_prompt(dysmenorrhea_level)
            dysmenorrhea_desc = f"\n【痛经状况】{dysmenorrhea_prompt}"
        
        # 加载破甲词（位于最顶部）
        jailbreak_text = self._load_jailbreak()
        jailbreak_section = f"{jailbreak_text}\n\n" if jailbreak_text else ""
        
        # 根据Bot的实际KFC模式生成提示词
        # 注意：当前Bot配置使用split模式（Planner + Replyer分离）
        if kfc_mode == "unified":
            # 统一模式：单次LLM调用，需要更详细的状态描述
            prompt = f"""
{jailbreak_section}【月经周期状态】
【我的身体】{behavior_hint}{dysmenorrhea_desc}
【我的心情】{mood_hint}

【性欲方面】{sexual_guidance}

【情感方面】{emotional_guidance}

【重要提醒】
1. 这就是我现在真实的状态，我会自然地表现出来，不会刻意掩饰或忽视。
2. 我不会用那些抽象的词来描述自己的状态（比如"有点隐隐的躁动"、"状态挺平和的"之类的）。
3. 我不会用"有点"、"隐隐"、"虽然"、"可能"、"似乎"这些模糊的词来淡化我的感受。
4. 我会把这些感受融入我的行为、语气、情绪里，自然地展现出来。
5. 这是我现在的真实状态，会影响我的所有反应。
"""
        else:
            # 分离模式（split）：Planner + Replyer，提示词需要精简清晰
            # 这是Bot当前使用的模式，提示词会注入到kfc_replyer
            prompt = f"""
{jailbreak_section}【我现在的状态】
【身体】{behavior_hint}{dysmenorrhea_desc}
【心情】{mood_hint}
【性欲】{sexual_guidance}
【情感】{emotional_guidance}

【重要】
1. 这就是我现在的状态，会自然地体现在我的回复里。
2. 不用那些模糊的词（"有点"、"隐隐"、"虽然"）来描述。
3. 把这些感受融入我的行为、语气、情绪中。
4. 这是我的真实状态，会影响我的所有表现。
"""
        
        return prompt.strip()