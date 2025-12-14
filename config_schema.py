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
            default="1.1.0",
            description="配置文件版本"
        ),
        "debug_mode": ConfigField(
            type=bool,
            default=False,
            description="是否启用调试模式，会输出更多日志信息"
        )
    },
    "cycle": {
        "cycle_length": ConfigField(
            type=int,
            default=28,
            description="月经周期长度 (天)",
            example="28"
        ),
        "auto_detect": ConfigField(
            type=bool,
            default=True,
            description="是否自动检测和适应周期变化"
        )
    },
    "impacts": {
        "menstrual_physical": ConfigField(
            type=float,
            default=0.8,
            description="月经期生理影响强度 (0-1)",
            example="0.8"
        ),
        "menstrual_psychological": ConfigField(
            type=float,
            default=0.7,
            description="月经期心理影响强度 (0-1)",
            example="0.7"
        ),
        "follicular_physical": ConfigField(
            type=float,
            default=0.1,
            description="卵泡期生理影响强度 (0-1)",
            example="0.1"
        ),
        "follicular_psychological": ConfigField(
            type=float,
            default=0.1,
            description="卵泡期心理影响强度 (0-1)",
            example="0.1"
        ),
        "ovulation_physical": ConfigField(
            type=float,
            default=0.4,
            description="排卵期生理影响强度 (0-1)",
            example="0.4"
        ),
        "ovulation_psychological": ConfigField(
            type=float,
            default=0.2,
            description="排卵期心理影响强度 (0-1)",
            example="0.2"
        ),
        "luteal_physical": ConfigField(
            type=float,
            default=0.6,
            description="黄体期生理影响强度 (0-1)",
            example="0.6"
        ),
        "luteal_psychological": ConfigField(
            type=float,
            default=0.5,
            description="黄体期心理影响强度 (0-1)",
            example="0.5"
        )
    },
    "kfc_integration": {
        "enabled": ConfigField(
            type=bool,
            default=True,
            description="是否启用KFC（私聊模式）集成"
        ),
        "mode": ConfigField(
            type=str,
            default="unified",
            description="KFC工作模式: unified(统一模式) 或 split(分离模式)",
            example="unified"
        ),
        "priority": ConfigField(
            type=int,
            default=100,
            description="KFC模式下提示词注入的优先级"
        )
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
        "cooldown_duration": ConfigField(
            type=int,
            default=300,
            description="冷却持续时间（秒），仅用于体力不支终止（高潮次数用尽）",
            example="300"
        ),
        "llm_model": ConfigField(
            type=str,
            default="judge_model",
            description="用于评分的LLM模型名称（可选），使用系统默认judge模型",
            example="judge_model"
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