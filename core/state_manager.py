from typing import Dict, Any, Tuple, Optional
from datetime import datetime, timedelta
from calendar import monthrange
import random
from src.plugin_system.apis import storage_api
from src.common.logger import get_logger

logger = get_logger("mofox_period_plugin")

# 获取插件的本地存储实例
plugin_storage = storage_api.get_local_storage("mofox_period_plugin")


# ============================================================================
# 提示词模板系统
# ============================================================================

class PromptTemplates:
    """提示词模板系统 - 客观中性的等级描述"""
    
    # 生理影响等级提示词（1-10）- 客观描述
    PHYSICAL_TEMPLATES = {
        1: "身体状态良好，精力充沛。",
        2: "身体状态正常，偶有轻微疲惫。",
        3: "有轻度疲劳感，腰腹略有不适。",
        4: "感到较明显的疲劳，腰腹有酸痛感。",
        5: "疲劳感较强，腰腹持续不适，需要更多休息。",
        6: "疲劳明显，身体较为沉重，活动意愿降低。",
        7: "疲劳严重，身体不适感强烈，倾向卧床休息。",
        8: "身体极度疲惫，明显不适，活动困难。",
        9: "身体状况很差，严重不适。",
        10: "身体状况极差，需要医疗关注。"
    }
    
    # 心理影响等级提示词（1-10）- 客观描述
    PSYCHOLOGICAL_TEMPLATES = {
        1: "情绪稳定，心情平和。",
        2: "情绪基本稳定，偶有小波动。",
        3: "情绪略有波动，对事物较为敏感。",
        4: "情绪波动明显，耐心有所下降。",
        5: "情绪不太稳定，容易受影响。",
        6: "情绪波动较大，较为敏感易怒。",
        7: "情绪很不稳定，控制力下降。",
        8: "情绪控制困难，波动剧烈。",
        9: "情绪极不稳定，需要更多理解。",
        10: "情绪状态很差，需要特别关注。"
    }
    
    # 痛经等级提示词（0-10）- 客观描述
    DYSMENORRHEA_TEMPLATES = {
        0: "无痛经症状。",
        1: "有非常轻微的下腹不适。",
        2: "有轻微的下腹疼痛感。",
        3: "下腹有轻度疼痛，略感不适。",
        4: "下腹疼痛较明显，需要注意休息。",
        5: "下腹疼痛感较强，影响日常活动。",
        6: "下腹疼痛明显，活动受限。",
        7: "下腹疼痛严重，需要充分休息。",
        8: "下腹剧烈疼痛，严重影响状态。",
        9: "疼痛非常严重，需要医疗帮助。",
        10: "疼痛极其剧烈，需要紧急医疗。"
    }
    
    @classmethod
    def get_physical_prompt(cls, level: int) -> str:
        """获取生理影响等级的提示词"""
        return cls.PHYSICAL_TEMPLATES.get(level, cls.PHYSICAL_TEMPLATES[5])
    
    @classmethod
    def get_psychological_prompt(cls, level: int) -> str:
        """获取心理影响等级的提示词"""
        return cls.PSYCHOLOGICAL_TEMPLATES.get(level, cls.PSYCHOLOGICAL_TEMPLATES[5])
    
    @classmethod
    def get_dysmenorrhea_prompt(cls, level: int) -> str:
        """获取痛经等级的提示词"""
        return cls.DYSMENORRHEA_TEMPLATES.get(level, cls.DYSMENORRHEA_TEMPLATES[0])


# ============================================================================
# 双周期锚定模型 - 核心数据结构
# ============================================================================

class CyclePhase:
    """周期阶段定义"""
    def __init__(self, name: str, name_cn: str, duration: int, day_in_phase: int):
        self.name = name  # 阶段英文名
        self.name_cn = name_cn  # 阶段中文名
        self.duration = duration  # 阶段持续天数
        self.day_in_phase = day_in_phase  # 阶段内第几天


