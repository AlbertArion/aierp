#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
SQLite数据库管理器
提供本地数据库支持，替代MongoDB
"""

import sqlite3
import json
import logging
from typing import Any, Optional, Dict, List
from datetime import datetime, date
import os

logger = logging.getLogger(__name__)

class SQLiteDatabase:
    """SQLite数据库管理器"""
    
    def __init__(self, db_path: str = "aierp.db"):
        self.db_path = db_path
        self.conn = None
        self._init_database()
    
    def _init_database(self):
        """初始化数据库和表结构"""
        try:
            self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self.conn.row_factory = sqlite3.Row  # 使结果可以按列名访问
            
            # 创建表结构
            self._create_tables()
            logger.info(f"SQLite数据库初始化成功: {self.db_path}")
            
        except Exception as e:
            logger.error(f"SQLite数据库初始化失败: {e}")
            raise
    
    def _create_tables(self):
        """创建数据库表"""
        cursor = self.conn.cursor()
        
        # 员工表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS employees (
                id TEXT PRIMARY KEY,
                employee_no TEXT UNIQUE,
                name TEXT NOT NULL,
                pinyin TEXT,
                phone TEXT,
                email TEXT,
                position TEXT,
                department_id TEXT,
                status TEXT,
                hire_date DATE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 项目表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS projects (
                id TEXT PRIMARY KEY,
                project_code TEXT UNIQUE,
                project_name TEXT NOT NULL,
                project_type TEXT,
                status TEXT,
                manager_id TEXT,
                start_date DATE,
                end_date DATE,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 部门表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS departments (
                id TEXT PRIMARY KEY,
                department_code TEXT UNIQUE,
                department_name TEXT NOT NULL,
                parent_id TEXT,
                manager_id TEXT,
                status TEXT,
                level INTEGER DEFAULT 1,
                sort_order INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 报工记录表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS work_reports (
                id TEXT PRIMARY KEY,
                employee_id TEXT NOT NULL,
                project_id TEXT NOT NULL,
                department_id TEXT NOT NULL,
                report_date DATE NOT NULL,
                work_hours REAL NOT NULL,
                work_content TEXT,
                work_location TEXT,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (employee_id) REFERENCES employees (id),
                FOREIGN KEY (project_id) REFERENCES projects (id),
                FOREIGN KEY (department_id) REFERENCES departments (id)
            )
        ''')
        
        # 创建索引
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_work_reports_employee ON work_reports(employee_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_work_reports_project ON work_reports(project_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_work_reports_date ON work_reports(report_date)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_work_reports_status ON work_reports(status)')
        
        # 批量核价：任务表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS pricing_batch_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trace_id TEXT UNIQUE NOT NULL,
                task_name TEXT,
                source_file_name TEXT,
                total_rows INTEGER DEFAULT 0,
                normalized_columns TEXT,
                status TEXT DEFAULT 'uploaded',
                stats_json TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                approved_at TIMESTAMP,
                approver TEXT
            )
        ''')

        # 批量核价：结果表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS pricing_batch_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trace_id TEXT NOT NULL,
                row_index INTEGER,
                material_code TEXT,
                material_name TEXT,
                specification TEXT,
                process_requirements TEXT,
                quantity REAL,
                uom TEXT,
                estimated_price REAL,
                currency TEXT,
                status TEXT,
                reason_or_notes TEXT,
                rule_version TEXT,
                extra_json TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        cursor.execute('CREATE INDEX IF NOT EXISTS idx_pricing_batch_results_trace ON pricing_batch_results(trace_id)')

        # SAP报工相关表
        # AFKO - 订单主数据表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS afko (
                id TEXT PRIMARY KEY,
                mandt TEXT NOT NULL,
                aufnr TEXT NOT NULL,
                gltrp DATE,
                gstrp DATE,
                ftrms DATE,
                gltrs DATE,
                gstrs DATE,
                gstri DATE,
                getri DATE,
                gltri DATE,
                ftrmi DATE,
                ftrmp DATE,
                rsnum TEXT,
                gasmg REAL,
                gamng REAL,
                gmein TEXT,
                plnbez TEXT,
                plnty TEXT,
                plnnr TEXT,
                plnaw TEXT,
                plnal TEXT,
                pverw TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # AFPO - 订单项目表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS afpo (
                id TEXT PRIMARY KEY,
                mandt TEXT NOT NULL,
                aufnr TEXT NOT NULL,
                posnr TEXT NOT NULL,
                psobs TEXT,
                qunum TEXT,
                qupos TEXT,
                projn TEXT,
                plnum TEXT,
                strmp DATE,
                etrmp DATE,
                kdauf TEXT,
                kdpos TEXT,
                kdein TEXT,
                beskz TEXT,
                psamg REAL,
                psmng REAL,
                wemng REAL,
                iamng REAL,
                amein TEXT,
                meins TEXT,
                matnr TEXT,
                pamng REAL,
                pgmng REAL,
                knttp TEXT,
                tpauf TEXT,
                ltrmi DATE,
                ltrmp DATE,
                kalnr TEXT,
                uebto TEXT,
                uebtk TEXT,
                untto TEXT,
                insmk TEXT,
                wepos TEXT,
                bwtar TEXT,
                bwty TEXT,
                pwerk TEXT,
                lgort TEXT,
                umrez TEXT,
                umren TEXT,
                webaz TEXT,
                elikz TEXT,
                safnr TEXT,
                verid TEXT,
                sernr TEXT,
                techs TEXT,
                dwerk TEXT,
                dauty TEXT,
                dauat TEXT,
                dgltp DATE,
                dglts DATE,
                dfrei TEXT,
                dnrel TEXT,
                verto TEXT,
                sobkz TEXT,
                kzvbr TEXT,
                wewrt REAL,
                weunb TEXT,
                ablad TEXT,
                wempf TEXT,
                charg TEXT,
                gsber TEXT,
                weaed DATE,
                cuobj TEXT,
                kbnkz TEXT,
                arsnr TEXT,
                arsps TEXT,
                krsnr TEXT,
                krsp TEXT,
                kckey TEXT,
                rtp01 TEXT,
                rtp02 TEXT,
                rtp03 TEXT,
                rtp04 TEXT,
                ksvon TEXT,
                ksbis TEXT,
                objnp TEXT,
                ndisr TEXT,
                vfmng REAL,
                gsbtr REAL,
                kzavc TEXT,
                kzbws TEXT,
                xloek TEXT,
                sernp TEXT,
                anzsn TEXT,
                objtype TEXT,
                ch_proc TEXT,
                fxpr TEXT,
                cuobj_root TEXT,
                berid TEXT,
                techs_copy TEXT,
                sgt_scat TEXT,
                kunnr2 TEXT,
                mill_oc_aufnr_u TEXT,
                mill_oc_rumng REAL,
                mill_oc_sort TEXT,
                ebel TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # AFVC - 订单工序表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS afvc (
                id TEXT PRIMARY KEY,
                mandt TEXT NOT NULL,
                aufpl TEXT NOT NULL,
                aplzl TEXT NOT NULL,
                plnfl REAL,
                plnkn REAL,
                plnal TEXT,
                plnty TEXT,
                vintv TEXT,
                plnnr TEXT,
                zaehl TEXT,
                vornr TEXT,
                steus TEXT,
                arbid TEXT,
                pdest TEXT,
                werks TEXT,
                ktsch TEXT,
                ltxa1 TEXT,
                ltxa2 TEXT,
                txtsp TEXT,
                vplty TEXT,
                vplnr TEXT,
                vplal TEXT,
                vplfl TEXT,
                vgwts TEXT,
                lar01 TEXT,
                lar02 TEXT,
                lar03 TEXT,
                lar04 TEXT,
                lar05 TEXT,
                lar06 TEXT,
                zerma TEXT,
                zgdat DATE,
                zcode TEXT,
                zulnr TEXT,
                loanz TEXT,
                loart TEXT,
                rsanz TEXT,
                qualf TEXT,
                anzma TEXT,
                rfgrp TEXT,
                rfsch TEXT,
                rasch TEXT,
                aufak TEXT,
                logrp TEXT,
                uemus TEXT,
                uekan TEXT,
                flies TEXT,
                spmus TEXT,
                splim TEXT,
                ablipkz TEXT,
                rstra TEXT,
                sumnr TEXT,
                sortl TEXT,
                lifnr TEXT,
                preis REAL,
                peinh TEXT,
                sakto TEXT,
                waers TEXT,
                infnr TEXT,
                esokz TEXT,
                ekorg TEXT,
                ekgrp TEXT,
                kzlgf TEXT,
                kzwrtf TEXT,
                matkl TEXT,
                ddehn TEXT,
                anzzl TEXT,
                prznt TEXT,
                mlstn TEXT,
                pprio TEXT,
                bukrs TEXT,
                anfko TEXT,
                anfkokrs TEXT,
                indet TEXT,
                larnt TEXT,
                prkst TEXT,
                aplfl TEXT,
                rueck TEXT,
                rmzhl TEXT,
                projn TEXT,
                objnr TEXT,
                spanz TEXT,
                bedid TEXT,
                bedzl TEXT,
                banfn TEXT,
                bnfpo TEXT,
                lek01 TEXT,
                lek02 TEXT,
                lek03 TEXT,
                lek04 TEXT,
                lek05 TEXT,
                lek06 TEXT,
                selkz TEXT,
                kalid TEXT,
                frsp TEXT,
                stdkn TEXT,
                anlzu TEXT,
                istru TEXT,
                isty TEXT,
                isnr TEXT,
                istkn TEXT,
                istpo TEXT,
                iupoz TEXT,
                ebort TEXT,
                vertl TEXT,
                leknw TEXT,
                nprio TEXT,
                pvzkn TEXT,
                phflg TEXT,
                phseq TEXT,
                knobj TEXT,
                erfsicht TEXT,
                qppktabs TEXT,
                otype TEXT,
                objektid TEXT,
                qlkapar TEXT,
                rstuf TEXT,
                nptxtky TEXT,
                subsys TEXT,
                pspnr TEXT,
                packno TEXT,
                txjcd TEXT,
                scope TEXT,
                gsber TEXT,
                prctr TEXT,
                no_disp TEXT,
                qkzprzeit TEXT,
                qkzztmg1 TEXT,
                qkzprmeng TEXT,
                qkzprfrei TEXT,
                kzfeat TEXT,
                qkztlsbest TEXT,
                aennr TEXT,
                cuobj_arb TEXT,
                evgew REAL,
                arbii TEXT,
                werki TEXT,
                cy_seqnr TEXT,
                kapt_puffr TEXT,
                ebel TEXT,
                ebelp TEXT,
                wempf TEXT,
                ablad TEXT,
                clasf TEXT,
                frunv TEXT,
                zschl TEXT,
                kalsm TEXT,
                sched_end DATE,
                netzkont TEXT,
                owaer TEXT,
                afnam TEXT,
                bednr TEXT,
                kzfix TEXT,
                pernr TEXT,
                frdlb TEXT,
                qpart TEXT,
                loekz TEXT,
                wkurs REAL,
                prod_act TEXT,
                fplnr TEXT,
                objtype TEXT,
                ch_proc TEXT,
                klvar TEXT,
                kalnr TEXT,
                fordn TEXT,
                fordp TEXT,
                mat_prkst TEXT,
                prz01 TEXT,
                rfpnt TEXT,
                func_area TEXT,
                techs TEXT,
                adpsp TEXT,
                rfippnt TEXT,
                mes_operid TEXT,
                mes_stepid TEXT,
                cum_cuguid TEXT,
                isdfps_objnr TEXT,
                afvc_status TEXT,
                mill_oc_aufnr_mo TEXT,
                wty_ind TEXT,
                tplnr TEXT,
                equnr TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # AFVV - 订单工序时间表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS afvv (
                id TEXT PRIMARY KEY,
                mandt TEXT NOT NULL,
                aufpl TEXT NOT NULL,
                aplzl TEXT NOT NULL,
                meinh TEXT,
                umren TEXT,
                umrez TEXT,
                bmsch TEXT,
                zmerh TEXT,
                zeier TEXT,
                vge01 TEXT,
                vgw01 REAL,
                vge02 TEXT,
                vgw02 REAL,
                vge03 TEXT,
                vgw03 REAL,
                vge04 TEXT,
                vgw04 REAL,
                vge05 TEXT,
                vgw05 REAL,
                vge06 TEXT,
                vgw06 REAL,
                zeimu TEXT,
                zminu TEXT,
                minwe TEXT,
                zeimb TEXT,
                zminb TEXT,
                zeilm TEXT,
                zlmax TEXT,
                zeilp TEXT,
                zlpro TEXT,
                zeiwn TEXT,
                zwnor TEXT,
                zeiwm TEXT,
                zwmin TEXT,
                zeitn TEXT,
                ztnor TEXT,
                zeitm TEXT,
                ztmin TEXT,
                plifz TEXT,
                dauno TEXT,
                daune TEXT,
                daumi TEXT,
                daume TEXT,
                einsa TEXT,
                einse TEXT,
                arbei TEXT,
                arbeh TEXT,
                mgvrg TEXT,
                asvrg TEXT,
                lmnag TEXT,
                xmnag TEXT,
                gmnag TEXT,
                ism01 TEXT,
                ism02 TEXT,
                ism03 TEXT,
                ism04 TEXT,
                ism05 TEXT,
                ism06 TEXT,
                ismnw TEXT,
                fsavd DATE,
                fsavz TEXT,
                fssbd DATE,
                fssbz TEXT,
                fssad DATE,
                fssaz TEXT,
                fsedd DATE,
                fsedz TEXT,
                fssld DATE,
                fsslz TEXT,
                fseld DATE,
                fselz TEXT,
                ssavd DATE,
                ssavz TEXT,
                sssbd DATE,
                sssbz TEXT,
                sssad DATE,
                sssaz TEXT,
                ssedd DATE,
                ssedz TEXT,
                sssld DATE,
                ssslz TEXT,
                sseld DATE,
                sselz TEXT,
                isavd DATE,
                ieavd DATE,
                isdd DATE,
                isdz TEXT,
                ierd DATE,
                ierz TEXT,
                isbd DATE,
                isbz TEXT,
                iebd DATE,
                iebz TEXT,
                isad DATE,
                isaz TEXT,
                iedd DATE,
                iedz TEXT,
                pedd DATE,
                pedz TEXT,
                puffr TEXT,
                pufgs TEXT,
                ntanf DATE,
                ntanz TEXT,
                ntend DATE,
                ntenz TEXT,
                ewstd DATE,
                ewstz TEXT,
                ewend DATE,
                ewenz TEXT,
                ewdan TEXT,
                ewdne TEXT,
                ewdam TEXT,
                ewdme TEXT,
                ewste TEXT,
                ewsta TEXT,
                wartz TEXT,
                wrtze TEXT,
                ruest TEXT,
                rstze TEXT,
                bearz TEXT,
                beaze TEXT,
                abrue TEXT,
                aruze TEXT,
                liegz TEXT,
                ligze TEXT,
                tranz TEXT,
                traze TEXT,
                iserh TEXT,
                ofm01 TEXT,
                ofm02 TEXT,
                ofm03 TEXT,
                ofm04 TEXT,
                ofm05 TEXT,
                ofm06 TEXT,
                ofmnw TEXT,
                bzoffb TEXT,
                ehoffb TEXT,
                offstb TEXT,
                offste TEXT,
                bzoffe TEXT,
                ehoffe TEXT,
                fpavd DATE,
                fpavz TEXT,
                fpedd DATE,
                fpedz TEXT,
                spavd DATE,
                spavz TEXT,
                spedd DATE,
                spedz TEXT,
                beazp TEXT,
                pufgp TEXT,
                puffp TEXT,
                bearp TEXT,
                epanf DATE,
                epanz TEXT,
                epend DATE,
                epenz TEXT,
                pdau TEXT,
                pdae TEXT,
                knote TEXT,
                vstzw TEXT,
                vstga TEXT,
                qrastzeht TEXT,
                qrastzfak TEXT,
                qrastmeng TEXT,
                qrastereh TEXT,
                aufkt TEXT,
                rmnag TEXT,
                ile01 TEXT,
                ile02 TEXT,
                ile03 TEXT,
                ile04 TEXT,
                ile05 TEXT,
                ile06 TEXT,
                rwfak TEXT,
                iprz1 TEXT,
                ipre1 TEXT,
                iprk1 TEXT,
                takt TEXT,
                oprz1 TEXT,
                opre1 TEXT,
                pspm_indicator TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # AUFK - 订单主数据表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS aufk (
                id TEXT PRIMARY KEY,
                mandt TEXT NOT NULL,
                aufnr TEXT NOT NULL,
                auart TEXT,
                autyp TEXT,
                refnr TEXT,
                ernam TEXT,
                erdat DATE,
                aenam TEXT,
                aedat DATE,
                ktext TEXT,
                ltext TEXT,
                bukrs TEXT,
                werks TEXT,
                gsber TEXT,
                kokrs TEXT,
                cckey TEXT,
                kostv TEXT,
                stort TEXT,
                sowrk TEXT,
                astkz TEXT,
                waers TEXT,
                astnr TEXT,
                stdat DATE,
                estnr TEXT,
                phas0 TEXT,
                phas1 TEXT,
                phas2 TEXT,
                phas3 TEXT,
                pdat1 DATE,
                pdat2 DATE,
                pdat3 DATE,
                idat1 DATE,
                idat2 DATE,
                idat3 DATE,
                objid TEXT,
                vogrp TEXT,
                loekz TEXT,
                plgkz TEXT,
                kvewe TEXT,
                kappl TEXT,
                kalsm TEXT,
                zschl TEXT,
                abkrs TEXT,
                kstar TEXT,
                kostl TEXT,
                saknr TEXT,
                setnm TEXT,
                cycle TEXT,
                sdate DATE,
                seqnr TEXT,
                user0 TEXT,
                user1 TEXT,
                user2 TEXT,
                user3 TEXT,
                user4 TEXT,
                user5 TEXT,
                user6 TEXT,
                user7 TEXT,
                user8 TEXT,
                user9 TEXT,
                objnr TEXT,
                prctr TEXT,
                pspel TEXT,
                awsls TEXT,
                abgsl TEXT,
                txjcd TEXT,
                func_area TEXT,
                scope TEXT,
                plint TEXT,
                kdauf TEXT,
                kdpos TEXT,
                aufex TEXT,
                ivpro TEXT,
                logsystem TEXT,
                flg_mltps TEXT,
                abukr TEXT,
                akstl TEXT,
                sizecl TEXT,
                izwek TEXT,
                umwkz TEXT,
                kstempf TEXT,
                zschm TEXT,
                pkosa TEXT,
                anfaufnr TEXT,
                procnr TEXT,
                proty TEXT,
                rsord TEXT,
                bemot TEXT,
                adrnra TEXT,
                erfzeit TEXT,
                aezeit TEXT,
                cstg_vrnt TEXT,
                costestnr TEXT,
                veraa_user TEXT,
                zbukrs TEXT,
                zzcpkg TEXT,
                zzkhyq TEXT,
                zztuhao TEXT,
                zzjsfa TEXT,
                zzxqbm TEXT,
                zzyfxmh TEXT,
                zzwxy TEXT,
                zzjy TEXT,
                zzjyjg TEXT,
                zzgzfx TEXT,
                zzbf TEXT,
                zzsernr TEXT,
                zzwtms TEXT,
                zzgzdm TEXT,
                zggyq TEXT,
                zxpl TEXT,
                zgg TEXT,
                zfg TEXT,
                vname TEXT,
                recid TEXT,
                etype TEXT,
                otype TEXT,
                jv_jibcl TEXT,
                jv_jibsa TEXT,
                jv_oco TEXT,
                cum_indcu TEXT,
                cum_cmnum TEXT,
                cum_auest TEXT,
                cum_desnum TEXT,
                vaplz TEXT,
                wawrk TEXT,
                ferc_ind TEXT,
                aufk_status TEXT,
                claim_control TEXT,
                update_needed TEXT,
                update_control TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # JEST - 对象状态表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS jest (
                id TEXT PRIMARY KEY,
                mandt TEXT NOT NULL,
                objnr TEXT NOT NULL,
                stat TEXT NOT NULL,
                inact TEXT,
                chgnr TEXT,
                dataaging TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # MAKT - 物料描述表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS makt (
                id TEXT PRIMARY KEY,
                mandt TEXT NOT NULL,
                matnr TEXT NOT NULL,
                spras TEXT NOT NULL,
                maktx TEXT,
                maktg TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # 创建索引
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_afko_aufnr ON afko(aufnr)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_afko_mandt ON afko(mandt)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_afpo_aufnr ON afpo(aufnr)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_afpo_matnr ON afpo(matnr)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_afvc_aufpl ON afvc(aufpl)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_afvv_aufpl ON afvv(aufpl)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_aufk_aufnr ON aufk(aufnr)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_jest_objnr ON jest(objnr)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_makt_matnr ON makt(matnr)')

        self.conn.commit()

        # 兼容新增列：为任务表补充文件路径列
        try:
            self._ensure_column_exists('pricing_batch_tasks', 'source_file_path', 'TEXT')
        except Exception:
            pass

        # 兼容旧库：若缺列则动态补齐
        self._ensure_column_exists('employees', 'status', 'TEXT')
        self._ensure_column_exists('projects', 'status', 'TEXT')
        self._ensure_column_exists('departments', 'status', 'TEXT')

    def _ensure_column_exists(self, table: str, column: str, col_type: str) -> None:
        """确保表存在指定列，不存在则添加"""
        try:
            cur = self.conn.cursor()
            cur.execute(f"PRAGMA table_info({table})")
            cols = [row[1] for row in cur.fetchall()]
            if column not in cols:
                cur.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
                self.conn.commit()
        except Exception as e:
            logger.warning(f"检查/添加列失败 {table}.{column}: {e}")
    
    def get_collection(self, collection_name: str):
        """获取集合对象（模拟MongoDB接口）"""
        return SQLiteCollection(self.conn, collection_name)
    
    def close(self):
        """关闭数据库连接"""
        if self.conn:
            self.conn.close()

class SQLiteCollection:
    """SQLite集合模拟器（模拟MongoDB Collection接口）"""
    
    def __init__(self, conn, table_name: str):
        self.conn = conn
        self.table_name = table_name
        self.cursor = conn.cursor()
    
    def find_one(self, filter_dict: Dict = None):
        """查找单条记录"""
        if not filter_dict:
            sql = f"SELECT * FROM {self.table_name} LIMIT 1"
            params = []
        else:
            where_clause, params = self._build_where_clause(filter_dict)
            sql = f"SELECT * FROM {self.table_name} WHERE {where_clause} LIMIT 1"
        
        self.cursor.execute(sql, params)
        row = self.cursor.fetchone()
        return dict(row) if row else None
    
    def find(self, filter_dict: Dict = None):
        """查找多条记录"""
        if not filter_dict:
            sql = f"SELECT * FROM {self.table_name}"
            params = []
        else:
            where_clause, params = self._build_where_clause(filter_dict)
            sql = f"SELECT * FROM {self.table_name} WHERE {where_clause}"
        
        self.cursor.execute(sql, params)
        rows = self.cursor.fetchall()
        return [dict(row) for row in rows]
    
    def insert_one(self, document: Dict):
        """插入单条记录"""
        # 处理日期类型
        processed_doc = self._process_document(document)
        
        columns = list(processed_doc.keys())
        placeholders = ['?' for _ in columns]
        values = list(processed_doc.values())
        
        sql = f"INSERT INTO {self.table_name} ({', '.join(columns)}) VALUES ({', '.join(placeholders)})"
        self.cursor.execute(sql, values)
        self.conn.commit()
        
        # 返回插入结果对象
        return type('Result', (), {'inserted_id': processed_doc.get('id', 'unknown')})()
    
    def insert_many(self, documents: List[Dict]):
        """插入多条记录"""
        if not documents:
            return type('Result', (), {'inserted_ids': []})()
        
        # 处理日期类型
        processed_docs = [self._process_document(doc) for doc in documents]
        
        columns = list(processed_docs[0].keys())
        placeholders = ['?' for _ in columns]
        
        sql = f"INSERT INTO {self.table_name} ({', '.join(columns)}) VALUES ({', '.join(placeholders)})"
        
        values_list = [list(doc.values()) for doc in processed_docs]
        self.cursor.executemany(sql, values_list)
        self.conn.commit()
        
        inserted_ids = [doc.get('id', 'unknown') for doc in processed_docs]
        return type('Result', (), {'inserted_ids': inserted_ids})()
    
    def update_one(self, filter_dict: Dict, update_dict: Dict):
        """更新单条记录"""
        where_clause, where_params = self._build_where_clause(filter_dict)
        
        set_clause = ', '.join([f"{key} = ?" for key in update_dict.keys()])
        params = list(update_dict.values()) + where_params
        
        sql = f"UPDATE {self.table_name} SET {set_clause} WHERE {where_clause}"
        self.cursor.execute(sql, params)
        self.conn.commit()
        
        return type('Result', (), {'modified_count': self.cursor.rowcount})()
    
    def delete_one(self, filter_dict: Dict):
        """删除单条记录"""
        where_clause, params = self._build_where_clause(filter_dict)
        sql = f"DELETE FROM {self.table_name} WHERE {where_clause}"
        self.cursor.execute(sql, params)
        self.conn.commit()
        
        return type('Result', (), {'deleted_count': self.cursor.rowcount})()
    
    def count_documents(self, filter_dict: Dict = None):
        """统计文档数量"""
        if not filter_dict:
            sql = f"SELECT COUNT(*) FROM {self.table_name}"
            params = []
        else:
            where_clause, params = self._build_where_clause(filter_dict)
            sql = f"SELECT COUNT(*) FROM {self.table_name} WHERE {where_clause}"
        
        self.cursor.execute(sql, params)
        return self.cursor.fetchone()[0]
    
    def aggregate(self, pipeline: List[Dict]):
        """聚合查询（简化实现）"""
        # 这里实现基本的聚合功能
        if not pipeline:
            return []
        
        # 简单实现 $group 聚合
        for stage in pipeline:
            if '$group' in stage:
                group = stage['$group']
                if group.get('_id') is None:  # 全局聚合
                    # 计算总数和总和
                    sql = f"SELECT COUNT(*) as total_reports, SUM(work_hours) as total_hours, AVG(work_hours) as avg_hours FROM {self.table_name}"
                    self.cursor.execute(sql)
                    result = self.cursor.fetchone()
                    
                    return [{
                        'total_reports': result[0] or 0,
                        'total_hours': result[1] or 0,
                        'avg_hours': result[2] or 0
                    }]
        
        return []
    
    def _build_where_clause(self, filter_dict: Dict):
        """构建WHERE子句"""
        if not filter_dict:
            return "1=1", []
        
        conditions = []
        params = []
        
        for key, value in filter_dict.items():
            if key == '$or':
                # 处理 $or 查询
                or_conditions = []
                for or_condition in value:
                    or_where, or_params = self._build_where_clause(or_condition)
                    or_conditions.append(f"({or_where})")
                    params.extend(or_params)
                conditions.append(f"({' OR '.join(or_conditions)})")
            elif isinstance(value, dict):
                # 处理复杂查询条件
                for op, op_value in value.items():
                    if op == '$regex':
                        conditions.append(f"{key} LIKE ?")
                        params.append(f"%{op_value}%")
                    elif op == '$gte':
                        conditions.append(f"{key} >= ?")
                        params.append(op_value)
                    elif op == '$lte':
                        conditions.append(f"{key} <= ?")
                        params.append(op_value)
                    elif op == '$options':
                        continue  # 忽略选项
                    else:
                        conditions.append(f"{key} = ?")
                        params.append(op_value)
            else:
                conditions.append(f"{key} = ?")
                params.append(value)
        
        return " AND ".join(conditions), params
    
    def _process_document(self, document: Dict):
        """处理文档数据，转换日期等特殊类型"""
        processed = document.copy()
        
        # 转换特殊类型
        for key, value in processed.items():
            if isinstance(value, (datetime, date)):
                processed[key] = value.isoformat()
            elif isinstance(value, list):
                # 将列表转换为JSON字符串
                processed[key] = json.dumps(value, ensure_ascii=False)
            elif isinstance(value, dict):
                # 将字典转换为JSON字符串
                processed[key] = json.dumps(value, ensure_ascii=False)
            elif hasattr(value, 'value') and hasattr(value, '__class__'):  # Enum类型
                processed[key] = value.value
        
        return processed

# 全局数据库实例
_sqlite_db_instance = None

def get_sqlite_db():
    """获取SQLite数据库实例"""
    global _sqlite_db_instance
    if _sqlite_db_instance is None:
        # 数据库文件现在位于app/db目录下
        db_path = os.path.join(os.path.dirname(__file__), "aierp.db")
        _sqlite_db_instance = SQLiteDatabase(db_path)
    return _sqlite_db_instance
