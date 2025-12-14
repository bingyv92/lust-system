from typing import Dict, Any, Tuple
from datetime import datetime, timedelta
from src.plugin_system.apis import storage_api
from src.common.logger import get_logger

logger = get_logger("mofox_period_plugin")

# 获取插件的本地存储实例
plugin_storage = storage_api.get_local_storage("mofox_period_plugin")

def get_last_period_date() -> str:
    """获取上次月经开始日期，如果没有设置过则设为安装当天"""
    last_period_date = plugin_storage.get("last_period_date", None)
    if last_period_date is None:
        # 首次使用，设置为今天
        today_str = datetime.now().strftime("%Y-%m-%d")
        plugin_storage.set("last_period_date", today_str)
        logger.info(f"首次安装，设置上次月经开始日期为: {today_str}")
        return today_str
    return last_period_date

def set_last_period_date(date_str: str) -> bool:
    """设置上次月经开始日期"""
    try:
        # 验证日期格式
        datetime.strptime(date_str, "%Y-%m-%d")
        plugin_storage.set("last_period_date", date_str)
        logger.info(f"更新上次月经开始日期为: {date_str}")
        return True
    except ValueError:
        logger.error(f"无效的日期格式: {date_str}")
        return False

class PeriodStateManager:
    """月经周期状态管理器 - 增强版本，更好的错误处理"""
    
    def __init__(self):
        self.last_calculated_date = None
        self.current_state = None
        self._fallback_state = None  # 备用状态缓存
        
    def calculate_current_state(self, cycle_length: int) -> Dict[str, Any]:
        """计算当前周期状态 - 增强错误处理"""
        today = datetime.now().date()
        
        # 如果已经计算过今天的状态，直接返回缓存
        if self.last_calculated_date == today and self.current_state:
            return self.current_state
        
        try:
            # 从存储中获取上次月经日期
            last_period_date = get_last_period_date()
                
            try:
                last_date = datetime.strptime(last_period_date, "%Y-%m-%d").date()
            except ValueError:
                logger.error(f"无效的日期格式: {last_period_date}, 使用默认值")
                last_date = datetime.now().date() - timedelta(days=14)
                
            # 验证周期长度
            if not isinstance(cycle_length, int) or cycle_length < 20 or cycle_length > 40:
                logger.warning(f"无效的周期长度: {cycle_length}，使用默认值28")
                cycle_length = 28
                
            # 计算当前周期天数
            days_passed = (today - last_date).days
            current_day = days_passed % cycle_length + 1
            
            # 确保天数在有效范围内
            if current_day < 1 or current_day > cycle_length:
                logger.warning(f"计算的天数超出范围: {current_day}，重新计算")
                current_day = 1
                
            # 确定当前阶段
            if current_day <= 5:
                stage = "menstrual"  # 月经期
            elif current_day <= 13:
                stage = "follicular"  # 卵泡期
            elif current_day == 14:
                stage = "ovulation"  # 排卵期
            else:
                stage = "luteal"  # 黄体期
                
            # 计算影响值
            physical_impact, psychological_impact = self._calculate_impacts(stage, current_day, cycle_length)
            
            # 验证影响值
            physical_impact = max(0.0, min(1.0, physical_impact))
            psychological_impact = max(0.0, min(1.0, psychological_impact))
            
            self.current_state = {
                "stage": stage,
                "current_day": current_day,
                "cycle_length": cycle_length,
                "physical_impact": round(physical_impact, 2),
                "psychological_impact": round(psychological_impact, 2),
                "stage_name_cn": self._get_stage_name_cn(stage),
                "description": self._get_stage_description(stage),
                "last_updated": today.isoformat(),
                "status": "normal"
            }
            
            self.last_calculated_date = today
            self._fallback_state = self.current_state.copy()  # 保存备用状态
            
            return self.current_state
            
        except Exception as e:
            logger.error(f"计算周期状态失败: {e}")
            
            # 如果存在备用状态，返回备用状态
            if self._fallback_state:
                logger.info("使用备用状态")
                self._fallback_state["status"] = "fallback"
                self._fallback_state["error"] = str(e)
                return self._fallback_state
            
            # 创建默认状态
            logger.info("创建默认状态")
            default_state = {
                "stage": "follicular",
                "current_day": 7,
                "cycle_length": 28,
                "physical_impact": 0.1,
                "psychological_impact": 0.1,
                "stage_name_cn": "卵泡期",
                "description": "状态恢复，情绪平稳，思维清晰",
                "last_updated": today.isoformat(),
                "status": "default",
                "error": str(e)
            }
            
            return default_state
        
    def _calculate_impacts(self, stage: str, current_day: int, cycle_length: int) -> Tuple[float, float]:
        """计算生理和心理影响值"""
        # 基础影响值配置
        base_impacts = {
            "menstrual": (0.8, 0.7),    # 生理高，心理中高
            "follicular": (0.1, 0.1),   # 生理低，心理低
            "ovulation": (0.4, 0.2),    # 生理中，心理低
            "luteal": (0.6, 0.5)        # 生理中高，心理中
        }
        
        physical_base, psychological_base = base_impacts[stage]
        
        # 在阶段内进行微调
        if stage == "menstrual":
            # 月经期：开始几天影响更强
            day_in_stage = current_day
            intensity = 1.0 - (day_in_stage - 1) / 5 * 0.3
            physical_impact = physical_base * intensity
            psychological_impact = psychological_base * intensity
            
        elif stage == "luteal":
            # 黄体期：后期影响更强（PMS症状）
            day_in_stage = current_day - 14
            total_days = cycle_length - 14
            intensity = 0.7 + (day_in_stage / total_days) * 0.3
            physical_impact = min(physical_base * intensity, 0.8)
            psychological_impact = min(psychological_base * intensity, 0.7)
            
        else:
            # 其他阶段使用基础值
            physical_impact = physical_base
            psychological_impact = psychological_base
            
        return round(physical_impact, 2), round(psychological_impact, 2)
        
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
        
    def _get_stage_name_cn(self, stage: str) -> str:
        """获取阶段中文名称"""
        names = {
            "menstrual": "月经期",
            "follicular": "卵泡期", 
            "ovulation": "排卵期",
            "luteal": "黄体期"
        }
        return names.get(stage, "未知阶段")
        
    def _get_stage_description(self, stage: str) -> str:
        """获取阶段描述"""
        descriptions = {
            "menstrual": "身体不适，情绪敏感，需要更多休息和理解",
            "follicular": "状态恢复，情绪平稳，思维清晰",
            "ovulation": "状态较佳，情绪积极，表达流畅",
            "luteal": "身体疲惫，情绪波动，需要更多耐心"
        }
        return descriptions.get(stage, "")