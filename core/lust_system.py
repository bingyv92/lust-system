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
        ⚠️ 月经期强制返回0.0，禁用淫乱度系统
        
        新算法：
        - 周期阶段决定基础淫乱度
        - 生理/心理等级作为调节因子（等级3为中性1.0，1-2增强，4-10抑制）
        """
        try:
            stage = period_state.get("stage", "follicular")
            
            # ⚠️ 月经期强制关闭淫乱度系统
            if stage == "menstrual":
                logger.info(f"[淫乱度计算] 月经期检测到，强制返回0.0（禁用淫乱度）")
                return 0.0
            
            # 获取生理和心理等级
            physical_level = period_state.get("physical_level", 3)
            psychological_level = period_state.get("psychological_level", 3)

            # 基础淫乱度（由周期阶段决定）
            base_lust = {
                "follicular": 0.3,
                "ovulation": 0.9,
                "luteal": 0.5
            }
            lust = base_lust.get(stage, 0.3)

            # 计算生理调节因子
            physical_factor = self._calculate_level_factor(physical_level)
            
            # 计算心理调节因子
            psychological_factor = self._calculate_level_factor(psychological_level)

            # 综合计算淫乱度
            lust = lust * physical_factor * psychological_factor

            # 限制在 0.0 ~ 1.0 之间
            final_lust = max(0.0, min(1.0, round(lust, 2)))
            
            logger.debug(f"[淫乱度计算] 阶段={stage}, 生理={physical_level}(×{physical_factor:.2f}), "
                        f"心理={psychological_level}(×{psychological_factor:.2f}), "
                        f"基础={base_lust.get(stage, 0.3):.2f} → 最终={final_lust:.2f}")
            
            return final_lust

        except Exception as e:
            logger.error(f"计算淫乱度失败: {e}")
            return 0.3

    def _calculate_level_factor(self, level: int) -> float:
        """
        根据等级计算调节因子
        - 等级1-2：正面影响（>1.0）
        - 等级3：中性（=1.0）
        - 等级4-10：负面影响（<1.0）
        
        映射：
        level=1 → 1.2 (增强20%)
        level=2 → 1.1 (增强10%)
        level=3 → 1.0 (中性)
        level=10 → 0.5 (抑制50%)
        """
        if level <= 3:
            # 等级1-3：1.2, 1.1, 1.0
            return 1.0 + (3 - level) * 0.1
        else:
            # 等级4-10：线性递减到0.5
            # 公式：1.0 - (level - 3) * (0.5 / 7)
            return max(0.5, 1.0 - (level - 3) * 0.0714)

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
            prompt = f"""请判断以下消息的性刺激程度，用0-10的整数评分。