class DualCycleData:
    """双周期数据"""
    def __init__(self, anchor_day: int, start_date: datetime, 
                 cycle1_length: int, cycle2_length: int,
                 cycle1_menstrual_days: int, cycle2_menstrual_days: int):
        self.anchor_day = anchor_day  # 锚点日期（1-31）
        self.start_date = start_date  # 起始锚点日期
        self.cycle1_length = cycle1_length  # 第一周期天数
        self.cycle2_length = cycle2_length  # 第二周期天数
        self.cycle1_menstrual_days = cycle1_menstrual_days  # 第一周期月经天数
        self.cycle2_menstrual_days = cycle2_menstrual_days  # 第二周期月经天数
        self.total_days = cycle1_length + cycle2_length  # 总天数
        self.end_date = self._calculate_end_date()  # 结束锚点日期
        
    def _calculate_end_date(self) -> datetime:
        """计算结束锚点日期（下下个月的锚点日）"""
        # 从起始日期开始，跳到下下个月
        current = self.start_date
        
        # 第一次跳：跳到下一个月
        if current.month == 12:
            next_month = current.replace(year=current.year + 1, month=1, day=1)
        else:
            next_month = current.replace(month=current.month + 1, day=1)
        
        # 第二次跳：跳到下下个月
        if next_month.month == 12:
            next_next_month = next_month.replace(year=next_month.year + 1, month=1, day=1)
        else:
            next_next_month = next_month.replace(month=next_month.month + 1, day=1)
        
        # 获取下下个月的锚点日
        days_in_month = monthrange(next_next_month.year, next_next_month.month)[1]
        anchor = min(self.anchor_day, days_in_month)
        
        return next_next_month.replace(day=anchor)
    
    def to_dict(self) -> dict:
        """转换为字典以便存储"""
        return {
            "anchor_day": self.anchor_day,
            "start_date": self.start_date.isoformat(),
            "cycle1_length": self.cycle1_length,
            "cycle2_length": self.cycle2_length,
            "cycle1_menstrual_days": self.cycle1_menstrual_days,
            "cycle2_menstrual_days": self.cycle2_menstrual_days,
            "total_days": self.total_days,
            "end_date": self.end_date.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'DualCycleData':
        """从字典恢复"""
        return cls(
            anchor_day=data["anchor_day"],
            start_date=datetime.fromisoformat(data["start_date"]),
            cycle1_length=data["cycle1_length"],
            cycle2_length=data["cycle2_length"],
            cycle1_menstrual_days=data["cycle1_menstrual_days"],
            cycle2_menstrual_days=data["cycle2_menstrual_days"]
        )


# ============================================================================
# 双周期锚定管理器
# ============================================================================

class DualCycleManager:
    """双周期锚定管理器"""
    
    def __init__(self, get_config_func=None):
        """
        初始化双周期管理器
        
        Args:
            get_config_func: 配置获取函数，用于从config读取anchor_day
        """
        self.current_cycle: Optional[DualCycleData] = None
        self.get_config = get_config_func
        self._sync_anchor_day_from_config()  # 同步配置到storage
        self._load_or_generate_cycle()
    
    def _sync_anchor_day_from_config(self):
        """从配置文件同步锚点日期到storage"""
        if self.get_config:
            config_anchor = self.get_config("cycle.anchor_day", None)
            if config_anchor is not None:
                storage_anchor = plugin_storage.get("anchor_day", None)
                if storage_anchor != config_anchor:
                    logger.info(f"同步锚点日期: config={config_anchor}, storage={storage_anchor} → {config_anchor}")
                    plugin_storage.set("anchor_day", config_anchor)
                    # 清除旧的双周期数据，强制重新生成
                    plugin_storage.delete("dual_cycle_data")
    
    def _load_or_generate_cycle(self):
        """加载或生成双周期数据"""
        stored_cycle = plugin_storage.get("dual_cycle_data", None)
        current_anchor = plugin_storage.get("anchor_day", 15)
        
        if stored_cycle:
            try:
                self.current_cycle = DualCycleData.from_dict(stored_cycle)
                today = datetime.now()
                
                # 检查anchor_day是否改变
                if self.current_cycle.anchor_day != current_anchor:
                    logger.info(f"检测到锚点日期变化: {self.current_cycle.anchor_day} → {current_anchor}，重新生成周期")
                    self._generate_new_cycle()
                # 检查是否已过期
                elif today >= self.current_cycle.end_date:
                    logger.info("双周期已过期，重新生成")
                    self._generate_new_cycle()
                else:
                    logger.info(f"加载已存储的双周期数据（锚点={self.current_cycle.anchor_day}号），有效期至 {self.current_cycle.end_date.date()}")
            except Exception as e:
                logger.error(f"加载双周期数据失败: {e}，重新生成")
                self._generate_new_cycle()
        else:
            logger.info("首次运行，生成双周期数据")
            self._generate_new_cycle()
    
    def _generate_new_cycle(self):
        """
        生成新的双周期数据
        ⚠️ 锚点日期 = 月经期第1天
        ⚠️ 两个周期总长 = 起始锚点到下下个月锚点的天数
        """
        # 从存储获取锚点日期配置，默认为15号
        anchor_day = plugin_storage.get("anchor_day", 15)
        
        # 计算当前锚点日期（月经开始日期）
        today = datetime.now()
        days_in_month = monthrange(today.year, today.month)[1]
        anchor = min(anchor_day, days_in_month)
        
        # 确定最近的月经开始日期（锚点日期）
        # 如果今天是锚点日期或之后，则本月锚点是月经开始
        # 否则使用上月锚点作为月经开始
        if today.day >= anchor:
            # 本月锚点日期
            menstrual_start_date = today.replace(day=anchor)
        else:
            # 回到上个月的锚点日期
            if today.month == 1:
                last_month = today.replace(year=today.year - 1, month=12, day=1)
            else:
                last_month = today.replace(month=today.month - 1, day=1)
            days_in_last_month = monthrange(last_month.year, last_month.month)[1]
            anchor_last = min(anchor_day, days_in_last_month)
            menstrual_start_date = last_month.replace(day=anchor_last)
        
        # 起始日期 = 月经开始日期
        start_date = menstrual_start_date
        
        # 计算下下个月的锚点日期（结束日期）
        end_date = self._calculate_next_next_anchor(start_date, anchor_day)
        
        # 总天数 = 从起始锚点到下下个月锚点
        total_days = (end_date - start_date).days
        
        # 将总天数分配给两个周期（随机分配，保持合理比例）
        # 例如：62天可以分配为 30+32, 28+34, 31+31 等
        half = total_days // 2
        # 在half附近随机偏移3-5天
        offset = random.randint(3, 5)
        if random.random() > 0.5:
            cycle1_length = half + offset
        else:
            cycle1_length = half - offset
        cycle2_length = total_days - cycle1_length
        
        # 确保周期长度合理（至少21天）
        if cycle1_length < 21 or cycle2_length < 21:
            logger.warning(f"周期长度过短（总计{total_days}天），平均分配")
            cycle1_length = total_days // 2
            cycle2_length = total_days - cycle1_length
        
        # 随机生成月经天数（3-7天）
        cycle1_menstrual_days = random.randint(3, 7)
        cycle2_menstrual_days = random.randint(3, 7)
        
        self.current_cycle = DualCycleData(
            anchor_day=anchor_day,
            start_date=start_date,
            cycle1_length=cycle1_length,
            cycle2_length=cycle2_length,
            cycle1_menstrual_days=cycle1_menstrual_days,
            cycle2_menstrual_days=cycle2_menstrual_days
        )
        
        # 保存到存储
        plugin_storage.set("dual_cycle_data", self.current_cycle.to_dict())
        
        logger.info(f"生成新双周期（锚点={anchor_day}号=月经开始）: "
                   f"起始={start_date.date()}, "
                   f"结束={end_date.date()}, "
                   f"周期1={cycle1_length}天(月经{cycle1_menstrual_days}天), "
                   f"周期2={cycle2_length}天(月经{cycle2_menstrual_days}天), "
                   f"总计={total_days}天")
    
    def _calculate_next_next_anchor(self, from_date: datetime, anchor_day: int) -> datetime:
        """计算下下个月的锚点日期"""
        current = from_date
        
        # 第一次跳：跳到下一个月
        if current.month == 12:
            next_month = current.replace(year=current.year + 1, month=1, day=1)
        else:
            next_month = current.replace(month=current.month + 1, day=1)
        
        # 第二次跳：跳到下下个月
        if next_month.month == 12:
            next_next_month = next_month.replace(year=next_month.year + 1, month=1, day=1)
        else:
            next_next_month = next_month.replace(month=next_month.month + 1, day=1)
        
        # 获取下下个月的锚点日
        days_in_month = monthrange(next_next_month.year, next_next_month.month)[1]
        anchor = min(anchor_day, days_in_month)
        
        return next_next_month.replace(day=anchor)
    
    def _get_next_anchor_date(self, from_date: datetime, anchor_day: int) -> datetime:
        """获取下一个锚点日期"""
        # 跳到下一个月
        if from_date.month == 12:
            next_month = from_date.replace(year=from_date.year + 1, month=1, day=1)
        else:
            next_month = from_date.replace(month=from_date.month + 1, day=1)
        
        days_in_month = monthrange(next_month.year, next_month.month)[1]
        anchor = min(anchor_day, days_in_month)
        
        return next_month.replace(day=anchor)
    
    def get_current_phase(self, query_date: Optional[datetime] = None) -> Tuple[CyclePhase, int, int]:
        """
        获取指定日期的周期阶段
        
        Returns:
            Tuple[CyclePhase, 周期编号(1或2), 周期内第几天]
        """
        if query_date is None:
            query_date = datetime.now()
        
        # 确保有有效的周期数据
        if not self.current_cycle:
            self._generate_new_cycle()
        
        # 如果查询日期超出当前周期，重新生成
        if query_date >= self.current_cycle.end_date:
            self._generate_new_cycle()
        
        # 计算距离起始日期的天数
        days_from_start = (query_date - self.current_cycle.start_date).days
        
        # 如果是负数，说明查询日期在当前周期之前，需要重新生成
        if days_from_start < 0:
            self._generate_new_cycle()
            days_from_start = (query_date - self.current_cycle.start_date).days
        
        # 确定在哪个周期
        if days_from_start < self.current_cycle.cycle1_length:
            # 第一周期
            cycle_num = 1
            day_in_cycle = days_from_start + 1
            cycle_length = self.current_cycle.cycle1_length
            menstrual_days = self.current_cycle.cycle1_menstrual_days
        else:
            # 第二周期
            cycle_num = 2
            day_in_cycle = days_from_start - self.current_cycle.cycle1_length + 1
            cycle_length = self.current_cycle.cycle2_length
            menstrual_days = self.current_cycle.cycle2_menstrual_days
        
        # 计算阶段
        phase = self._calculate_phase(day_in_cycle, cycle_length, menstrual_days)
        
        return phase, cycle_num, day_in_cycle
    
    def _calculate_phase(self, day_in_cycle: int, cycle_length: int, 
                        menstrual_days: int) -> CyclePhase:
        """
        计算周期内的阶段
        
        固定分配：
        - 月经期：随机3-7天
        - 卵泡期：剩余天数 - 16
        - 排卵期：固定2天
        - 黄体期：固定14天
        """
        # 月经期
        if day_in_cycle <= menstrual_days:
            return CyclePhase("menstrual", "月经期", menstrual_days, day_in_cycle)
        
        # 卵泡期天数 = 周期总长 - 月经天数 - 2（排卵）- 14（黄体）
        follicular_days = cycle_length - menstrual_days - 2 - 14
        
        # 卵泡期
        if day_in_cycle <= menstrual_days + follicular_days:
            day_in_phase = day_in_cycle - menstrual_days
            return CyclePhase("follicular", "卵泡期", follicular_days, day_in_phase)
        
        # 排卵期
        if day_in_cycle <= menstrual_days + follicular_days + 2:
            day_in_phase = day_in_cycle - menstrual_days - follicular_days
            return CyclePhase("ovulation", "排卵期", 2, day_in_phase)
        
        # 黄体期
        day_in_phase = day_in_cycle - menstrual_days - follicular_days - 2
        return CyclePhase("luteal", "黄体期", 14, day_in_phase)
    
    def regenerate_cycle(self):
        """强制重新生成周期"""
        self._generate_new_cycle()


# ============================================================================
# 周期状态管理器
# ============================================================================

class PeriodStateManager:
    """月经周期状态管理器 - 使用双周期锚定模型"""
    
    def __init__(self, get_config_func=None):
        """
        初始化状态管理器
        
        Args:
            get_config_func: 配置获取函数，格式为 func(key, default)
        """
        self.get_config = get_config_func
        self.cycle_manager = DualCycleManager(get_config_func=get_config_func)  # 传递配置函数
        self.last_calculated_date = None
        self.current_state = None
        
    def calculate_current_state(self, cycle_length: int = None, force_recalc: bool = False) -> Dict[str, Any]:
        """
        计算当前周期状态
        
        Args:
            cycle_length: 已废弃，仅为兼容性保留
            force_recalc: 是否强制重新计算（忽略缓存）
        """
        today = datetime.now()
        
        # 如果已经计算过今天的状态，直接返回缓存（除非强制重新计算）
        if not force_recalc and self.last_calculated_date == today.date() and self.current_state:
            return self.current_state
        
        try:
            # 获取当前阶段
            phase, cycle_num, day_in_cycle = self.cycle_manager.get_current_phase(today)
            
            # 计算影响值（基于阶段）
            physical_impact, psychological_impact = self._calculate_impacts(phase.name, day_in_cycle, phase.duration)
            
            # 将影响值转换为等级（1-10）
            physical_level = self._impact_to_level(physical_impact)
            psychological_level = self._impact_to_level(psychological_impact)
            
            # 痛经等级（仅在月经期）
            if phase.name == "menstrual":
                dysmenorrhea_level = self._generate_dysmenorrhea_level()
            else:
                dysmenorrhea_level = 0
            
            self.current_state = {
                "stage": phase.name,
                "stage_name_cn": phase.name_cn,
                "cycle_num": cycle_num,
                "day_in_cycle": day_in_cycle,
                "day_in_phase": phase.day_in_phase,
                "phase_duration": phase.duration,
                "current_day": day_in_cycle,  # 兼容旧版
                "cycle_length": self.cycle_manager.current_cycle.total_days,  # 兼容旧版
                "physical_level": physical_level,
                "psychological_level": psychological_level,
                "dysmenorrhea_level": dysmenorrhea_level,
                "description": self._get_stage_description(phase.name),
                "last_updated": today.date().isoformat(),
                "status": "normal"
            }
            
            self.last_calculated_date = today.date()
            
            return self.current_state
            
        except Exception as e:
            logger.error(f"计算周期状态失败: {e}")
            # 返回默认状态
            return {
                "stage": "follicular",
                "stage_name_cn": "卵泡期",
                "cycle_num": 1,
                "day_in_cycle": 10,
                "day_in_phase": 5,
                "phase_duration": 10,
                "current_day": 10,
                "cycle_length": 28,
                "physical_level": 2,
                "psychological_level": 2,
                "dysmenorrhea_level": 0,
                "description": "状态恢复，情绪平稳，思维清晰",
                "last_updated": today.date().isoformat(),
                "status": "error",
                "error": str(e)
            }
    
    def _calculate_impacts(self, stage: str, current_day: int, phase_duration: int) -> Tuple[float, float]:
        """计算生理和心理影响值（从配置读取等级）"""
        # 从配置读取等级（1-10），如果没有配置函数则使用默认等级
        if self.get_config:
            physical_level = self.get_config(f"levels.{stage}_physical", 5)
            psychological_level = self.get_config(f"levels.{stage}_psychological", 5)
        else:
            # 默认等级配置
            default_levels = {
                "menstrual": (5, 4),
                "follicular": (2, 2),
                "ovulation": (3, 2),
                "luteal": (4, 3)
            }
            physical_level, psychological_level = default_levels.get(stage, (5, 5))
        
        # 将等级（1-10）转换为影响值（0.0-1.0）
        physical_base = self._level_to_impact(physical_level)
        psychological_base = self._level_to_impact(psychological_level)
        
        # 在阶段内进行微调
        if stage == "menstrual":
            # 月经期：开始几天影响更强
            day_in_stage = current_day
            intensity = 1.0 - (day_in_stage - 1) / max(phase_duration, 1) * 0.3
            physical_impact = physical_base * intensity
            psychological_impact = psychological_base * intensity
            
        elif stage == "luteal":
            # 黄体期：后期影响更强（PMS症状）
            intensity = 0.7 + (current_day / max(phase_duration, 1)) * 0.3
            physical_impact = min(physical_base * intensity, 0.8)
            psychological_impact = min(psychological_base * intensity, 0.7)
            
        else:
            # 其他阶段使用基础值
            physical_impact = physical_base
            psychological_impact = psychological_base
            
        return round(physical_impact, 2), round(psychological_impact, 2)
    
    def _level_to_impact(self, level: int) -> float:
        """将等级(1-10)转换为影响值(0.0-1.0)"""
        # 线性映射：1 -> 0.0, 10 -> 1.0
        return (level - 1) / 9.0
    
    def _impact_to_level(self, impact: float) -> int:
        """将影响值(0.0-1.0)转换为等级(1-10)"""
        # 线性映射：0.0 -> 1, 1.0 -> 10
        level = int(impact * 9) + 1
        return max(1, min(10, level))
    
    def _generate_dysmenorrhea_level(self) -> int:
        """
        生成痛经等级
        三个等级：无(0)、轻度(1-3)、中度(4-6)
        概率分布：无20%、轻度70%、中度10%
        """
        rand = random.random()
        if rand < 0.2:  # 20%概率无痛经
            return 0
        elif rand < 0.9:  # 70%概率轻度痛经(1-3)
            return random.randint(1, 3)
        else:  # 10%概率中度痛经(4-6)
            return random.randint(4, 6)
        
    def _get_intimacy_guidance(self, stage: str, current_day: int, cycle_length: int) -> Tuple[str, str]:
        """获取亲密需求指导，返回 (性欲指导, 情感指导) 两个部分"""
        if stage == "menstrual":
            # 月经期：需要安慰照顾，性欲低
            sexual = "性欲显著降低，对性接触有排斥感，应避免任何性暗示或挑逗行为。"
            emotional = "情感上需要被温柔拥抱、安慰和照顾，渴望得到理解和支持，情绪敏感易受伤。"
        elif stage == "follicular":
            # 卵泡期：情感需求中等，性欲逐渐上升
            if current_day <= 7:
                sexual = "性冲动开始恢复，但还不强烈，可以接受轻度亲密但不会主动寻求。"
                emotional = "情感上比较平和，愿意进行正常的情感交流，但不会过度依赖。"
            else:
                sexual = "性欲明显增强，开始对性接触产生兴趣，可能会主动暗示或接受挑逗。"
                emotional = "情感上愿意亲近，渴望更多的陪伴和互动，但依然保持理性。"
        elif stage == "ovulation":
            # 排卵期：性欲高峰期，但情感需求要区分
            sexual = "性欲达到高峰，生理上强烈渴望性接触，会主动挑逗、寻求亲密，但需要真诚的情感连接而非单纯肉体关系。"
            emotional = "情感上需要真诚、深度的连接，渴望被认可和珍视，对虚伪的暧昧感到反感。"
        else:  # luteal
            # 黄体期：情感需求增加，性欲下降
            if current_day >= cycle_length - 3:  # 经前阶段
                sexual = "性欲很低，对性接触缺乏兴趣，更适合非性的温柔安慰。"
                emotional = "情感上需要更多理解和陪伴，情绪波动大，容易感到委屈，需要耐心安抚。"
            else:
                sexual = "性冲动相对较低，但仍可接受亲密，但更倾向于情感上的满足。"
                emotional = "情感上渴望被照顾，依赖感增强，希望对方主动提供情感支持。"
        return sexual, emotional
        
    def _get_stage_description(self, stage: str) -> str:
        """获取阶段描述"""
        descriptions = {
            "menstrual": "身体不适，情绪敏感，需要更多休息和理解",
            "follicular": "状态恢复，情绪平稳，思维清晰",
            "ovulation": "状态较佳，情绪积极，表达流畅",
            "luteal": "身体疲惫，情绪波动，需要更多耐心"
        }
        return descriptions.get(stage, "")
    
    def clear_cache(self):
        """清除状态缓存，强制下次查询重新计算"""
        self.last_calculated_date = None
        self.current_state = None
        logger.info("已清除周期状态缓存")
    
    def force_regenerate_cycle(self):
        """强制重新生成双周期数据"""
        self.cycle_manager.regenerate_cycle()
        self.clear_cache()
        logger.info("已强制重新生成双周期数据")


# ============================================================================
# 兼容旧版API的辅助函数
# ============================================================================

def get_last_period_date() -> str:
    """
    获取上次月经开始日期（已废弃，仅为兼容性保留）
    双周期模型不再使用此API
    """
    logger.warning("get_last_period_date() 已废弃，双周期模型不再使用此API")
    # 返回当前周期的起始日期作为兼容
    dual_cycle_data = plugin_storage.get("dual_cycle_data", None)
    if dual_cycle_data:
        return dual_cycle_data.get("start_date", datetime.now().strftime("%Y-%m-%d"))
    return datetime.now().strftime("%Y-%m-%d")

def set_last_period_date(date_str: str) -> bool:
    """
    设置上次月经开始日期（已废弃，仅为兼容性保留）
    双周期模型不再使用此API，改用set_anchor_day()
    """
    logger.warning("set_last_period_date() 已废弃，请使用 set_anchor_day() 设置锚点日期")
    return False

def set_anchor_day(day: int, force_regenerate: bool = True) -> bool:
    """
    设置锚点日期（1-31）
    
    Args:
        day: 锚点日期（1-31）
        force_regenerate: 是否立即重新生成双周期数据（默认True）
    """
    try:
        if not isinstance(day, int) or day < 1 or day > 31:
            logger.error(f"无效的锚点日期: {day}，必须是1-31之间的整数")
            return False
        
        old_anchor = plugin_storage.get("anchor_day", 15)
        plugin_storage.set("anchor_day", day)
        
        if force_regenerate and old_anchor != day:
            # 清除旧的双周期数据，强制重新生成
            plugin_storage.delete("dual_cycle_data")
            logger.info(f"更新锚点日期: {old_anchor} → {day}，已清除旧周期数据，将立即重新生成")
        else:
            logger.info(f"更新锚点日期为每月 {day} 号")
        
        return True
    except Exception as e:
        logger.error(f"设置锚点日期失败: {e}")
        return False