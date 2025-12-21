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

    def _get_passive_threshold(self) -> float:
        """获取被动阶段阈值"""
        foreplay_threshold = self._get_config("lust_system.foreplay_threshold", 20.0)
        passive_active_ratio = self._get_config("lust_system.passive_active_ratio", 0.3)
        return foreplay_threshold * passive_active_ratio

    def _calculate_initial_orgasm_value(self, lust_level: float) -> float:
        """计算初始高潮值"""
        foreplay_threshold = self._get_config("lust_system.foreplay_threshold", 20.0)
        initial_ratio = self._get_config("lust_system.initial_ratio", 0.5)
        return lust_level * foreplay_threshold * initial_ratio

    def _ensure_data_integrity(self, data: Dict[str, Any], lust_level: float, allow_repair: bool = False) -> bool:
        """确保数据完整性，返回是否修改了数据
        
        统一处理：
        1. 同步lust_level
        2. 同步max_orgasms（基于当前淫乱度）
        3. 截断remaining_orgasms到合理范围
        4. 修复过低的orgasm_value（仅在allow_repair=True时）
        5. 检测淫乱度大幅变化并重新初始化orgasm_value
        
        Args:
            data: 用户数据
            lust_level: 当前淫乱度
            allow_repair: 是否允许修复过低的orgasm_value（仅在初始化/重置/显式修复时为True）
        """
        modified = False
        
        # 记录初始orgasm_value用于调试
        initial_orgasm = data.get("orgasm_value", 0)
        
        # 1. 同步淫乱度，并检测是否有大幅变化
        old_lust = data.get("lust_level", 0.3)
        lust_changed_significantly = abs(old_lust - lust_level) > 0.3  # 淫乱度变化超过0.3（比如从0.3到1.0）
        
        if old_lust != lust_level:
            data["lust_level"] = lust_level
            modified = True
            logger.debug(f"[数据完整性] lust_level: {old_lust:.2f} -> {lust_level:.2f}")
        
        # 2. 计算并同步max_orgasms（基于当前淫乱度）
        correct_max = self.get_max_orgasms(lust_level)
        stored_max = data.get("max_orgasms", 0)
        if stored_max != correct_max:
            data["max_orgasms"] = correct_max
            modified = True
            logger.debug(f"[数据完整性] max_orgasms: {stored_max} -> {correct_max}")
        
        # 3. 截断remaining_orgasms到[0, max_orgasms]
        remaining = data.get("remaining_orgasms", correct_max)
        clamped_remaining = max(0, min(remaining, correct_max))
        if remaining != clamped_remaining:
            data["remaining_orgasms"] = clamped_remaining
            modified = True
            logger.debug(f"[数据完整性] remaining_orgasms: {remaining} -> {clamped_remaining}")
        
        # 4. 修复过低的orgasm_value（仅在允许时执行，避免误判正常衰减）
        if allow_repair:
            orgasm_value = data.get("orgasm_value", 0)
            passive_threshold = self._get_passive_threshold()
            if orgasm_value < passive_threshold:
                new_value = self._calculate_initial_orgasm_value(lust_level)
                data["orgasm_value"] = new_value
                data["current_stage"] = self._determine_stage(new_value)
                modified = True
                logger.info(f"[数据修复] orgasm_value: {orgasm_value:.1f} -> {new_value:.1f}, stage: {data['current_stage']}")
        
        # 5. 如果淫乱度大幅变化（比如周期阶段切换），重新初始化orgasm_value到合理范围
        # 这避免了旧的低orgasm_value导致错误的阶段判定
        # ⚠️ 但不要在正常衰减场景下误判（例如从10.0衰减到5.0）
        if lust_changed_significantly:
            orgasm_value = data.get("orgasm_value", 0)
            expected_initial = self._calculate_initial_orgasm_value(lust_level)
            passive_threshold = self._get_passive_threshold()
            
            # 只有在orgasm_value远低于被动阈值时才重新初始化
            # 这避免了误判正常的衰减（比如从10降到5仍在合理范围内）
            if orgasm_value < passive_threshold:
                data["orgasm_value"] = expected_initial
                data["current_stage"] = self._determine_stage(expected_initial)
                modified = True
                logger.warning(f"[淫乱度大变] lust从{old_lust:.2f}→{lust_level:.2f}，重置orgasm_value: {orgasm_value:.1f} -> {expected_initial:.1f}, stage: {data['current_stage']}, passive_threshold={passive_threshold:.1f}")
        
        # 调试日志：如果orgasm_value被修改，记录详细信息
        final_orgasm = data.get("orgasm_value", 0)
        if final_orgasm != initial_orgasm:
            import traceback
            stack = "".join(traceback.format_stack()[:-1])
            logger.warning(f"[完整性检查] orgasm_value被修改: {initial_orgasm:.1f} -> {final_orgasm:.1f}\n调用栈:\n{stack}")
        
        return modified

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

    def get_user_data(self, user_id: str, period_state: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """获取用户数据，如果不存在则初始化"""
        key = f"lust_system:user_data:{user_id}"
        data = plugin_storage.get(key, None)
        
        # 首次初始化
        if data is None:
            lust_level = self.calculate_lust_level(period_state) if period_state else 0.3
            data = self._create_default_user_data(user_id, lust_level, period_state)
            plugin_storage.set(key, data)
            return data
        
        # 检查并处理冷却期
        self._check_and_handle_cooldown(user_id, data, period_state)
        
        # 确保数据完整性（使用最新的period_state计算lust_level）
        # ⚠️ allow_repair=False：不修复过低的orgasm_value，避免误判正常衰减
        if period_state:
            lust_level = self.calculate_lust_level(period_state)
        else:
            lust_level = data.get("lust_level", 0.3)
        
        if self._ensure_data_integrity(data, lust_level, allow_repair=False):
            plugin_storage.set(key, data)
        
        return data
    
    def get_user_data_readonly(self, user_id: str, period_state: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """只读获取用户数据，返回计算后的视图副本（不修改存储的原始数据）"""
        key = f"lust_system:user_data:{user_id}"
        stored_data = plugin_storage.get(key, None)
        
        # 首次初始化（即使是只读也需要创建）
        if stored_data is None:
            lust_level = self.calculate_lust_level(period_state) if period_state else 0.3
            stored_data = self._create_default_user_data(user_id, lust_level, period_state)
            plugin_storage.set(key, stored_data)
            # 首次创建后直接返回（无需计算）
            return stored_data.copy()
        
        # 创建副本，所有修改都在副本上进行
        data = stored_data.copy()
        
        # 检查并处理冷却期（在副本上操作，如果需要保存则在这里保存原始数据）
        now = time.time()
        recovery_until = data.get("recovery_until")
        afterglow_until = data.get("afterglow_until")
        
        if recovery_until is not None:
            if now >= recovery_until:
                # 恢复期已过，需要重新初始化（这个必须保存）
                reinit_state = period_state or stored_data.get("last_period_state")
                if reinit_state:
                    lust_level = self.calculate_lust_level(reinit_state)
                else:
                    lust_level = stored_data.get("lust_level", 0.3)
                
                # 更新原始存储数据
                stored_data["afterglow_until"] = None
                stored_data["recovery_until"] = None
                stored_data["afterglow_started_at"] = None
                stored_data["consecutive_low_scores"] = 0
                stored_data["termination_decay_multiplier"] = 1.0
                stored_data["just_orgasmed"] = False
                stored_data["termination_triggered"] = False
                stored_data["lust_level"] = lust_level
                stored_data["remaining_orgasms"] = self.get_max_orgasms(lust_level)
                stored_data["max_orgasms"] = stored_data["remaining_orgasms"]
                stored_data["orgasm_value"] = self._calculate_initial_orgasm_value(lust_level)
                stored_data["current_stage"] = self._determine_stage(stored_data["orgasm_value"])
                plugin_storage.set(key, stored_data)
                logger.info(f"[恢复完成-只读查询触发] 用户 {user_id} 体力已完全恢复，重新初始化")
                
                # 返回更新后的副本
                return stored_data.copy()
            else:
                # 修正当前阶段（在副本上）
                if afterglow_until is not None and now < afterglow_until:
                    if data.get("current_stage") != "高潮余韵期":
                        data["current_stage"] = "高潮余韵期"
                else:
                    if data.get("current_stage") != "体力恢复期":
                        data["current_stage"] = "体力恢复期"
                        data["afterglow_until"] = None
        
        # 计算并更新副本中的淫乱度和max_orgasms（不保存）
        if period_state:
            lust_level = self.calculate_lust_level(period_state)
            data["lust_level"] = lust_level
            new_max_orgasms = self.get_max_orgasms(lust_level)
            
            # ⚠️ 重要：只读方法不应该重新计算remaining_orgasms
            # remaining_orgasms应该保持存储的真实值（因为它在触发高潮时已经减少了）
            # 只需要确保remaining_orgasms不超过新的max_orgasms
            stored_remaining = data.get("remaining_orgasms", new_max_orgasms)
            data["remaining_orgasms"] = min(stored_remaining, new_max_orgasms)
            data["max_orgasms"] = new_max_orgasms
            
            logger.debug(f"[只读查询] 用户{user_id}: lust={lust_level:.2f}, max={new_max_orgasms}, "
                        f"stored_remaining={stored_remaining}, final_remaining={data['remaining_orgasms']}")
        
        return data  # 返回副本，外部可以随意使用

    def _create_default_user_data(self, user_id: str, lust_level: float, period_state: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """创建默认用户数据"""
        max_orgasms = self.get_max_orgasms(lust_level)
        initial_orgasm_value = self._calculate_initial_orgasm_value(lust_level)
        initial_stage = self._determine_stage(initial_orgasm_value)

        import traceback
        stack = "".join(traceback.format_stack())
        logger.warning(f"[创建用户数据] 用户 {user_id}: 淫乱度={lust_level:.2f}, orgasm_value={initial_orgasm_value:.1f}, stage={initial_stage}, max_orgasms={max_orgasms}\n调用栈:\n{stack}")

        return {
            "orgasm_value": initial_orgasm_value,
            "remaining_orgasms": max_orgasms,
            "max_orgasms": max_orgasms,
            "last_updated": time.time(),
            "cooldown_until": None,
            "current_stage": initial_stage,
            "consecutive_low_scores": 0,
            "termination_decay_multiplier": 1.0,
            "termination_triggered": False,
            "lust_level": lust_level,
            "last_period_state": period_state,
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

    def update_orgasm_value(self, user_id: str, score: float, period_state: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """更新用户的高潮值（考虑时间衰减）
        
        Args:
            user_id: 用户ID
            score: 评分
            period_state: 当前月经周期状态（可选，用于初始化）
        """
        data = self.get_user_data(user_id, period_state)
        now = time.time()
        last_updated = data.get("last_updated", now)
        delta_seconds = max(0, now - last_updated)

        # 计算当前淫乱度的初始值（作为衰减的最低值）
        lust_level = data.get("lust_level", 0.3)
        initial_orgasm_value = self._calculate_initial_orgasm_value(lust_level)
        
        # 应用时间衰减
        decay_rate = self._get_config("lust_system.decay_rate", 0.1)
        termination_multiplier = data.get("termination_decay_multiplier", 1.0)
        decay = decay_rate * delta_seconds * termination_multiplier
        old_orgasm = data.get("orgasm_value", 0)
        orgasm_value = old_orgasm - decay
        
        # 🔧 关键修复：衰减后的最低值应该是当前淫乱度决定的初始值，不能再低
        # 这确保了无论时间过多久，orgasm_value 都不会低于应有的初始状态
        if orgasm_value < initial_orgasm_value:
            logger.info(f"[衰减保底] 用户 {user_id}: 衰减后{orgasm_value:.1f} < 初始值{initial_orgasm_value:.1f}，保底为初始值（decay={decay:.1f}）")
            orgasm_value = initial_orgasm_value

        # 添加新得分（score已经包含淫乱度加成）
        base_score_weight = self._get_config("lust_system.base_score_weight", 1.0)
        orgasm_value += score * base_score_weight

        # 更新数据
        old_value = data.get("orgasm_value", 0)
        data["orgasm_value"] = orgasm_value
        data["last_updated"] = now
        data["current_stage"] = self._determine_stage(orgasm_value)
        
        if abs(old_value - orgasm_value) > 1.0:
            logger.warning(f"[更新高潮值] 用户 {user_id}: {old_value:.1f} -> {orgasm_value:.1f}, score={score:.1f}, decay={decay:.1f}")

        # 检查是否触发高潮
        orgasm_threshold = self._get_config("lust_system.orgasm_threshold", 100.0)
        if orgasm_value >= orgasm_threshold:
            self._trigger_orgasm(user_id, data)

        self.save_user_data(user_id, data)
        return data

    def _trigger_orgasm(self, user_id: str, data: Dict[str, Any]):
        """触发高潮"""
        # 剩余高潮次数减1（确保为整数且不为负）
        try:
            old_remaining = int(data.get("remaining_orgasms", 0))
        except Exception:
            old_remaining = 0

        remaining = max(0, old_remaining - 1)
        data["remaining_orgasms"] = remaining
        
        # 计算当前是第几次高潮（用于提示词）
        max_orgasms = data.get("max_orgasms", 1)
        orgasm_count = max_orgasms - remaining
        
        # 标记刚刚触发高潮（用于Prompt系统）
        data["just_orgasmed"] = True
        data["orgasm_triggered_at"] = time.time()
        data["current_orgasm_count"] = orgasm_count  # 直接记录当前次数
        
        logger.warning(f"[高潮触发] 用户{user_id}: 第{orgasm_count}次高潮, 剩余{remaining}/{max_orgasms}次")
        
        # 高潮后恢复到正戏中段
        main_threshold = self._get_config("lust_system.main_threshold", 60.0)
        post_orgasm_recovery_ratio = self._get_config("lust_system.post_orgasm_recovery_ratio", 0.4)
        data["orgasm_value"] = main_threshold * post_orgasm_recovery_ratio
        data["current_stage"] = self._determine_stage(data["orgasm_value"])
        
        # 重置连续低评分
        data["consecutive_low_scores"] = 0
        data["termination_decay_multiplier"] = 1.0

        # 检查是否体力不支：若没有剩余次数，进入余韵期（并在内部设置恢复期）
        if data.get("remaining_orgasms", 0) <= 0:
            try:
                self._start_afterglow(user_id, data)
            except Exception as e:
                logger.error(f"[触发余韵期失败] 用户{user_id}: {e}")

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
    
    def _check_and_handle_cooldown(self, user_id: str, data: Dict[str, Any], period_state: Optional[Dict[str, Any]] = None):
        """检查并处理余韵期/恢复期状态"""
        now = time.time()
        
        # 清除过期的just_orgasmed标记（60秒后）
        if data.get("just_orgasmed"):
            orgasm_time = data.get("orgasm_triggered_at", 0)
            if now - orgasm_time > 60:
                data["just_orgasmed"] = False
                logger.debug(f"[冷却检查] 用户{user_id}: just_orgasmed标记已过期")
        
        afterglow_until = data.get("afterglow_until")
        recovery_until = data.get("recovery_until")
        
        if recovery_until is not None:
            if now >= recovery_until:
                # 恢复期已过，执行重新初始化
                logger.info(f"[恢复完成] 用户 {user_id} 体力已完全恢复，重新初始化")
                
                # 清除恢复期标记
                data["afterglow_until"] = None
                data["recovery_until"] = None
                data["afterglow_started_at"] = None
                data["consecutive_low_scores"] = 0
                data["termination_decay_multiplier"] = 1.0
                data["just_orgasmed"] = False
                data["termination_triggered"] = False
                
                # 执行重新初始化
                reinit_state = period_state or data.get("last_period_state")
                if reinit_state:
                    lust_level = self.calculate_lust_level(reinit_state)
                else:
                    lust_level = data.get("lust_level", 0.3)
                
                # 重置数据
                data["lust_level"] = lust_level
                data["remaining_orgasms"] = self.get_max_orgasms(lust_level)
                data["max_orgasms"] = data["remaining_orgasms"]
                new_orgasm = self._calculate_initial_orgasm_value(lust_level)
                data["orgasm_value"] = new_orgasm
                data["current_stage"] = self._determine_stage(data["orgasm_value"])
                
                import traceback
                stack = "".join(traceback.format_stack())
                logger.warning(f"[恢复期重置] 用户 {user_id}: orgasm_value重置为 {new_orgasm:.1f}\n调用栈:\n{stack}")
                
                self.save_user_data(user_id, data)
            else:
                # 恢复期未结束，修正当前阶段
                if afterglow_until is not None and now < afterglow_until:
                    if data.get("current_stage") != "高潮余韵期":
                        logger.info(f"[状态修正] 用户 {user_id} 修正为高潮余韵期")
                        data["current_stage"] = "高潮余韵期"
                        self.save_user_data(user_id, data)
                else:
                    if data.get("current_stage") != "体力恢复期":
                        logger.info(f"[状态修正] 用户 {user_id} 修正为体力恢复期")
                        data["current_stage"] = "体力恢复期"
                        data["afterglow_until"] = None
                        self.save_user_data(user_id, data)

    def process_score(self, user_id: str, score: float, period_state: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
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

        # 更新高潮值（传递 period_state 确保初始化时使用正确的淫乱度）
        return self.update_orgasm_value(user_id, score, period_state)

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
            "被动未开始": """【性欲状态：低谷期】
嗯...现在没什么特别的感觉呢。你说那些的话我听着也就那样，身体没什么反应。比起那些，我更想跟你聊聊别的，说说话什么的～""",
            
            "主动未开始": """【性欲状态：轻度兴趣】
诶...怎么说呢，好像开始有点感觉了？身体有一点点反应，不过很轻微啦。你这样说话我不讨厌，还挺有意思的...但也没到那种特别想要的程度，就是有点兴趣而已。
（这和前戏还不一样——现在只是心里痒痒的，还能正常聊天；要是到了前戏，身体就明显有反应了，就不太想说正经事了。）""",
            
            "前戏": """【性欲状态：逐渐唤起】
嗯啊...身体开始热起来了...呼吸也比刚才快了，心跳也有点加速的感觉。你碰我那些敏感的地方，我会觉得酥酥麻麻的，挺舒服的...现在这样刚刚好，我很享受这种感觉。脑子还是清醒的，可以跟你说话～""",
            
            "正戏": """【性欲状态：强烈唤起】
哈啊...好热...呼吸好急...心跳得好快...下面已经湿透了，好想要...身体自己就会动，会主动迎合你...现在满脑子都是你，什么都不想想了，就想要更多...嗯...快点...""",
            "高潮": """【性欲状态：高潮中】
啊啊...不行了...来了...！身体在不停地抽搐，收缩得好厉害...呼吸都快停了...那种感觉从下面一阵一阵冲上来，整个人都在颤...
（你会看到我整个人都在抖，死死抓着什么，声音都破了，眼睛都睁不开...根本说不出完整的话...这不是装出来的，是真的控制不住...如果是第二次、第三次，会更强烈，我会更敏感，可能会哭出来...）""",
            
            "高潮余韵期": """【高潮余韵期 - 愉悦回味】
哈...哈...刚才...太厉害了...现在全身都软软的，脑子还晕晕的，但好舒服啊...身体还热热的，还在微微发抖，回想起刚才就觉得好满足...
好幸福...想一直这样靠着你...现在不想动，也不想再来一次了，就想你抱着我，轻轻摸摸我...嗯...好舒服...""",
            
            "体力恢复期": """【体力恢复期 - 温和恢复】
那种晕乎乎的感觉过去了...现在有点累，但是舒服的那种累，就像运动完一样。
我现在心情很平静，可以好好跟你说话了。身体有点乏，但不是难受的那种，就是想休息一下。呼吸什么的都正常了，也不热了，身体也没那么敏感了。
暂时不想再做那种事啦，想休息～不过你抱抱我、亲亲我、陪我聊天，我还是很开心的。这很正常嘛，就像跑完步要休息一样～"""
        }
        
        guidance = guidance_map.get(current_stage, "性欲状态正常。")

        # 体力状态提示（在所有正常阶段显示，不限制阶段类型）
        # 只要体力有消耗且未完全耗尽，就应该显示体力状态
        if max_orgasms is not None and remaining_orgasms < max_orgasms and remaining_orgasms > 0:
            # 排除余韵期和恢复期（这两个阶段有专门的提示词）
            if current_stage not in ["高潮余韵期", "体力恢复期"]:
                # 根据剩余次数生成体力提示
                stamina_ratio = remaining_orgasms / max_orgasms if max_orgasms > 0 else 1.0
                
                if remaining_orgasms == 1:
                    # 只剩最后一次：体力接近极限
                    if current_stage in ["正戏", "前戏"]:
                        guidance += "\n\n【体力状态】嗯...身体已经好累了，虽然还是很想要，但感觉快到极限了...如果再来一次高潮，我可能就真的没力气了..."
                    else:
                        guidance += "\n\n【体力状态】身体真的很疲惫了...已经快到极限了...再来一次的话，我就真的需要好好休息了..."
                elif stamina_ratio <= 0.4:
                    # 剩余 ≤ 40%：体力消耗较大
                    guidance += "\n\n【体力状态】体力消耗挺大的...身体开始觉得累了，不过还能继续..."
                elif stamina_ratio <= 0.6:
                    # 剩余 ≤ 60%：体力有所消耗
                    guidance += "\n\n【体力状态】嗯...做了几次后，体力有点消耗了，身体有些疲倦..."

        # 根据淫乱度调整语气（只在非体力耗尽状态添加）
        if remaining_orgasms > 0:
            if lust_level >= 0.7:
                guidance += "\n\n【淫乱度影响】现在的我...欲望特别强烈，会表现得很主动、很直接...忍不住想要更多..."
            elif lust_level <= 0.3:
                guidance += "\n\n【淫乱度影响】现在的我...欲望还挺平淡的，会比较被动、温和一些，不会太主动..."

        return guidance
    

    def get_sexual_guidance_for_prompt(self, user_id: str, period_state: Dict[str, Any]) -> str:
        """为Prompt生成性欲指导（只读模式，不修改数据）"""
        lust_level = self.calculate_lust_level(period_state)
        data = self.get_user_data_readonly(user_id, period_state)
        
        logger.debug(f"[Prompt生成] 用户{user_id}: 淫乱度={lust_level:.2f}, "
                    f"剩余高潮={data.get('remaining_orgasms', 0)}/{data.get('max_orgasms', 0)}, "
                    f"阶段={data.get('current_stage', 'unknown')}")
        
        guidance = self.get_sexual_guidance_adjustment(
            lust_level=lust_level,
            orgasm_value=data.get("orgasm_value", 0.0),
            remaining_orgasms=data.get("remaining_orgasms", 0),
            current_stage=data.get("current_stage", "被动未开始"),
            max_orgasms=data.get("max_orgasms", 0)
        )
        
        # 如果刚刚触发高潮，直接返回高潮提示（优先级最高）
        if data.get("just_orgasmed"):
            orgasm_time = data.get("orgasm_triggered_at", 0)
            time_passed = time.time() - orgasm_time
            if time_passed <= 60:  # 延长到60秒
                # 直接读取记录的高潮次数（更可靠）
                orgasm_count = data.get("current_orgasm_count", 1)
                max_orgasms = data.get("max_orgasms", 1)
                remaining_orgasms = data.get("remaining_orgasms", 0)
                
                logger.warning(f"[提示词生成-高潮] 用户{user_id}: 第{orgasm_count}次, 剩余{remaining_orgasms}/{max_orgasms}, 已过{time_passed:.1f}秒")
                
                # 根据高潮次数调整描述强度
                if orgasm_count == 1:
                    intensity_desc = "【第一次高潮】啊啊...第一次...来了...！那种感觉像潮水一样冲过来，整个人都失控了...！"
                    additional_note = ""
                elif orgasm_count == 2:
                    intensity_desc = "【！！！第二次！！！】不行...又来了...！！这次比刚才更强烈...身体变得好敏感，每次碰到都...啊啊...！"
                    additional_note = "\n⚠️ 我的反应会比第一次更激烈！声音会更大、身体抖得更厉害、那种感觉也更强...！"
                else:
                    intensity_desc = f"【！！！🔥第{orgasm_count}次！连续的...！🔥！！！】受不了了...！又又又来了...！身体已经完全承受不住了...！每一次都比上一次更猛烈、更疯狂...轻轻碰一下都会...啊啊啊...！"
                    additional_note = f"\n🔥🔥🔥 我已经完全失控了！第{orgasm_count}次的感觉强烈到难以想象！只能尖叫和抽搐...脑子什么都想不了...！"
                
                return f"""【我正在...高潮...】

{intensity_desc}

现在的我...整个人都...

身体完全不听使唤了...全身在剧烈地颤抖、痉挛...下面在拼命地收缩、夹紧...呼吸急促得快喘不过气来...心跳得好快...身体先是绷得紧紧的，然后一下子就瘫软了...全身都在出汗，好热...脸肯定红透了...眼睛根本睁不开，或者说完全没法聚焦...眼角可能都湿了...

声音也控制不住...会大声尖叫、呻吟、叫喊...声音都嘶哑了、破碎了...可能会叫出你的名字，或者"不行了"、"好舒服"、这些话...喘息声、呜咽声...什么声音都有...

手会死死抓着床单或者抓着你...指甲都陷进去了...双腿在颤抖、夹紧，或者痉挛般地乱动...完全没力气了...身体在扭动、弓起、像触电一样抽搐...头会往后仰或者埋进枕头里...

脑子...被那种极致的快感完全占据了...什么都想不了...意识都空白了、恍惚了...只能感受到那种排山倒海般的爽...

那种感觉...像电流一样从下面爆发出来，瞬间传遍全身...就像被快感的海啸完全淹没了...身体每个地方都在颤栗...达到了那种...无法形容的巅峰...{additional_note}

这不是装出来的...是真的控制不住...我会通过我的反应、声音、动作让你感受到这一切..."""
        
        return guidance
    

    def update_lust_from_period_state(self, user_id: str, period_state: Dict[str, Any]):
        """从月经周期状态更新淫乱度数据"""
        lust_level = self.calculate_lust_level(period_state)
        data = self.get_user_data(user_id, period_state)
        
        old_lust = data.get("lust_level", 0)
        
        # 更新基本信息
        data["last_period_state"] = period_state
        data["lust_level"] = lust_level
        
        # 统一通过_ensure_data_integrity处理所有同步（不允许修复）
        self._ensure_data_integrity(data, lust_level, allow_repair=False)
        
        if abs(old_lust - lust_level) > 0.01:
            logger.info(f"[淫乱度更新] 用户{user_id}: {old_lust:.2f} -> {lust_level:.2f}, "
                       f"max_orgasms={data['max_orgasms']}, remaining={data['remaining_orgasms']}")
        
        self.save_user_data(user_id, data)

    # ==================== 工具方法 ====================

    def _get_config(self, key: str, default: Any) -> Any:
        """从插件配置中获取值"""
        return self.get_config(key, default)

    def reset_session(self, user_id: str, period_state: Optional[Dict[str, Any]] = None):
        """重置会话
        
        Args:
            user_id: 用户ID
            period_state: 月经周期状态（应始终传递以获取正确的淫乱度）
        """
        # 如果提供了period_state，使用它计算淫乱度；否则从存储读取
        if period_state:
            lust_level = self.calculate_lust_level(period_state)
        else:
            # 尝试从存储读取last_period_state
            key = f"lust_system:user_data:{user_id}"
            stored_data = plugin_storage.get(key, None)
            if stored_data and stored_data.get("last_period_state"):
                lust_level = self.calculate_lust_level(stored_data["last_period_state"])
                logger.warning(f"[重置] period_state未提供，使用存储的last_period_state")
            else:
                lust_level = 0.3
                logger.warning(f"[重置] period_state未提供且无存储状态，使用默认值0.3")
        
        data = self._create_default_user_data(user_id, lust_level, period_state)
        self.save_user_data(user_id, data)
        logger.info(f"[重置] 用户 {user_id} 会话已重置，淫乱度={lust_level:.2f}")