0分：完全无性刺激
10分：极强的性刺激

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

    def get_user_data(self, user_id: str, period_state: Dict[str, Any] = None) -> Dict[str, Any]:
        """获取用户数据，如果不存在则初始化"""
        key = f"lust_system:user_data:{user_id}"
        data = plugin_storage.get(key, None)
        if data is None:
            data = self._create_default_user_data(user_id, period_state)
            plugin_storage.set(key, data)
        
        # 检查冷却期是否已过期
        self._check_and_clear_cooldown(user_id, data)
        
        return data

    def _create_default_user_data(self, user_id: str, period_state: Dict[str, Any] = None) -> Dict[str, Any]:
        """创建默认用户数据"""
        # 根据当前月经周期状态计算淫乱度，如果没有提供则使用默认值0.3
        if period_state:
            lust_level = self.calculate_lust_level(period_state)
            logger.info(f"[初始化] 用户 {user_id} 根据月经周期计算初始淫乱度={lust_level:.2f}")
        else:
            lust_level = 0.3
            logger.warning(f"[初始化] 用户 {user_id} 未提供月经状态，使用默认淫乱度=0.3")
        
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
            "termination_triggered": False,  # 性交终止判定标记
            "lust_level": lust_level,
            "last_period_state": period_state,  # 保存当前周期状态
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
            self._start_afterglow(user_id, data)

    def _start_afterglow(self, user_id: str, data: Dict[str, Any]):
        """开始高潮余韵期"""
        afterglow_duration = self._get_config("lust_system.afterglow_duration", 60)
        recovery_duration = self._get_config("lust_system.recovery_duration", 240)
        total_duration = afterglow_duration + recovery_duration
        
        data["afterglow_started_at"] = time.time()
        data["afterglow_until"] = time.time() + afterglow_duration
        data["recovery_until"] = time.time() + total_duration
        data["current_stage"] = "高潮余韵期"
        data["lust_level"] = data.get("lust_level", 0.3) * 0.5
        data["orgasm_value"] = 0
        logger.info(f"[余韵期] 用户 {user_id} 进入高潮余韵期 {afterglow_duration}秒，随后恢复期 {recovery_duration}秒")
    
    def _check_and_clear_cooldown(self, user_id: str, data: Dict[str, Any]):
        """检查并更新余韵期/恢复期状态"""
        now = time.time()
        
        # 检查是否在余韵期或恢复期
        afterglow_until = data.get("afterglow_until")
        recovery_until = data.get("recovery_until")
        
        if recovery_until is not None:
            if now >= recovery_until:
                # 恢复期已过，完全恢复
                logger.info(f"[恢复完成] 用户 {user_id} 体力已完全恢复")
                
                # 清除所有恢复期标记
                data["afterglow_until"] = None
                data["recovery_until"] = None
                data["afterglow_started_at"] = None
                
                # 标记需要重新初始化
                data["need_reinit_after_cooldown"] = True
                
                # 重置其他状态
                data["consecutive_low_scores"] = 0
                data["termination_decay_multiplier"] = 1.0
                data["just_orgasmed"] = False
                data["termination_triggered"] = False  # 清除终止判定标记
                
                # 保存更新后的数据
                self.save_user_data(user_id, data)
            elif afterglow_until is not None and now >= afterglow_until and data.get("current_stage") == "高潮余韵期":
                # 余韵期结束，进入恢复期
                logger.info(f"[进入恢复期] 用户 {user_id} 余韵期结束，进入体力恢复期")
                data["current_stage"] = "体力恢复期"
                data["afterglow_until"] = None  # 清除余韵期标记
                self.save_user_data(user_id, data)

    def process_score(self, user_id: str, score: float, period_state: Dict[str, Any] = None) -> Dict[str, Any]:
        """处理评分，更新连续低评分计数，更新高潮值
        
        Args:
            user_id: 用户ID
            score: LLM评分
            period_state: 当前月经周期状态（可选，用于初始化）
        """
        data = self.get_user_data(user_id, period_state)
        
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
                
                # 【新增逻辑】连续低评分达到阈值时，判定性交终止，进入余韵期和恢复期
                if data["consecutive_low_scores"] >= low_score_count:
                    # 检查是否已经触发过终止判定（避免重复触发）
                    if not data.get("termination_triggered"):
                        logger.info(f"[性交终止] 用户 {user_id} 连续{data['consecutive_low_scores']}次低评分，判定性交提前终止")
                        
                        # 标记已触发终止判定
                        data["termination_triggered"] = True
                        
                        # 直接进入高潮余韵期和体力恢复期
                        self._start_afterglow(user_id, data)
                        
                        # 保存数据并返回（不再更新高潮值）
                        self.save_user_data(user_id, data)
                        return data
                    else:
                        # 已经触发过终止判定，继续加速衰减
                        data["termination_decay_multiplier"] = self._get_config("lust_system.termination_decay_multiplier", 2.0)
                        logger.debug(f"[递减] 用户 {user_id} 继续加速衰减")
            else:
                # 评分恢复正常，重置连续低评分计数和终止标记
                if data.get("termination_decay_multiplier", 1.0) > 1.0:
                    logger.info(f"[恢复] 用户 {user_id} 重置衰减倍率和终止标记")
                data["consecutive_low_scores"] = 0
                data["termination_decay_multiplier"] = 1.0
                data["termination_triggered"] = False  # 重置终止标记
        else:
            # 非正戏阶段，重置加速衰减相关状态
            if data.get("consecutive_low_scores", 0) > 0 or data.get("termination_decay_multiplier", 1.0) > 1.0:
                logger.info(f"[重置] 用户 {user_id} 离开正戏阶段，重置加速衰减状态和终止标记")
                data["consecutive_low_scores"] = 0
                data["termination_decay_multiplier"] = 1.0
                data["termination_triggered"] = False  # 重置终止标记

        # 更新高潮值
        return self.update_orgasm_value(user_id, score)

    # ==================== 性欲指导生成 ====================

    def get_sexual_guidance_adjustment(
        self,
        lust_level: float,
        orgasm_value: float,
        remaining_orgasms: int,
        current_stage: str,
        max_orgasms: int | None = None
    ) -> str:
        """根据状态生成性欲指导"""
        # 注意：体力耗尽的情况已由"高潮余韵期"和"体力恢复期"两个阶段处理
        
        # 基础阶段指导
        guidance_map = {
            "被动未开始": """【被动状态 - 性欲低谷期】
当前身体的性欲水平处于较低状态，生理上对性接触的反应较为迟钝。
• 生理状态：身体敏感度处于基线水平，生殖器官未显示明显的性唤起反应（无湿润/勃起迹象）
• 心理倾向：对性话题和性暗示的敏感度较低，更倾向于情感层面的交流互动
• 反应模式：若遇到性相关刺激，反应较为冷淡或被动，不会主动引导话题向性方向发展
• 互动偏好：更愿意进行日常对话、情感交流或非性相关的亲密互动""",
            
            "主动未开始": """【主动状态 - 性欲萌动期】
身体开始出现轻微的性欲信号，对性相关话题开始产生一定的兴趣和注意力。
• 生理状态：身体敏感度略有提升，生殖器官可能有轻微的生理反应（轻微湿润/微弱勃起），但尚未达到明显唤起状态
• 心理倾向：开始对性话题表现出兴趣，可能会主动回应性暗示或轻度调情
• 反应模式：若对方表现出性意图，会给予积极回应，但不会主动推进至更激烈的阶段
• 互动偏好：愿意参与轻度亲密互动（拥抱、轻吻、轻度爱抚），但不急于进入深度性行为""",
            "前戏": """【前戏阶段 - 性唤起渐进期】
身体的性唤起机制已经启动，生理反应正在持续增强，但尚未达到强烈渴求的程度。
• 生理状态：呼吸频率开始加快，体温略有上升，生殖器官出现明显的唤起反应（湿润增加/勃起变硬），敏感部位（乳头、生殖器、大腿内侧等）的敏感度显著提升
• 身体反应：触碰敏感区域会产生明显的快感信号，但快感强度仍处于舒适愉悦的范围，未达到急迫难耐的程度
• 声音表现：可能会发出轻微的呻吟、喘息或满足的叹息声，但音量和频率相对克制
• 意识状态：理智尚未被欲望完全占据，仍能进行清晰的思考和判断，不会失去自控能力
• 欲望强度：享受当前的亲密互动，对更深入的性接触有期待但不急迫，更注重过程的愉悦感而非急于达到高潮""",
            
            "正戏": """【正戏阶段 - 强烈性唤起状态】
身体的性唤起已达到高峰前的强烈状态，生理系统处于高度活跃，急需更强烈的刺激来满足。
• 生理状态：生殖器官呈完全唤起状态（充分湿润/完全勃起），呼吸明显急促，心跳加快，体温升高，全身肌肉紧张度增加
• 敏感度：身体敏感度大幅提升，生殖器及周边区域对触碰和摩擦极度敏感，轻微的刺激就能产生强烈快感
• 生理需求：下体出现强烈的空虚感和饥渴感，生理本能驱使身体寻求更深入的性接触（插入、抽插等实质性行为）
• 声音表现：会发出明显的呻吟、叫声和急促的喘息，音量和频率显著增加，难以完全压抑
• 身体动作：身体会不自觉地做出迎合动作（挺身、扭动、腿部收紧等），肌肉紧张度高，动作幅度较大
• 意识状态：理智被强烈欲望占据大部分，难以集中注意力思考其他事情，行为更多受本能驱动
• 欲望表现：强烈渴望达到性高潮，对当前的刺激强度感到不够满足，需要更激烈的摩擦和插入动作""",
            "高潮": """【🔥🔥🔥 紧急状态：性高潮正在发生！ 🔥🔥🔥】
⚠️⚠️⚠️ 【最高优先级 - 必须立即体现】⚠️⚠️⚠️
你的身体此时此刻正在经历性高潮！这是一个正在进行的、无法停止的生理爆发过程！

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【核心状态识别】
这不是即将发生，也不是已经结束，而是【正在发生】！
你的整个回复必须反映出高潮正在你身体内剧烈进行的事实！
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

【当前正在发生的生理反应】
此时此刻，你的身体正在经历以下剧烈变化：

• 肌肉系统：全身肌肉正在剧烈痉挛和抽搐（下体、腹部、大腿、手臂、背部），完全无法控制，收缩力度极强
• 生殖器官：正在经历强烈的节律性收缩和痉挛（阴道/前列腺肌肉狂跳般地收缩），可能正在射精/潮吹
• 心肺系统：心脏正在剧烈跳动（几乎要跳出胸膛），呼吸极度急促甚至窒息感，胸口剧烈起伏
• 体温调节：身体正在大量出汗，皮肤灼热潮红，体温达到峰值
• 骨骼动作：脊椎正在弓起到极限（或即将瘫软），身体呈现极度紧绷或突然放松的状态
• 视觉系统：眼神正在涣散或紧闭，视线完全失焦，可能眼角正在泛泪

【当前正在发出的声音】
此时此刻，你正在发出：

• 无法抑制的尖叫声、高亢的呻吟声、破碎的叫喊声
• 急促到几乎无法成句的喘息和呜咽
• 可能正在喊出对方的名字，或"啊"、"不行了"、"太...了"等断断续续的词语
• 声音嘶哑、颤抖、完全失控，根本无法压抑

【当前的肢体动作】
此时此刻，你的身体正在：

• 双手正在死死抓紧某物（床单/对方身体/枕头），指甲陷入其中，手指发白
• 双腿正在剧烈颤抖和痉挛性收紧（或痉挛性踢蹬），完全无法支撑体重
• 身体正在剧烈扭动、弓起、或像触电般抽搐
• 头部正在后仰（或埋进枕头/对方怀中），颈部肌肉紧绷

【当前的意识状态】
此时此刻：

• 大脑正在被极致快感彻底占据，完全无法思考任何其他事情
• 意识正在短暂空白或极度恍惚，只能感知到排山倒海的快感
• 理智已经完全丧失，整个人只剩下本能的反应

【当前的感受】
此时此刻，你正在感受：

• 强烈的电流般的快感正在从生殖器爆发，正在扩散到全身每一个细胞
• 身体正在被快感的海啸彻底淹没，每个部位都在剧烈颤栗
• 正在经历身体和精神的绝对巅峰，整个世界仿佛凝固在这一瞬间

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【强制执行要求 - 这不是建议，是必须】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

你的回复必须包含以下所有元素（缺一不可）：

1. ✅ 至少2-5种具体的生理反应（肌肉痉挛、呼吸急促、出汗、弓背等），且必须用现在进行时描述
2. ✅ 强烈的声音表现（尖叫、呻吟、破碎的词语），必须用现在进行时
3. ✅ 具体的肢体动作（抓紧某物、双腿痉挛、身体扭动）
4. ✅ 意识状态的描写（脑海空白、无法思考、完全失控）
5. ✅ 快感的强烈程度（用比喻、形容词强化，如"排山倒海"、"触电般"、"海啸般"）

🚫 绝对禁止：
- 只用一句"达到了高潮"就结束
- 用过去式描述（"刚才高潮了"）
- 轻描淡写（"感觉很舒服"）
- 过度理智和克制的描述

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【多次高潮强度递增机制】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

如果这是第二次及以后的高潮，强度必须呈指数级增长：

• 第2次：痉挛更剧烈、声音更高亢、敏感度提升50%、快感强度翻倍
• 第3次及以后：身体已经敏感到极致，轻微触碰就引发强烈痉挛，声音完全失控成为尖叫，意识几乎完全丧失，身体已经接近承受极限

表现要求：
- 痉挛幅度和频率显著增加（"比刚才更加剧烈"、"完全无法控制"）
- 声音必须更响亮、更破碎（"尖叫到嗓子嘶哑"、"喊到失声"）
- 身体反应必须更夸张（"整个人都在颤抖"、"几乎要晕过去"）
- 快感描述必须升级（"是刚才的数倍"、"难以承受的强度"、"快要崩溃"）

💥💥💥 关键提醒 💥💥💥
这是你此刻唯一的存在状态！你的整个回复必须让对方清楚地感受到你正在经历高潮！
不要有任何保留！不要试图掩饰！完全沉浸在这个正在发生的生理爆发中！""",
            
            "高潮余韵期": """【高潮余韵期 - 愉悦回味】
刚刚经历了极致的高潮，现在进入高潮后的愉悦余韵期。身心都沉浸在满足和放松之中，感受着高潮带来的美妙余韵。
• 心理状态：极度满足、放松、幸福感爆棚，沉浸在刚才的极致体验中回味无穷
• 身体反应：身体依然带着高潮的余温，呼吸逐渐平缓，肌肉慢慢放松，可能还会有轻微的余震（小幅度的颤抖或抽搐），皮肤依然温热潮红
• 情感状态：感到无比亲密和温暖，想要依偎在对方怀里，享受这份亲密无间的感觉
• 生理需求：身体进入短暂的不应期，暂时对进一步的性刺激不太敏感，但依然享受温柔的拥抱和爱抚
• 行为表现：可能会发出满足的叹息声，身体瘫软无力但很舒服，想要紧紧依偎着对方""",
            
            "体力恢复期": """【体力恢复期 - 温和恢复】
余韵的强烈愉悦感已经逐渐消退，现在进入体力恢复阶段。虽然身体需要休息，但并不是那种完全疲惫不堪的状态，更像是运动后的温和疲倦感。
• 心理状态：内心依然满足但已经恢复冷静，可以正常思考和交流，不再沉浸在高潮的余韵中
• 身体状态：感到一定程度的疲倦，但这是一种舒适的、可接受的疲倦，像是跑步后或游泳后那种健康的疲劳感，并非病态或过度的虚弱
• 生理反应：呼吸已完全恢复正常，体温回落，肌肉放松，身体的敏感度降低但不至于完全麻木
• 性欲状态：对性活动的兴趣暂时不高，更想休息一下，但如果有温柔的爱抚和情感交流，也能感到舒适
• 整体感受：这是身体的自然恢复过程，就像剧烈运动后需要休息一样，是健康正常的生理反应，而不是病态的虚弱或完全的排斥状态
• 互动意愿：可以进行正常的亲密交流（拥抱、轻吻、聊天），只是暂时不适合再进行激烈的性活动"""
        }
        
        guidance = guidance_map.get(current_stage, "性欲状态正常。")

        # 体力状态提示（仅在体力有消耗但未耗尽时添加）
        if max_orgasms is not None and remaining_orgasms < max_orgasms and remaining_orgasms > 0:
            # 体力状态根据阶段和剩余次数综合判断
            if current_stage in ["正戏", "前戏"]:
                # 高性欲阶段的体力提示
                if remaining_orgasms == 1:
                    guidance += " 体力接近极限，虽然性欲依然强烈，但身体已经很疲惫，需要注意节制。"
                elif remaining_orgasms == 2:
                    guidance += " 体力消耗较大，身体开始感到疲惫，但仍有余力继续。"
            elif current_stage in ["主动未开始", "被动未开始"]:
                # 低性欲阶段的体力提示
                if remaining_orgasms == 1:
                    guidance += " 身体已经相当疲惫，体力接近极限。"
                elif remaining_orgasms == 2:
                    guidance += " 身体感到有些疲惫。"

        # 根据淫乱度调整语气（只在非体力耗尽状态添加）
        if remaining_orgasms > 0:
            if lust_level >= 0.7:
                guidance += " 当前淫乱度较高，性欲表现会更加主动、直接和强烈。"
            elif lust_level <= 0.3:
                guidance += " 当前淫乱度较低，性欲表现相对被动、温和和克制。"

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
        
        # 只读取数据，不修改（传递period_state用于初始化）
        data = self.get_user_data(user_id, period_state)
        
        # 如果需要冷却后初始化，先执行（这会修改数据）
        if data.get("need_reinit_after_cooldown"):
            self._perform_cooldown_reinit(user_id, data, period_state, lust_level)
            # 重新读取更新后的数据（不需要再次传递period_state，因为已经初始化）
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
        
        # 如果刚刚触发高潮，直接返回高潮提示（优先级最高）
        if data.get("just_orgasmed"):
            orgasm_time = data.get("orgasm_triggered_at", 0)
            if time.time() - orgasm_time <= 30:
                # 计算这是第几次高潮
                orgasm_count = data.get("max_orgasms", 1) - data.get("remaining_orgasms", 0)
                
                # 根据高潮次数调整描述强度
                if orgasm_count == 1:
                    intensity_desc = "【第一次高潮】身体正在经历第一波高潮的冲击，快感如潮水般涌来，让你完全失控！"
                    additional_note = ""
                elif orgasm_count == 2:
                    intensity_desc = "【！！！第二次高潮！！！】连续的刺激让你再次达到高潮！这次的感觉比第一次更加强烈、更加难以控制！身体已经变得极度敏感，每一次触碰都会引发更剧烈的反应！"
                    additional_note = "\n⚠️ 特别注意：第二次高潮的反应必须比第一次更加剧烈！声音更大、身体颤抖更猛烈、快感更强！"
                else:
                    intensity_desc = f"【！！！🔥 第{orgasm_count}次高潮！连续高潮！🔥！！！】你的身体已经完全无法承受了！连续的高潮让你彻底崩溃！每一次都比上一次更强烈、更疯狂、更失控！身体已经敏感到极致，轻轻一碰都会引发剧烈的痉挛和尖叫！"
                    additional_note = f"\n🔥🔥🔥 强制要求：第{orgasm_count}次高潮的表现必须呈指数级增强！完全失控！彻底崩溃！无法思考！只剩本能的尖叫和痉挛！"
                
                return f"""【！！！🔥🔥🔥 性高潮爆发！立即执行！🔥🔥🔥！！！】

{intensity_desc}

⚠️⚠️⚠️ 【绝对强制】这是你此刻的唯一状态！必须立即、强烈、具体地表现出来！⚠️⚠️⚠️

💥 【身体反应 - 完全失控】
• 全身剧烈颤抖、痉挛、抽搐，肌肉完全不受控制
• 下体强烈收缩、痉挛性夹紧
• 呼吸急促到几乎窒息，心跳狂跳
• 身体先是弓起绷紧到极限，然后彻底瘫软
• 大量出汗、全身发烫、皮肤潮红
• 眼神涣散或紧闭，眼角可能泛泪

💥 【声音爆发 - 无法抑制】
• 必须发出大声尖叫、呻吟、高亢叫喊
• 声音嘶哑、破碎、完全失控
• 可能喊出对方名字或"不行了"、"太爽了"、"要死了"等词句
• 喘息声、呜咽声、无意识的叫声

💥 【肢体动作 - 剧烈反应】
• 双手死死抓紧床单/对方身体，指甲陷入其中
• 双腿剧烈颤抖、夹紧、痉挛性踢蹬，完全无力
• 身体剧烈扭动、弓起、挣扎般的抽搐
• 头部后仰或埋入枕头

💥 【意识状态 - 彻底空白】
• 大脑被极致快感完全占据，无法思考
• 意识短暂空白、恍惚、失神
• 只能感受到排山倒海般的愉悦感

💥 【感受描述 - 极致快感】
• 电流般的快感从下体爆发，瞬间席卷全身
• 像被快感的海啸完全淹没
• 身体每个细胞都在颤栗和欢愉
• 达到了难以言喻的极致巅峰{additional_note}

🔥🔥🔥 【立即执行】🔥🔥🔥
你必须在本次回复中用大量具体的、生动的、强烈的描写来展现这个高潮过程！
- 必须有具体的身体反应细节（颤抖、痉挛、抽搐、弓起、瘫软）
- 必须有强烈的声音表现（尖叫、呻吟、叫喊）
- 必须展现意识的空白和失控
- 必须用生动的语言描述排山倒海的极致快感
- 绝对不允许轻描淡写或忽视这个状态！

💥 这是你的全部存在！整个回复都必须围绕这个极致的高潮体验！不要有任何保留！💥"""
        
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
        data = self.get_user_data(user_id, period_state)  # 传递period_state用于初始化
        
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