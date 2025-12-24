"""
消息缓解判定事件处理器
监听 ON_MESSAGE 事件，判断用户消息是否具有痛经缓解作用
"""
from src.plugin_system import BaseEventHandler, EventType
from src.plugin_system.base.base_event import HandlerResult
from src.plugin_system.apis import llm_api
from src.common.logger import get_logger

# 导入管理器（延迟导入避免循环依赖）
from core.llm_relief_manager import LLMReliefManager

logger = get_logger("mofox_period_plugin.message_relief_handler")


class MessageReliefHandler(BaseEventHandler):
    """消息痛经缓解判定处理器
    
    订阅 ON_MESSAGE 事件，当用户发送消息时判断是否具有痛经缓解作用。
    如果判定有缓解作用，将临时降低痛经等级。
    
    注意：此功能为预留功能，需要LLM API集成后才能正常工作
    """
    
    handler_name = "message_relief_handler"
    handler_description = "使用LLM判定用户消息是否对痛经有缓解作用"
    init_subscribe = [EventType.ON_MESSAGE]
    weight = 60  # 在lust_scoring_handler之后执行
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.state_manager = None
        self.relief_manager = None
    
    async def execute(self, kwargs: dict | None) -> HandlerResult:  # type: ignore[override]
        """处理用户消息，判定是否有缓解痛经作用
        
        Args:
            kwargs: 事件参数，格式为 {"message": DatabaseMessages, ...}
        """
        try:
            if not kwargs:
                return HandlerResult(success=True, continue_process=True)
            # 检查是否启用LLM缓解功能
            enabled = self.get_config("plugin.enabled", False)
            llm_relief_enabled = self.get_config("dysmenorrhea.enable_llm_relief", False)
            
            if not enabled or not llm_relief_enabled:
                return HandlerResult(success=True, continue_process=True)
            
            # 延迟初始化管理器
            if not self.state_manager:
                from core.state_manager import get_state_manager
                self.state_manager = get_state_manager(get_config_func=self.get_config)
            
            if not self.relief_manager:
                config = self._collect_config()
                self.relief_manager = LLMReliefManager(config)
            
            # 检查当前是否在月经期
            state = self.state_manager.calculate_current_state()
            current_stage = state.get("stage")
            dysmenorrhea_level = state.get("dysmenorrhea_level", 0)
            
            logger.debug(f"当前周期状态: 阶段={current_stage}, 痛经等级={dysmenorrhea_level}")
            
            # 只在月经期且有痛经时才进行判定
            if current_stage != "menstrual":
                logger.debug(f"跳过缓解判定: 当前非月经期（{current_stage}）")
                return HandlerResult(success=True, continue_process=True)
            
            if dysmenorrhea_level == 0:
                logger.debug("跳过缓解判定: 当前无痛经症状")
                return HandlerResult(success=True, continue_process=True)
            
            # 获取 DatabaseMessages 对象
            db_message = kwargs.get("message")
            if not db_message or not hasattr(db_message, "processed_plain_text"):
                logger.debug("跳过缓解判定: 无法获取消息对象或文本内容")
                return HandlerResult(success=True, continue_process=True)
            
            # 获取消息文本内容
            message_text = db_message.processed_plain_text
            if not message_text or len(message_text.strip()) == 0:
                logger.debug("跳过缓解判定: 消息内容为空")
                return HandlerResult(success=True, continue_process=True)
            
            logger.info(f"📝 触发痛经缓解判定流程")
            logger.info(f"   当前痛经等级: {dysmenorrhea_level}级")
            logger.info(f"   消息内容: {message_text}")
            
            # 使用 LLM API 进行缓解判定
            has_relief = await self._judge_relief_with_llm(message_text)
            
            if has_relief:
                # 应用缓解效果
                self.relief_manager.apply_relief()
                logger.info(f"✅ 痛经缓解效果已生效！")
            else:
                logger.debug(f"❌ 消息未被判定为有缓解作用")
            
        except Exception as e:
            logger.error(f"消息缓解判定失败: {e}")
        
        return HandlerResult(success=True, continue_process=True)
    
    def _get_model_config(self, config_key: str, default_value: str = "utils"):
        """
        获取模型配置，支持两种方式：
        1. 任务配置名称（如 "utils", "replyer"）- 从 get_available_models() 获取
        2. 具体模型名称（如 "deepseek-v3", "qwen3-14b"）- 创建临时 TaskConfig
        
        Args:
            config_key: 配置键名
            default_value: 默认值
            
        Returns:
            TaskConfig 对象
        """
        from src.config.api_ada_configs import TaskConfig
        
        model_name = self.get_config(config_key, default_value)
        
        # 类型检查：确保 model_name 是字符串
        if not isinstance(model_name, str):
            logger.warning(f"[模型选择] 配置值类型错误: {type(model_name)}，使用默认值")
            model_name = default_value
        
        models = llm_api.get_available_models()
        
        # 方式1: 检查是否是任务配置名称
        if model_name in models:
            logger.debug(f"[模型选择] 使用任务配置: {model_name}")
            return models[model_name]
        
        # 方式2: 作为具体模型名称，创建临时 TaskConfig
        logger.info(f"[模型选择] '{model_name}' 不是任务配置，作为具体模型名称使用")
        try:
            temp_config = TaskConfig(
                model_list=[model_name],
                temperature=0.3,
                max_tokens=10
            )
            return temp_config
        except Exception as e:
            logger.error(f"[模型选择] 创建模型配置失败: {e}，使用默认模型")
            return next(iter(models.values())) if models else None
    
    async def _judge_relief_with_llm(self, message_text: str) -> bool:
        """
        使用 LLM API 判断消息是否有缓解作用
        
        Args:
            message_text: 用户消息内容
            
        Returns:
            bool: True 表示有缓解作用
        """
        try:
            logger.info(f"========== 痛经缓解LLM判定开始 ==========")
            
            # 构造判定提示词
            prompt = f"""请判断以下用户消息是否对痛经有缓解作用。

缓解作用包括但不限于：
- 表达关心、安慰、理解
- 提供实用建议（热敷、喝热水、休息等）
- 询问需要帮助
- 提供情感支持和陪伴
- 物理安慰动作（抽抱、摸头、温暖的手等）
- 分散注意力的有趣内容

不包括：
- 普通闲聊
- 无关话题
- 责备或不理解的言论

用户消息："{message_text}"

请只回答"是"或"否"。"""
            
            logger.info(f"待判定消息: {message_text}")
            
            # 获取模型配置（支持任务配置名或具体模型名）
            model_config = self._get_model_config("dysmenorrhea.llm_model", "utils")
            if not model_config:
                logger.warning("⚠️ 无可用LLM模型，跳过判定")
                return False
            
            # 获取模型名称（用于日志）
            if hasattr(model_config, 'model_list') and model_config.model_list:
                actual_model_name = model_config.model_list[0]
            else:
                actual_model_name = "unknown"
            
            logger.info(f"🤖 使用模型: {actual_model_name}")
            
            # 调用LLM
            success, response, _, _ = await llm_api.generate_with_model(
                prompt=prompt,
                model_config=model_config,
                request_type="mofox_period_plugin.relief_judgment",
                temperature=0.3,  # 降低随机性
                max_tokens=10
            )
            
            if not success:
                logger.warning(f"❌ LLM调用失败: {response}")
                logger.info(f"========== 痛经缓解LLM判定失败 ==========\n")
                return False
            
            logger.info(f"LLM原始响应: '{response}'")
            
            # 解析响应
            result = response.strip().lower()
            has_relief = "是" in result or "yes" in result or "有" in result
            
            logger.info(f"判定结果: {'✅ 有缓解作用' if has_relief else '❌ 无缓解作用'}")
            
            if has_relief:
                duration = self.get_config("dysmenorrhea.relief_duration_minutes", 60)
                reduction = self.get_config("dysmenorrhea.relief_reduction", 1)
                logger.info(f"🌟 消息被判定具有痛经缓解作用！")
                logger.info(f"   缓解参数: 降低{reduction}级, 持续{duration}分钟")
            
            logger.info(f"========== 痛经缓解LLM判定结束 ==========\n")
            return has_relief
            
        except Exception as e:
            logger.error(f"❌ LLM判定过程出错: {e}", exc_info=True)
            return False
    
    def _collect_config(self) -> dict:
        """收集配置信息"""
        return {
            "dysmenorrhea.prob_none": self.get_config("dysmenorrhea.prob_none", 0.25),
            "dysmenorrhea.prob_mild": self.get_config("dysmenorrhea.prob_mild", 0.30),
            "dysmenorrhea.prob_moderate": self.get_config("dysmenorrhea.prob_moderate", 0.25),
            "dysmenorrhea.prob_severe": self.get_config("dysmenorrhea.prob_severe", 0.20),
            "dysmenorrhea.enable_llm_relief": self.get_config("dysmenorrhea.enable_llm_relief", False),
            "dysmenorrhea.relief_duration_minutes": self.get_config("dysmenorrhea.relief_duration_minutes", 60),
            "dysmenorrhea.relief_reduction": self.get_config("dysmenorrhea.relief_reduction", 1),
        }
