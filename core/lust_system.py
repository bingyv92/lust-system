import time
from typing import Dict, Any, Optional, List
from src.plugin_system.apis import storage_api, llm_api
from src.common.logger import get_logger

logger = get_logger("mofox_period_plugin")

# 获取插件的本地存储实例
plugin_storage = storage_api.get_local_storage("mofox_period_plugin")

class LustSystem:
    """淫乱度与高潮值系统"""

    def __init__(self, get_config=None):
        """初始化LustSystem"""
        self.get_config = get_config or (lambda key, default: default)

    # ==================== 淫乱度计算 ====================

    def calculate_lust_level(self, period_state: Dict[str, Any]) -> float:
        """
        根据月经周期状态计算淫乱度 (0.0 ~ 1.0)
        """
        try:
            stage = period_state.get("stage", "follicular")
            current_day = period_state.get("current_day", 1)
            cycle_length = period_state.get("cycle_length", 28)

            # 基础淫乱度映射
            base_lust = {
                "menstrual": 0.1,
                "follicular": 0.3,
                "ovulation": 0.9,
                "luteal": 0.5
            }
            lust = base_lust.get(stage, 0.3)

            # 根据周期天数微调
            adjustment = self._calculate_adjustment(stage, current_day, cycle_length)
            lust += adjustment

            # 限制在 0.0 ~ 1.0 之间
            return max(0.0, min(1.0, round(lust, 2)))

        except Exception as e:
            logger.error(f"计算淫乱度失败: {e}")
            return 0.3

    def _calculate_adjustment(self, stage: str, current_day: int, cycle_length: int) -> float:
        """计算周期内微调值"""
        if stage == "menstrual":
            return (current_day - 1) / 5 * 0.05
        elif stage == "follicular":
            day_in_stage = current_day - 1
            return (day_in_stage / 13) * 0.2
        elif stage == "ovulation":
            return 0.0
        elif stage == "luteal":
            day_in_stage = current_day - 14
            total_days = cycle_length - 14
            if total_days <= 0:
                return 0.0
            return (day_in_stage / total_days) * 0.1
        return 0.0

    def get_max_orgasms(self, lust_level: float) -> int:
        """根据淫乱度计算最大高潮次数"""
        return max(1, int(lust_level * 5))

    # ==================== LLM评分 ====================

    async def score_message_with_llm(self, text: str, lust_level: float) -> float:
        """
        使用LLM对消息内容评分，返回0-10的分数
        """
        try:
            # 构建提示词
            prompt = f"""请判断以下消息的性暗示程度，用0-10的整数评分。
0分：完全无性暗示
10分：极强的性暗示

消息："{text}"

请只输出一个0-10之间的整数，不要有其他内容。"""

            # 获取可用的LLM模型
            models = llm_api.get_available_models()
            if not models:
                logger.warning("[LLM评分] 无可用模型，使用【关键词回退方案】")
                return self._keyword_score(text, lust_level)

            # 尝试使用配置的模型，否则使用第一个可用模型
            model_name = self._get_config("lust_system.llm_model", "default")
            model_config = models.get(model_name) or next(iter(models.values()))
            
            # 尝试多种可能的属性名获取模型名称
            actual_model_name = (
                getattr(model_config, "name", None) or
                getattr(model_config, "model_name", None) or
                getattr(model_config, "id", None) or
                getattr(model_config, "model_id", None) or
                str(model_name)
            )
            logger.debug(f"[LLM评分] 模型配置类型: {type(model_config)}, 可用属性: {dir(model_config)[:10]}")
            
            # 调用LLM
            success, response, _, _ = await llm_api.generate_with_model(
                prompt=prompt,
                model_config=model_config,
                request_type="mofox_period_plugin.lust_scoring",
            )
            
            if not success:
                logger.warning(f"[LLM评分] 模型 {actual_model_name} 调用失败: {response}，使用【关键词回退方案】")
                return self._keyword_score(text, lust_level)
            
            # 解析分数
            score = self._parse_score(response)
            if score is None:
                logger.warning(f"[LLM评分] 模型 {actual_model_name} 无法解析响应: {response[:100]}，使用【关键词回退方案】")
                return self._keyword_score(text, lust_level)
            
            # 应用淫乱度加成：分数 × (1 + 淫乱度)
            weighted_score = score * (1.0 + lust_level)
            logger.info(f"[LLM评分] ✅ 模型={actual_model_name}, 原始={score}, 淫乱度={lust_level:.2f}, 加成后={weighted_score:.1f}")
            
            return round(weighted_score, 1)
            
        except Exception as e:
            logger.error(f"[LLM评分] 异常: {e}")
            return self._keyword_score(text, lust_level)

    def _parse_score(self, response: str) -> Optional[float]:
        """从LLM响应中解析分数"""
        import re
        match = re.search(r'(\d+)', response.strip())
        if match:
            score = int(match.group(1))
            if 0 <= score <= 10:
                return float(score)
        return None

    def _keyword_score(self, text: str, lust_level: float) -> float:
        """基于关键词的评分（回退方案）"""
        keywords = [
            # 核心性行为词汇
            "做爱", "性交", "插入", "高潮", "射精", "性爱", "交配", "云雨",
            
            # 身体部位
            "阴道", "阴茎", "胸部", "乳房", "奶子", "屁股", "臀部", "下体", "私处",
            "阴蒂", "G点", "龟头", "乳头", "乳晕", "大腿", "腰", "小腹",
            
            # 动作词汇
            "舔", "摸", "操", "干", "肏", "弄", "揉", "搓", "吸", "咬", "亲", "吻",
            "抚摸", "爱抚", "触碰", "抱", "搂", "压", "骑", "坐", "趴", "跪",
            
            # 状态描述
            "骚", "淫", "浪", "欲", "硬", "湿", "润", "软", "胀", "热", "烫", "酥",
            "麻", "痒", "紧", "松", "滑", "黏", "涨", "胀", "肿", "敏感",
            
            # 性行为类型
            "前戏", "后入", "口交", "肛交", "自慰", "手淫", "打飞机", "指交",
            "深喉", "吞精", "颜射", "胸推", "足交", "69", "3P", "群交",
            
            # 生理反应
            "勃起", "硬了", "挺立", "充血", "呻吟", "喘息", "叫床", "高潮",
            "潮吹", "抽搐", "痉挛", "颤抖", "收缩", "夹紧", "发软", "瘫软",
            
            # 情感词汇
            "老公", "老婆", "宝贝", "亲爱的", "想要", "渴望", "迫不及待",
            "忍不住", "受不了", "要死了", "好想", "想念",
            
            # 感受描述
            "舒服", "爽", "快感", "愉悦", "满足", "销魂", "欲仙欲死", "飘飘欲仙",
            "酸爽", "刺激", "兴奋", "激动", "疼", "痛", "难受",
            
            # 场景物品
            "内射", "外射", "避孕套", "套套", "润滑", "润滑液", "情趣", "体位",
            "床上", "被窝", "枕头", "沙发", "浴室", "车里",
            
            # 行为描述
            "调情", "诱惑", "挑逗", "勾引", "撩", "性感", "妩媚", "风骚",
            "裸体", "脱光", "脱衣", "露出", "春光", "走光", "凸点",
            
            # 时间场景
            "夜晚", "深夜", "半夜", "清晨", "午后", "黄昏",
            
            # 隐私相关
            "秘密", "私密", "隐私", "悄悄", "偷偷", "秘密",
            
            # 拟声词
            "啊", "嗯", "哦", "呜", "唔", "嘤", "嗷", "嘶",
            
            # 其他暗示
            "那个", "那里", "那方面", "办事", "来一发", "整一下",
            "睡一觉", "睡了", "上床", "滚床单", "办正事"
        ]
        
        # 统计命中的关键词数量
        matched_keywords = [kw for kw in keywords if kw in text]
        keyword_count = len(matched_keywords)
        
        # 每个关键词0.5分，最高10分
        score = min(keyword_count * 0.5, 10.0)
        weighted = score * (1.0 + lust_level)
        
        logger.info(f"[关键词回退方案] 匹配={keyword_count}个关键词, 基础分={score}, 淫乱度={lust_level:.2f}, 加成后={weighted:.1f}")
        return round(weighted, 1)

    # ==================== 高潮值管理 ====================

    def get_user_data(self, user_id: str) -> Dict[str, Any]:
        """获取用户数据，如果不存在则初始化"""
        key = f"lust_system:user_data:{user_id}"
        data = plugin_storage.get(key, None)
        if data is None:
            data = self._create_default_user_data(user_id)
            plugin_storage.set(key, data)
        
        # 检查冷却期是否已过期
        self._check_and_clear_cooldown(user_id, data)
        
        return data

    def _create_default_user_data(self, user_id: str) -> Dict[str, Any]:
        """创建默认用户数据"""
        lust_level = 0.3
        max_orgasms = self.get_max_orgasms(lust_level)
        foreplay_threshold = self._get_config("lust_system.foreplay_threshold", 20.0)
        initial_ratio = self._get_config("lust_system.initial_ratio", 0.5)
        initial_orgasm_value = lust_level * foreplay_threshold * initial_ratio

        return {
            "orgasm_value": initial_orgasm_value,
            "remaining_orgasms": max_orgasms,
            "max_orgasms": max_orgasms,
            "last_updated": time.time(),
            "cooldown_until": None,
            "current_stage": self._determine_stage(initial_orgasm_value),
            "consecutive_low_scores": 0,
            "termination_decay_multiplier": 1.0,
            "lust_level": lust_level,
            "last_period_state": None,
        }

    def save_user_data(self, user_id: str, data: Dict[str, Any]):
        """保存用户数据"""
        key = f"lust_system:user_data:{user_id}"
        plugin_storage.set(key, data)

    def _determine_stage(self, orgasm_value: float) -> str:
        """根据高潮值确定当前阶段"""
        foreplay_threshold = self._get_config("lust_system.foreplay_threshold", 20.0)
        main_threshold = self._get_config("lust_system.main_threshold", 60.0)
        orgasm_threshold = self._get_config("lust_system.orgasm_threshold", 100.0)
        passive_active_ratio = self._get_config("lust_system.passive_active_ratio", 0.3)
        passive_active_threshold = foreplay_threshold * passive_active_ratio

        if orgasm_value < passive_active_threshold:
            return "被动未开始"
        elif orgasm_value < foreplay_threshold:
            return "主动未开始"
        elif orgasm_value < main_threshold:
            return "前戏"
        elif orgasm_value < orgasm_threshold:
            return "正戏"
        else:
            return "高潮"

    def update_orgasm_value(self, user_id: str, score: float) -> Dict[str, Any]:
        """更新用户的高潮值（考虑时间衰减）"""
        data = self.get_user_data(user_id)
        now = time.time()
        last_updated = data.get("last_updated", now)
        delta_seconds = max(0, now - last_updated)

        # 应用时间衰减
        decay_rate = self._get_config("lust_system.decay_rate", 0.1)
        termination_multiplier = data.get("termination_decay_multiplier", 1.0)
        decay = decay_rate * delta_seconds * termination_multiplier
        orgasm_value = max(0, data.get("orgasm_value", 0) - decay)

        # 添加新得分（score已经包含淫乱度加成）
        base_score_weight = self._get_config("lust_system.base_score_weight", 1.0)
        orgasm_value += score * base_score_weight

        # 更新数据
        data["orgasm_value"] = orgasm_value
        data["last_updated"] = now
        data["current_stage"] = self._determine_stage(orgasm_value)

        # 检查是否触发高潮
        orgasm_threshold = self._get_config("lust_system.orgasm_threshold", 100.0)
        if orgasm_value >= orgasm_threshold:
            self._trigger_orgasm(user_id, data)

        self.save_user_data(user_id, data)
        return data

    def _trigger_orgasm(self, user_id: str, data: Dict[str, Any]):
        """触发高潮"""
        logger.info(f"[高潮] 用户 {user_id} 触发高潮")
        
        # 标记刚刚触发高潮（用于Prompt系统）
        data["just_orgasmed"] = True
        data["orgasm_triggered_at"] = time.time()
        
        # 剩余高潮次数减1
        remaining = data.get("remaining_orgasms", 1)
        if remaining > 0:
            data["remaining_orgasms"] = remaining - 1
        
        # 高潮后恢复到正戏中段
        main_threshold = self._get_config("lust_system.main_threshold", 60.0)
        post_orgasm_recovery_ratio = self._get_config("lust_system.post_orgasm_recovery_ratio", 0.4)
        data["orgasm_value"] = main_threshold * post_orgasm_recovery_ratio
        data["current_stage"] = self._determine_stage(data["orgasm_value"])
        
        # 重置连续低评分
        data["consecutive_low_scores"] = 0
        data["termination_decay_multiplier"] = 1.0

        # 检查是否体力不支
        if data["remaining_orgasms"] <= 0:
            self._start_cooldown(user_id, data)

    def _start_cooldown(self, user_id: str, data: Dict[str, Any]):
        """开始冷却（体力不支）"""
        cooldown_duration = self._get_config("lust_system.cooldown_duration", 300)
        data["cooldown_until"] = time.time() + cooldown_duration
        data["current_stage"] = "冷却"
        data["lust_level"] = data.get("lust_level", 0.3) * 0.5
        data["orgasm_value"] = 0
        logger.info(f"[冷却] 用户 {user_id} 进入冷却 {cooldown_duration}秒")
    
    def _check_and_clear_cooldown(self, user_id: str, data: Dict[str, Any]):
        """检查并清除已过期的冷却期"""
        cooldown_until = data.get("cooldown_until")
        if cooldown_until is not None:
            now = time.time()
            if now >= cooldown_until:
                # 冷却期已过，恢复状态
                logger.info(f"[冷却结束] 用户 {user_id} 冷却期已过，等待最新月经周期数据更新状态")
                
                # 清除冷却期标记
                data["cooldown_until"] = None
                
                # 标记需要重新初始化（在下次调用get_sexual_guidance_adjustment_for_user时会用最新数据更新）
                data["need_reinit_after_cooldown"] = True
                
                # 重置其他状态
                data["consecutive_low_scores"] = 0
                data["termination_decay_multiplier"] = 1.0
                data["just_orgasmed"] = False
                
                # 保存更新后的数据
                self.save_user_data(user_id, data)

    def process_score(self, user_id: str, score: float) -> Dict[str, Any]:
        """处理评分，更新连续低评分计数，更新高潮值"""
        data = self.get_user_data(user_id)
        
        # 清除上次的高潮标记（如果存在且已过期）
        if data.get("just_orgasmed"):
            orgasm_time = data.get("orgasm_triggered_at", 0)
            # 高潮标记保持30秒，之后自动清除
            if time.time() - orgasm_time > 30:
                data["just_orgasmed"] = False
        
        # 只在"正戏"阶段才触发低评分加速衰减机制
        current_stage = data.get("current_stage", "被动未开始")
        if current_stage == "正戏":
            low_score_threshold = self._get_config("lust_system.low_score_threshold", 3.0)

            if score < low_score_threshold:
                data["consecutive_low_scores"] = data.get("consecutive_low_scores", 0) + 1
                low_score_count = self._get_config("lust_system.low_score_count_to_terminate", 3)
                if data["consecutive_low_scores"] >= low_score_count:
                    data["termination_decay_multiplier"] = self._get_config("lust_system.termination_decay_multiplier", 2.0)
                    logger.info(f"[递减] 用户 {user_id} 在正戏阶段触发加速衰减")
            else:
                if data.get("termination_decay_multiplier", 1.0) > 1.0:
                    logger.info(f"[恢复] 用户 {user_id} 重置衰减倍率")
                data["consecutive_low_scores"] = 0
                data["termination_decay_multiplier"] = 1.0
        else:
            # 非正戏阶段，重置加速衰减相关状态
            if data.get("consecutive_low_scores", 0) > 0 or data.get("termination_decay_multiplier", 1.0) > 1.0:
                logger.info(f"[重置] 用户 {user_id} 离开正戏阶段，重置加速衰减状态")
                data["consecutive_low_scores"] = 0
                data["termination_decay_multiplier"] = 1.0

        # 更新高潮值
        return self.update_orgasm_value(user_id, score)

    # ==================== 性欲指导生成 ====================

    def get_sexual_guidance_adjustment(
        self,
        lust_level: float,
        orgasm_value: float,
        remaining_orgasms: int,
        current_stage: str,
        max_orgasms: int = None
    ) -> str:
        """根据状态生成性欲指导"""
        guidance_map = {
            "被动未开始": "性欲较低，对性接触兴趣不大，更倾向于情感交流，处于被动状态。",
            "主动未开始": "性欲开始萌动，对性接触表现出一定兴趣，愿意主动参与轻度亲密。",
            "前戏": "开始产生性趣，愿意接受轻度亲密，但还不渴望实质性行为。",
            "正戏": "性欲强烈，主动寻求性接触，表现出明显的生理反应。",
            "高潮": "达到性高潮，身心愉悦，之后进入短暂的不应期。",
            "冷却": "性欲得到满足后进入冷却，体力不支，性欲暂时降低。"
        }
        
        guidance = guidance_map.get(current_stage, "性欲状态正常。")

        # 只有在已经消耗过高潮次数时才显示体力提示
        # 判断依据：remaining_orgasms < max_orgasms（说明已经使用过）
        if max_orgasms is not None and remaining_orgasms < max_orgasms:
            # 已经消耗过，根据剩余次数显示体力状态
            if remaining_orgasms == 0:
                guidance += " 体力已耗尽，需要休息恢复。"
            elif remaining_orgasms <= 1:
                guidance += " 体力接近极限，请温柔对待。"
            elif remaining_orgasms <= 2:
                guidance += " 体力尚可，但不宜过度激烈。"

        # 根据淫乱度调整语气
        if lust_level >= 0.7:
            guidance += " 淫乱度较高，性欲表现更为主动和强烈。"
        elif lust_level <= 0.3:
            guidance += " 淫乱度较低，性欲表现较为被动和温和。"

        return guidance
    

    def get_sexual_guidance_for_prompt(
        self,
        user_id: str,
        period_state: Dict[str, Any]
    ) -> str:
        """
        【只读模式】为Prompt生成性欲指导，不修改用户数据
        专门用于Prompt注入，避免覆盖LLM评分后的状态更新
        """
        # 计算当前淫乱度
        lust_level = self.calculate_lust_level(period_state)
        
        # 只读取数据，不修改
        data = self.get_user_data(user_id)
        
        # 如果需要冷却后初始化，先执行（这会修改数据）
        if data.get("need_reinit_after_cooldown"):
            self._perform_cooldown_reinit(user_id, data, period_state, lust_level)
            # 重新读取更新后的数据
            data = self.get_user_data(user_id)
        
        # 检查淫乱度是否需要更新（但不立即更新，避免覆盖评分后的状态）
        old_lust = data.get("lust_level", 0)
        if abs(old_lust - lust_level) > 0.01:
            # 记录需要更新，但不立即执行
            logger.debug(f"[Prompt只读] 检测到淫乱度变化 {old_lust:.2f}→{lust_level:.2f}，将在下次评分时更新")
        
        # 使用最新的淫乱度计算指导（但使用存储的remaining_orgasms等状态）
        current_lust = lust_level  # 使用最新计算的淫乱度
        
        logger.debug(f"[Prompt只读] 用户{user_id}: 淫乱度={current_lust:.2f}, "
                    f"剩余高潮={data.get('remaining_orgasms', 0)}/{data.get('max_orgasms', 0)}, "
                    f"当前阶段={data.get('current_stage', 'unknown')}, "
                    f"高潮值={data.get('orgasm_value', 0):.1f}")
        
        guidance = self.get_sexual_guidance_adjustment(
            lust_level=current_lust,
            orgasm_value=data.get("orgasm_value", 0.0),
            remaining_orgasms=data.get("remaining_orgasms", 0),
            current_stage=data.get("current_stage", "被动未开始"),
            max_orgasms=data.get("max_orgasms", 0)
        )
        
        # 如果刚刚触发高潮，直接返回高潮提示
        if data.get("just_orgasmed"):
            orgasm_time = data.get("orgasm_triggered_at", 0)
            if time.time() - orgasm_time <= 30:
                return "【刚刚达到高潮】你刚刚经历了强烈的性高潮，身体和精神都处于极度愉悦和敏感的状态。现在进入短暂的不应期，对进一步刺激暂时失去兴趣，需要时间恢复。"
        
        return guidance
    
    def _perform_cooldown_reinit(
        self,
        user_id: str,
        data: Dict[str, Any],
        period_state: Dict[str, Any],
        lust_level: float
    ):
        """执行冷却后的重新初始化"""
        logger.info(f"[冷却后初始化] 用户 {user_id} 使用最新月经周期数据重新初始化")
        
        # 使用最新的period_state和lust_level重新初始化
        data["lust_level"] = lust_level
        data["last_period_state"] = period_state
        
        # 重置高潮次数
        data["remaining_orgasms"] = self.get_max_orgasms(lust_level)
        data["max_orgasms"] = data["remaining_orgasms"]
        
        # 重置高潮值到初始状态
        foreplay_threshold = self._get_config("lust_system.foreplay_threshold", 20.0)
        initial_ratio = self._get_config("lust_system.initial_ratio", 0.5)
        data["orgasm_value"] = lust_level * foreplay_threshold * initial_ratio
        
        # 更新阶段
        data["current_stage"] = self._determine_stage(data["orgasm_value"])
        
        # 清除重新初始化标记
        data["need_reinit_after_cooldown"] = False
        
        self.save_user_data(user_id, data)
        logger.info(f"[冷却后初始化] 淫乱度={lust_level:.2f}, 剩余高潮={data['remaining_orgasms']}, 阶段={data['current_stage']}")
    
    def update_lust_from_period_state(
        self,
        user_id: str,
        period_state: Dict[str, Any]
    ):
        """
        【写入模式】从月经周期状态更新淫乱度数据
        在LLM评分时调用，确保淫乱度和最大高潮次数保持同步
        """
        lust_level = self.calculate_lust_level(period_state)
        data = self.get_user_data(user_id)
        
        old_lust = data.get("lust_level", 0)
        data["last_period_state"] = period_state
        data["lust_level"] = lust_level
        
        # 如果淫乱度发生变化，需要重新计算高潮次数上限
        if abs(old_lust - lust_level) > 0.01:
            new_max_orgasms = self.get_max_orgasms(lust_level)
            old_max = data.get("max_orgasms", 0)
            # 如果最大值增加了，同步增加剩余次数
            if new_max_orgasms > old_max:
                diff = new_max_orgasms - old_max
                data["remaining_orgasms"] = data.get("remaining_orgasms", 0) + diff
            data["max_orgasms"] = new_max_orgasms
            logger.info(f"[淫乱度更新] 用户{user_id}: {old_lust:.2f}→{lust_level:.2f}, "
                       f"最大高潮次数={new_max_orgasms}")
        
        self.save_user_data(user_id, data)

    # ==================== 工具方法 ====================

    def _get_config(self, key: str, default: Any) -> Any:
        """从插件配置中获取值"""
        return self.get_config(key, default)

    def reset_session(self, user_id: str):
        """重置会话"""
        data = self._create_default_user_data(user_id)
        self.save_user_data(user_id, data)
        logger.info(f"[重置] 用户 {user_id} 会话已重置")