from src.plugin_system import ConfigField

# 配置Schema定义 - 增强版本，包含KFC集成和更好的错误处理
CONFIG_SCHEMA = {
    "plugin": {
        "enabled": ConfigField(
            type=bool,
            default=False,
            description="是否启用月经周期状态插件"
        ),
        "config_version": ConfigField(
            type=str,
            default="3.0.0",
            description="配置文件版本（3.0使用双周期锚定模型）"
        ),
        "debug_mode": ConfigField(
            type=bool,
            default=False,
            description="是否启用调试模式，会输出更多日志信息"
        )
    },
    "cycle": {
        "anchor_day": ConfigField(
            type=int,
            default=15,
            description="锚点日期（1-31），每月固定号数作为周期计算基准",
            example="15"
        )
    },
    "levels": {
        "menstrual_physical": ConfigField(
            type=int,
            default=5,
            description="月经期生理影响等级（1-10）",
            example="5"
        ),
        "menstrual_psychological": ConfigField(
            type=int,
            default=4,
            description="月经期心理影响等级（1-10）",
            example="4"
        ),
        "follicular_physical": ConfigField(
            type=int,
            default=2,
            description="卵泡期生理影响等级（1-10）",
            example="2"
        ),
        "follicular_psychological": ConfigField(
            type=int,
            default=2,
            description="卵泡期心理影响等级（1-10）",
            example="2"
        ),
        "ovulation_physical": ConfigField(
            type=int,
            default=3,
            description="排卵期生理影响等级（1-10）",
            example="3"
        ),
        "ovulation_psychological": ConfigField(
            type=int,
            default=2,
            description="排卵期心理影响等级（1-10）",
            example="2"
        ),
        "luteal_physical": ConfigField(
            type=int,
            default=4,
            description="黄体期生理影响等级（1-10）",
            example="4"
        ),
        "luteal_psychological": ConfigField(
            type=int,
            default=3,
            description="黄体期心理影响等级（1-10）",
            example="3"
        )
    },
    "dysmenorrhea": {
        "prob_none": ConfigField(
            type=float,
            default=0.25,
            description="无痛经概率（0.0-1.0）"
        ),
        "prob_mild": ConfigField(
            type=float,
            default=0.30,
            description="轻度痛经概率（1-2级，0.0-1.0）"
        ),
        "prob_moderate": ConfigField(
            type=float,
            default=0.25,
            description="中度痛经概率（3-4级，0.0-1.0）"
        ),
        "prob_severe": ConfigField(
            type=float,
            default=0.20,
            description="重度痛经概率（5-6级，0.0-1.0）"
        ),
        "enable_llm_relief": ConfigField(
            type=bool,
            default=False,
            description="是否启用LLM判定消息缓解痛经功能"
        ),
        "llm_model": ConfigField(
            type=str,
            default="utils",
            description="缓解判定使用的LLM模型。支持两种方式：\n"
                       "1. 任务配置名（如 'utils', 'replyer'）\n"
                       "2. 具体模型名（如 'deepseek-v3', 'qwen3-14b'）- 对应 model_config.toml 中的 name 字段"
        ),
        "relief_duration_minutes": ConfigField(
            type=int,
            default=60,
            description="缓解效果持续时间（分钟）"
        ),
        "relief_reduction": ConfigField(
            type=int,
            default=1,
            description="缓解时降低的痛经等级（0-6）"
        )
    },
    "kfc_integration": {
        "enabled": ConfigField(
            type=bool,
            default=True,
            description="是否启用KFC（私聊模式）集成"
        ),
        "priority": ConfigField(
            type=int,
            default=100,
            description="KFC模式下提示词注入的优先级"
        )
        # 注意：KFC工作模式不在插件配置中设置
        # 插件会自动从Bot config读取 [kokoro_flow_chatter] mode 的值
        # 这样可以确保插件始终与Bot的实际KFC模式保持一致
    },
    "lust_system": {
        "enabled": ConfigField(
            type=bool,
            default=True,
            description="是否启用淫乱度与高潮值子系统（仅KFC模式）"
        ),
        "orgasm_threshold": ConfigField(
            type=float,
            default=100.0,
            description="高潮阈值，达到此值触发高潮",
            example="100.0"
        ),
        "foreplay_threshold": ConfigField(
            type=float,
            default=20.0,
            description="前戏阈值",
            example="20.0"
        ),
        "main_threshold": ConfigField(
            type=float,
            default=60.0,
            description="正戏阈值",
            example="60.0"
        ),
        "base_score_weight": ConfigField(
            type=float,
            default=1.0,
            description="基础得分权重，用于调整LLM评分对高潮值的影响",
            example="1.0"
        ),
        "decay_rate": ConfigField(
            type=float,
            default=0.1,
            description="高潮值衰减率（每秒减少的分数）",
            example="0.1"
        ),
        "post_orgasm_recovery_ratio": ConfigField(
            type=float,
            default=0.4,
            description="高潮后高潮值恢复比例，相对于 main_threshold（例如0.4表示恢复至正戏阈值的40%）",
            example="0.4"
        ),
        "initial_ratio": ConfigField(
            type=float,
            default=0.5,
            description="初始高潮值系数，用于计算初始高潮值（lust_level * foreplay_threshold * initial_ratio）",
            example="0.5"
        ),
        "passive_active_ratio": ConfigField(
            type=float,
            default=0.3,
            description="被动主动阈值系数，用于划分被动未开始和主动未开始（passive_active_threshold = foreplay_threshold * passive_active_ratio）",
            example="0.3"
        ),
        "low_score_threshold": ConfigField(
            type=float,
            default=3.0,
            description="低评分阈值，低于此值视为低评分",
            example="3.0"
        ),
        "low_score_count_to_terminate": ConfigField(
            type=int,
            default=3,
            description="连续低评分次数触发终止",
            example="3"
        ),
        "termination_decay_multiplier": ConfigField(
            type=float,
            default=2.0,
            description="递减机制中的衰减率乘数，用于加速高潮值下降",
            example="2.0"
        ),
        "afterglow_duration": ConfigField(
            type=int,
            default=60,
            description="高潮余韵期持续时间（秒），刚高潮后的愉悦放松期",
            example="60"
        ),
        "recovery_duration": ConfigField(
            type=int,
            default=240,
            description="体力恢复期持续时间（秒），余韵期结束后的体力恢复阶段",
            example="240"
        ),
        "llm_model": ConfigField(
            type=str,
            default="utils",
            description="用于评分的LLM模型。支持两种方式：\n"
                       "1. 任务配置名（如 'utils', 'replyer'）\n"
                       "2. 具体模型名（如 'deepseek-v3', 'qwen3-14b'）- 对应 model_config.toml 中的 name 字段",
            example="deepseek-v3"
        )
    },
    "backup": {
        "auto_backup": ConfigField(
            type=bool,
            default=True,
            description="是否自动备份配置和数据"
        ),
        "backup_days": ConfigField(
            type=int,
            default=30,
            description="备份保留天数"
        )
    }
}