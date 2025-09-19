"""
DataX配置生成器
支持SAP、用友等ERP系统的数据同步配置生成
"""

import json
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from enum import Enum


class DataSourceType(Enum):
    SAP = "sap"
    UFIDA = "ufida"
    ORACLE = "oracle"
    MYSQL = "mysql"


@dataclass
class DataXJobConfig:
    """DataX作业配置"""
    job_id: str
    source_type: DataSourceType
    source_config: Dict[str, Any]
    target_config: Dict[str, Any]
    tables: List[str]
    parallel: int = 3
    speed_bytes: int = 1048576  # 1MB/s
    speed_records: int = 1000   # 1000 records/s


class DataXConfigGenerator:
    """DataX配置生成器"""
    
    def __init__(self):
        self.sap_reader_template = {
            "name": "sapreader",
            "parameter": {
                "username": "",
                "password": "",
                "host": "",
                "port": 8000,
                "client": "000",
                "system_number": "00",
                "language": "ZH",
                "table": "",
                "column": [],
                "where": "",
                "split_pk": "",
                "split_mode": "range"
            }
        }
        
        self.ufida_reader_template = {
            "name": "mysqlreader",
            "parameter": {
                "username": "",
                "password": "",
                "column": [],
                "split_pk": "",
                "connection": [{
                    "table": [],
                    "jdbcUrl": []
                }]
            }
        }
        
        self.snowflake_writer_template = {
            "name": "snowflakewriter",
            "parameter": {
                "username": "",
                "password": "",
                "column": [],
                "preSql": [],
                "postSql": [],
                "connection": [{
                    "jdbcUrl": "",
                    "table": []
                }]
            }
        }

    def generate_sap_config(self, job_id: str, tables: List[str], 
                          sap_config: Dict[str, Any]) -> Dict[str, Any]:
        """生成SAP数据源配置"""
        config = {
            "job": {
                "setting": {
                    "speed": {
                        "channel": self._calculate_channel_count(tables),
                        "byte": 1048576,
                        "record": 1000
                    },
                    "errorLimit": {
                        "record": 0,
                        "percentage": 0.02
                    }
                },
                "content": []
            }
        }
        
        for table in tables:
            reader = self.sap_reader_template.copy()
            reader["parameter"].update({
                "username": sap_config.get("username", ""),
                "password": sap_config.get("password", ""),
                "host": sap_config.get("host", ""),
                "port": sap_config.get("port", 8000),
                "client": sap_config.get("client", "000"),
                "system_number": sap_config.get("system_number", "00"),
                "table": table,
                "column": self._get_table_columns(table, "sap"),
                "where": sap_config.get("where", ""),
                "split_pk": self._get_primary_key(table, "sap")
            })
            
            writer = self.snowflake_writer_template.copy()
            writer["parameter"].update({
                "username": sap_config.get("snowflake_username", ""),
                "password": sap_config.get("snowflake_password", ""),
                "connection": [{
                    "jdbcUrl": sap_config.get("snowflake_url", ""),
                    "table": [f"{sap_config.get('snowflake_schema', 'PUBLIC')}.{table}"]
                }],
                "column": self._get_table_columns(table, "snowflake"),
                "preSql": [f"TRUNCATE TABLE {sap_config.get('snowflake_schema', 'PUBLIC')}.{table}"],
                "postSql": []
            })
            
            config["job"]["content"].append({
                "reader": reader,
                "writer": writer
            })
        
        return config

    def generate_ufida_config(self, job_id: str, tables: List[str],
                            ufida_config: Dict[str, Any]) -> Dict[str, Any]:
        """生成用友数据源配置"""
        config = {
            "job": {
                "setting": {
                    "speed": {
                        "channel": self._calculate_channel_count(tables),
                        "byte": 1048576,
                        "record": 1000
                    },
                    "errorLimit": {
                        "record": 0,
                        "percentage": 0.02
                    }
                },
                "content": []
            }
        }
        
        for table in tables:
            reader = self.ufida_reader_template.copy()
            reader["parameter"].update({
                "username": ufida_config.get("username", ""),
                "password": ufida_config.get("password", ""),
                "connection": [{
                    "jdbcUrl": [ufida_config.get("jdbc_url", "")],
                    "table": [table]
                }],
                "column": self._get_table_columns(table, "ufida"),
                "split_pk": self._get_primary_key(table, "ufida")
            })
            
            writer = self.snowflake_writer_template.copy()
            writer["parameter"].update({
                "username": ufida_config.get("snowflake_username", ""),
                "password": ufida_config.get("snowflake_password", ""),
                "connection": [{
                    "jdbcUrl": ufida_config.get("snowflake_url", ""),
                    "table": [f"{ufida_config.get('snowflake_schema', 'PUBLIC')}.{table}"]
                }],
                "column": self._get_table_columns(table, "snowflake"),
                "preSql": [f"TRUNCATE TABLE {ufida_config.get('snowflake_schema', 'PUBLIC')}.{table}"],
                "postSql": []
            })
            
            config["job"]["content"].append({
                "reader": reader,
                "writer": writer
            })
        
        return config

    def _calculate_channel_count(self, tables: List[str]) -> int:
        """计算通道数量"""
        return min(len(tables) * 2, 10)  # 每个表最多2个通道，总通道数不超过10

    def _get_table_columns(self, table: str, source_type: str) -> List[str]:
        """获取表字段列表（模拟实现，实际应从元数据获取）"""
        # 这里应该从数据库元数据获取，现在返回模拟数据
        common_columns = ["id", "created_at", "updated_at"]
        
        if source_type == "sap":
            if "sales" in table.lower():
                return common_columns + ["vbeln", "kunnr", "netwr", "waerk", "erdat"]
            elif "finance" in table.lower():
                return common_columns + ["bukrs", "gjahr", "belnr", "dmbtr", "waers"]
        elif source_type == "ufida":
            if "sales" in table.lower():
                return common_columns + ["order_no", "customer_code", "amount", "currency", "order_date"]
            elif "finance" in table.lower():
                return common_columns + ["company_code", "fiscal_year", "voucher_no", "amount", "currency"]
        elif source_type == "snowflake":
            # Snowflake目标表字段
            return common_columns + ["source_system", "sync_time", "sync_status"]
        
        return common_columns

    def _get_primary_key(self, table: str, source_type: str) -> str:
        """获取主键字段"""
        if source_type == "sap":
            if "sales" in table.lower():
                return "vbeln"
            elif "finance" in table.lower():
                return "belnr"
        elif source_type == "ufida":
            if "sales" in table.lower():
                return "order_no"
            elif "finance" in table.lower():
                return "voucher_no"
        
        return "id"

    def save_config(self, config: Dict[str, Any], file_path: str) -> bool:
        """保存配置到文件"""
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"保存DataX配置失败: {e}")
            return False

    def load_config(self, file_path: str) -> Optional[Dict[str, Any]]:
        """从文件加载配置"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"加载DataX配置失败: {e}")
            return None
