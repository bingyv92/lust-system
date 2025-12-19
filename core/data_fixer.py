"""启动时自动修复淫乱度数据的工具"""
from typing import Dict, Any
from src.plugin_system.apis import storage_api
from src.common.logger import get_logger

logger = get_logger("mofox_period_plugin")

def fix_all_lust_data(lust_system_instance):
    """修复所有用户的淫乱度数据
    
    Args:
        lust_system_instance: LustSystem 实例
    """
    try:
        plugin_storage = storage_api.get_local_storage("mofox_period_plugin")
        all_data = plugin_storage.get_all()
        
        fixed_count = 0
        for key, data in all_data.items():
            if not key.startswith("lust_system:user_data:"):
                continue
            
            user_id = key.replace("lust_system:user_data:", "")
            
            # 检查并修复 current_stage
            orgasm_value = data.get("orgasm_value", 0)
            stored_stage = data.get("current_stage", "")
            correct_stage = lust_system_instance._determine_stage(orgasm_value)
            
            if stored_stage != correct_stage:
                logger.warning(f"[数据修复] 用户{user_id}: stage错误 '{stored_stage}' -> '{correct_stage}' (orgasm={orgasm_value:.1f})")
                data["current_stage"] = correct_stage
                plugin_storage.set(key, data)
                fixed_count += 1
            
            # 检查 max_orgasms 是否与 lust_level 一致
            lust_level = data.get("lust_level", 0.3)
            stored_max = data.get("max_orgasms", 0)
            correct_max = lust_system_instance.get_max_orgasms(lust_level)
            
            if stored_max != correct_max:
                logger.warning(f"[数据修复] 用户{user_id}: max_orgasms错误 {stored_max} -> {correct_max}")
                data["max_orgasms"] = correct_max
                # 同时修复 remaining_orgasms
                remaining = data.get("remaining_orgasms", 0)
                data["remaining_orgasms"] = min(remaining, correct_max)
                plugin_storage.set(key, data)
                fixed_count += 1
        
        if fixed_count > 0:
            logger.info(f"[启动修复] 修复了 {fixed_count} 条数据")
        else:
            logger.info(f"[启动检查] 所有数据完整，无需修复")
            
    except Exception as e:
        logger.error(f"[启动修复] 失败: {e}", exc_info=True)
