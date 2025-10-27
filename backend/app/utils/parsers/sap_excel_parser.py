#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
SAP报工数据Excel解析器
用于解析报工一览表所需数据.xlsx文件中的各个工作表数据
"""

import pandas as pd
import uuid
from datetime import datetime, date
from typing import Dict, List, Any, Optional
import logging

logger = logging.getLogger(__name__)

class SAPExcelParser:
    """SAP报工数据Excel解析器"""
    
    def __init__(self, excel_file_path: str):
        self.excel_file_path = excel_file_path
        self.sheets_data = {}
        
    def parse_all_sheets(self) -> Dict[str, List[Dict[str, Any]]]:
        """解析所有工作表数据"""
        try:
            # 读取Excel文件
            excel_file = pd.ExcelFile(self.excel_file_path)
            
            # 解析各个工作表
            for sheet_name in excel_file.sheet_names:
                if sheet_name == '示例数据':
                    continue  # 跳过示例数据表
                    
                logger.info(f"正在解析工作表: {sheet_name}")
                df = pd.read_excel(self.excel_file_path, sheet_name=sheet_name)
                
                # 根据工作表名称调用对应的解析方法
                if sheet_name == 'AFKO':
                    self.sheets_data[sheet_name] = self._parse_afko(df)
                elif sheet_name == 'AFPO':
                    self.sheets_data[sheet_name] = self._parse_afpo(df)
                elif sheet_name == 'AFVC':
                    self.sheets_data[sheet_name] = self._parse_afvc(df)
                elif sheet_name == 'AFVV':
                    self.sheets_data[sheet_name] = self._parse_afvv(df)
                elif sheet_name == 'AUFK':
                    self.sheets_data[sheet_name] = self._parse_aufk(df)
                elif sheet_name == 'JEST':
                    self.sheets_data[sheet_name] = self._parse_jest(df)
                elif sheet_name == 'MAKT':
                    self.sheets_data[sheet_name] = self._parse_makt(df)
                else:
                    logger.warning(f"未知的工作表: {sheet_name}")
                    
            logger.info(f"成功解析 {len(self.sheets_data)} 个工作表")
            return self.sheets_data
            
        except Exception as e:
            logger.error(f"解析Excel文件失败: {e}")
            raise
    
    def _parse_afko(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """解析AFKO工作表数据"""
        records = []
        
        for index, row in df.iterrows():
            try:
                record = {
                    'id': str(uuid.uuid4()),
                    'mandt': self._safe_str(row.get('MANDT')),
                    'aufnr': self._safe_str(row.get('AUFNR')),
                    'gltrp': self._safe_date(row.get('GLTRP')),
                    'gstrp': self._safe_date(row.get('GSTRP')),
                    'ftrms': self._safe_date(row.get('FTRMS')),
                    'gltrs': self._safe_date(row.get('GLTRS')),
                    'gstrs': self._safe_date(row.get('GSTRS')),
                    'gstri': self._safe_date(row.get('GSTRI')),
                    'getri': self._safe_date(row.get('GETRI')),
                    'gltri': self._safe_date(row.get('GLTRI')),
                    'ftrmi': self._safe_date(row.get('FTRMI')),
                    'ftrmp': self._safe_date(row.get('FTRMP')),
                    'rsnum': self._safe_str(row.get('RSNUM')),
                    'gasmg': self._safe_float(row.get('GASMG')),
                    'gamng': self._safe_float(row.get('GAMNG')),
                    'gmein': self._safe_str(row.get('GMEIN')),
                    'plnbez': self._safe_str(row.get('PLNBEZ')),
                    'plnty': self._safe_str(row.get('PLNTY')),
                    'plnnr': self._safe_str(row.get('PLNNR')),
                    'plnaw': self._safe_str(row.get('PLNAW')),
                    'plnal': self._safe_str(row.get('PLNAL')),
                    'pverw': self._safe_str(row.get('PVERW')),
                    'created_at': datetime.now(),
                    'updated_at': datetime.now()
                }
                records.append(record)
            except Exception as e:
                logger.warning(f"解析AFKO第{index}行数据失败: {e}")
                continue
                
        logger.info(f"AFKO解析完成，共{len(records)}条记录")
        return records
    
    def _parse_afpo(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """解析AFPO工作表数据"""
        records = []
        
        for index, row in df.iterrows():
            try:
                record = {
                    'id': str(uuid.uuid4()),
                    'mandt': self._safe_str(row.get('MANDT')),
                    'aufnr': self._safe_str(row.get('AUFNR')),
                    'posnr': self._safe_str(row.get('POSNR')),
                    'psobs': self._safe_str(row.get('PSOBS')),
                    'qunum': self._safe_str(row.get('QUNUM')),
                    'qupos': self._safe_str(row.get('QUPOS')),
                    'projn': self._safe_str(row.get('PROJN')),
                    'plnum': self._safe_str(row.get('PLNUM')),
                    'strmp': self._safe_date(row.get('STRMP')),
                    'etrmp': self._safe_date(row.get('ETRMP')),
                    'kdauf': self._safe_str(row.get('KDAUF')),
                    'kdpos': self._safe_str(row.get('KDPOS')),
                    'kdein': self._safe_str(row.get('KDEIN')),
                    'beskz': self._safe_str(row.get('BESKZ')),
                    'psamg': self._safe_float(row.get('PSAMG')),
                    'psmng': self._safe_float(row.get('PSMNG')),
                    'wemng': self._safe_float(row.get('WEMNG')),
                    'iamng': self._safe_float(row.get('IAMNG')),
                    'amein': self._safe_str(row.get('AMEIN')),
                    'meins': self._safe_str(row.get('MEINS')),
                    'matnr': self._safe_str(row.get('MATNR')),
                    'pamng': self._safe_float(row.get('PAMNG')),
                    'pgmng': self._safe_float(row.get('PGMNG')),
                    'knttp': self._safe_str(row.get('KNTTP')),
                    'tpauf': self._safe_str(row.get('TPAUF')),
                    'ltrmi': self._safe_date(row.get('LTRMI')),
                    'ltrmp': self._safe_date(row.get('LTRMP')),
                    'kalnr': self._safe_str(row.get('KALNR')),
                    'uebto': self._safe_str(row.get('UEBTO')),
                    'uebtk': self._safe_str(row.get('UEBTK')),
                    'untto': self._safe_str(row.get('UNTTO')),
                    'insmk': self._safe_str(row.get('INSMK')),
                    'wepos': self._safe_str(row.get('WEPOS')),
                    'bwtar': self._safe_str(row.get('BWTAR')),
                    'bwty': self._safe_str(row.get('BWTTY')),
                    'pwerk': self._safe_str(row.get('PWERK')),
                    'lgort': self._safe_str(row.get('LGORT')),
                    'umrez': self._safe_str(row.get('UMREZ')),
                    'umren': self._safe_str(row.get('UMREN')),
                    'webaz': self._safe_str(row.get('WEBAZ')),
                    'elikz': self._safe_str(row.get('ELIKZ')),
                    'safnr': self._safe_str(row.get('SAFNR')),
                    'verid': self._safe_str(row.get('VERID')),
                    'sernr': self._safe_str(row.get('SERNR')),
                    'techs': self._safe_str(row.get('TECHS')),
                    'dwerk': self._safe_str(row.get('DWERK')),
                    'dauty': self._safe_str(row.get('DAUTY')),
                    'dauat': self._safe_str(row.get('DAUAT')),
                    'dgltp': self._safe_date(row.get('DGLTP')),
                    'dglts': self._safe_date(row.get('DGLTS')),
                    'dfrei': self._safe_str(row.get('DFREI')),
                    'dnrel': self._safe_str(row.get('DNREL')),
                    'verto': self._safe_str(row.get('VERTO')),
                    'sobkz': self._safe_str(row.get('SOBKZ')),
                    'kzvbr': self._safe_str(row.get('KZVBR')),
                    'wewrt': self._safe_float(row.get('WEWRT')),
                    'weunb': self._safe_str(row.get('WEUNB')),
                    'ablad': self._safe_str(row.get('ABLAD')),
                    'wempf': self._safe_str(row.get('WEMPF')),
                    'charg': self._safe_str(row.get('CHARG')),
                    'gsber': self._safe_str(row.get('GSBER')),
                    'weaed': self._safe_date(row.get('WEAED')),
                    'cuobj': self._safe_str(row.get('CUOBJ')),
                    'kbnkz': self._safe_str(row.get('KBNKZ')),
                    'arsnr': self._safe_str(row.get('ARSNR')),
                    'arsps': self._safe_str(row.get('ARSPS')),
                    'krsnr': self._safe_str(row.get('KRSNR')),
                    'krsp': self._safe_str(row.get('KRSPS')),
                    'kckey': self._safe_str(row.get('KCKEY')),
                    'rtp01': self._safe_str(row.get('RTP01')),
                    'rtp02': self._safe_str(row.get('RTP02')),
                    'rtp03': self._safe_str(row.get('RTP03')),
                    'rtp04': self._safe_str(row.get('RTP04')),
                    'ksvon': self._safe_str(row.get('KSVON')),
                    'ksbis': self._safe_str(row.get('KSBIS')),
                    'objnp': self._safe_str(row.get('OBJNP')),
                    'ndisr': self._safe_str(row.get('NDISR')),
                    'vfmng': self._safe_float(row.get('VFMNG')),
                    'gsbtr': self._safe_float(row.get('GSBTR')),
                    'kzavc': self._safe_str(row.get('KZAVC')),
                    'kzbws': self._safe_str(row.get('KZBWS')),
                    'xloek': self._safe_str(row.get('XLOEK')),
                    'sernp': self._safe_str(row.get('SERNP')),
                    'anzsn': self._safe_str(row.get('ANZSN')),
                    'objtype': self._safe_str(row.get('OBJTYPE')),
                    'ch_proc': self._safe_str(row.get('CH_PROC')),
                    'fxpr': self._safe_str(row.get('FXPRU')),
                    'cuobj_root': self._safe_str(row.get('CUOBJ_ROOT')),
                    'berid': self._safe_str(row.get('BERID')),
                    'techs_copy': self._safe_str(row.get('TECHS_COPY')),
                    'sgt_scat': self._safe_str(row.get('SGT_SCAT')),
                    'kunnr2': self._safe_str(row.get('KUNNR2')),
                    'mill_oc_aufnr_u': self._safe_str(row.get('MILL_OC_AUFNR_U')),
                    'mill_oc_rumng': self._safe_float(row.get('MILL_OC_RUMNG')),
                    'mill_oc_sort': self._safe_str(row.get('MILL_OC_SORT')),
                    'ebel': self._safe_str(row.get('EBELN')),
                    'created_at': datetime.now(),
                    'updated_at': datetime.now()
                }
                records.append(record)
            except Exception as e:
                logger.warning(f"解析AFPO第{index}行数据失败: {e}")
                continue
                
        logger.info(f"AFPO解析完成，共{len(records)}条记录")
        return records
    
    def _parse_afvc(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """解析AFVC工作表数据"""
        records = []
        
        for index, row in df.iterrows():
            try:
                record = {
                    'id': str(uuid.uuid4()),
                    'mandt': self._safe_str(row.get('MANDT')),
                    'aufpl': self._safe_str(row.get('AUFPL')),
                    'aplzl': self._safe_str(row.get('APLZL')),
                    'plnfl': self._safe_float(row.get('PLNFL')),
                    'plnkn': self._safe_float(row.get('PLNKN')),
                    'plnal': self._safe_str(row.get('PLNAL')),
                    'plnty': self._safe_str(row.get('PLNTY')),
                    'vintv': self._safe_str(row.get('VINTV')),
                    'plnnr': self._safe_str(row.get('PLNNR')),
                    'zaehl': self._safe_str(row.get('ZAEHL')),
                    'vornr': self._safe_str(row.get('VORNR')),
                    'steus': self._safe_str(row.get('STEUS')),
                    'arbid': self._safe_str(row.get('ARBID')),
                    'pdest': self._safe_str(row.get('PDEST')),
                    'werks': self._safe_str(row.get('WERKS')),
                    'ktsch': self._safe_str(row.get('KTSCH')),
                    'ltxa1': self._safe_str(row.get('LTXA1')),
                    'ltxa2': self._safe_str(row.get('LTXA2')),
                    'txtsp': self._safe_str(row.get('TXTSP')),
                    'vplty': self._safe_str(row.get('VPLTY')),
                    'vplnr': self._safe_str(row.get('VPLNR')),
                    'vplal': self._safe_str(row.get('VPLAL')),
                    'vplfl': self._safe_str(row.get('VPLFL')),
                    'vgwts': self._safe_str(row.get('VGWTS')),
                    'lar01': self._safe_str(row.get('LAR01')),
                    'lar02': self._safe_str(row.get('LAR02')),
                    'lar03': self._safe_str(row.get('LAR03')),
                    'lar04': self._safe_str(row.get('LAR04')),
                    'lar05': self._safe_str(row.get('LAR05')),
                    'lar06': self._safe_str(row.get('LAR06')),
                    'zerma': self._safe_str(row.get('ZERMA')),
                    'zgdat': self._safe_date(row.get('ZGDAT')),
                    'zcode': self._safe_str(row.get('ZCODE')),
                    'zulnr': self._safe_str(row.get('ZULNR')),
                    'loanz': self._safe_str(row.get('LOANZ')),
                    'loart': self._safe_str(row.get('LOART')),
                    'rsanz': self._safe_str(row.get('RSANZ')),
                    'qualf': self._safe_str(row.get('QUALF')),
                    'anzma': self._safe_str(row.get('ANZMA')),
                    'rfgrp': self._safe_str(row.get('RFGRP')),
                    'rfsch': self._safe_str(row.get('RFSCH')),
                    'rasch': self._safe_str(row.get('RASCH')),
                    'aufak': self._safe_str(row.get('AUFAK')),
                    'logrp': self._safe_str(row.get('LOGRP')),
                    'uemus': self._safe_str(row.get('UEMUS')),
                    'uekan': self._safe_str(row.get('UEKAN')),
                    'flies': self._safe_str(row.get('FLIES')),
                    'spmus': self._safe_str(row.get('SPMUS')),
                    'splim': self._safe_str(row.get('SPLIM')),
                    'ablipkz': self._safe_str(row.get('ABLIPKZ')),
                    'rstra': self._safe_str(row.get('RSTRA')),
                    'sumnr': self._safe_str(row.get('SUMNR')),
                    'sortl': self._safe_str(row.get('SORTL')),
                    'lifnr': self._safe_str(row.get('LIFNR')),
                    'preis': self._safe_float(row.get('PREIS')),
                    'peinh': self._safe_str(row.get('PEINH')),
                    'sakto': self._safe_str(row.get('SAKTO')),
                    'waers': self._safe_str(row.get('WAERS')),
                    'infnr': self._safe_str(row.get('INFNR')),
                    'esokz': self._safe_str(row.get('ESOKZ')),
                    'ekorg': self._safe_str(row.get('EKORG')),
                    'ekgrp': self._safe_str(row.get('EKGRP')),
                    'kzlgf': self._safe_str(row.get('KZLGF')),
                    'kzwrtf': self._safe_str(row.get('KZWRTF')),
                    'matkl': self._safe_str(row.get('MATKL')),
                    'ddehn': self._safe_str(row.get('DDEHN')),
                    'anzzl': self._safe_str(row.get('ANZZL')),
                    'prznt': self._safe_str(row.get('PRZNT')),
                    'mlstn': self._safe_str(row.get('MLSTN')),
                    'pprio': self._safe_str(row.get('PPRIO')),
                    'bukrs': self._safe_str(row.get('BUKRS')),
                    'anfko': self._safe_str(row.get('ANFKO')),
                    'anfkokrs': self._safe_str(row.get('ANFKOKRS')),
                    'indet': self._safe_str(row.get('INDET')),
                    'larnt': self._safe_str(row.get('LARNT')),
                    'prkst': self._safe_str(row.get('PRKST')),
                    'aplfl': self._safe_str(row.get('APLFL')),
                    'rueck': self._safe_str(row.get('RUECK')),
                    'rmzhl': self._safe_str(row.get('RMZHL')),
                    'projn': self._safe_str(row.get('PROJN')),
                    'objnr': self._safe_str(row.get('OBJNR')),
                    'spanz': self._safe_str(row.get('SPANZ')),
                    'bedid': self._safe_str(row.get('BEDID')),
                    'bedzl': self._safe_str(row.get('BEDZL')),
                    'banfn': self._safe_str(row.get('BANFN')),
                    'bnfpo': self._safe_str(row.get('BNFPO')),
                    'lek01': self._safe_str(row.get('LEK01')),
                    'lek02': self._safe_str(row.get('LEK02')),
                    'lek03': self._safe_str(row.get('LEK03')),
                    'lek04': self._safe_str(row.get('LEK04')),
                    'lek05': self._safe_str(row.get('LEK05')),
                    'lek06': self._safe_str(row.get('LEK06')),
                    'selkz': self._safe_str(row.get('SELKZ')),
                    'kalid': self._safe_str(row.get('KALID')),
                    'frsp': self._safe_str(row.get('FRSP')),
                    'stdkn': self._safe_str(row.get('STDKN')),
                    'anlzu': self._safe_str(row.get('ANLZU')),
                    'istru': self._safe_str(row.get('ISTRU')),
                    'isty': self._safe_str(row.get('ISTTY')),
                    'isnr': self._safe_str(row.get('ISTNR')),
                    'istkn': self._safe_str(row.get('ISTKN')),
                    'istpo': self._safe_str(row.get('ISTPO')),
                    'iupoz': self._safe_str(row.get('IUPOZ')),
                    'ebort': self._safe_str(row.get('EBORT')),
                    'vertl': self._safe_str(row.get('VERTL')),
                    'leknw': self._safe_str(row.get('LEKNW')),
                    'nprio': self._safe_str(row.get('NPRIO')),
                    'pvzkn': self._safe_str(row.get('PVZKN')),
                    'phflg': self._safe_str(row.get('PHFLG')),
                    'phseq': self._safe_str(row.get('PHSEQ')),
                    'knobj': self._safe_str(row.get('KNOBJ')),
                    'erfsicht': self._safe_str(row.get('ERFSICHT')),
                    'qppktabs': self._safe_str(row.get('QPPKTABS')),
                    'otype': self._safe_str(row.get('OTYPE')),
                    'objektid': self._safe_str(row.get('OBJEKTID')),
                    'qlkapar': self._safe_str(row.get('QLKAPAR')),
                    'rstuf': self._safe_str(row.get('RSTUF')),
                    'nptxtky': self._safe_str(row.get('NPTXTKY')),
                    'subsys': self._safe_str(row.get('SUBSYS')),
                    'pspnr': self._safe_str(row.get('PSPNR')),
                    'packno': self._safe_str(row.get('PACKNO')),
                    'txjcd': self._safe_str(row.get('TXJCD')),
                    'scope': self._safe_str(row.get('SCOPE')),
                    'gsber': self._safe_str(row.get('GSBER')),
                    'prctr': self._safe_str(row.get('PRCTR')),
                    'no_disp': self._safe_str(row.get('NO_DISP')),
                    'qkzprzeit': self._safe_str(row.get('QKZPRZEIT')),
                    'qkzztmg1': self._safe_str(row.get('QKZZTMG1')),
                    'qkzprmeng': self._safe_str(row.get('QKZPRMENG')),
                    'qkzprfrei': self._safe_str(row.get('QKZPRFREI')),
                    'kzfeat': self._safe_str(row.get('KZFEAT')),
                    'qkztlsbest': self._safe_str(row.get('QKZTLSBEST')),
                    'aennr': self._safe_str(row.get('AENNR')),
                    'cuobj_arb': self._safe_str(row.get('CUOBJ_ARB')),
                    'evgew': self._safe_float(row.get('EVGEW')),
                    'arbii': self._safe_str(row.get('ARBII')),
                    'werki': self._safe_str(row.get('WERKI')),
                    'cy_seqnr': self._safe_str(row.get('CY_SEQNRV')),
                    'kapt_puffr': self._safe_str(row.get('KAPT_PUFFR')),
                    'ebel': self._safe_str(row.get('EBELN')),
                    'ebelp': self._safe_str(row.get('EBELP')),
                    'wempf': self._safe_str(row.get('WEMPF')),
                    'ablad': self._safe_str(row.get('ABLAD')),
                    'clasf': self._safe_str(row.get('CLASF')),
                    'frunv': self._safe_str(row.get('FRUNV')),
                    'zschl': self._safe_str(row.get('ZSCHL')),
                    'kalsm': self._safe_str(row.get('KALSM')),
                    'sched_end': self._safe_date(row.get('SCHED_END')),
                    'netzkont': self._safe_str(row.get('NETZKONT')),
                    'owaer': self._safe_str(row.get('OWAER')),
                    'afnam': self._safe_str(row.get('AFNAM')),
                    'bednr': self._safe_str(row.get('BEDNR')),
                    'kzfix': self._safe_str(row.get('KZFIX')),
                    'pernr': self._safe_str(row.get('PERNR')),
                    'frdlb': self._safe_str(row.get('FRDLB')),
                    'qpart': self._safe_str(row.get('QPART')),
                    'loekz': self._safe_str(row.get('LOEKZ')),
                    'wkurs': self._safe_float(row.get('WKURS')),
                    'prod_act': self._safe_str(row.get('PROD_ACT')),
                    'fplnr': self._safe_str(row.get('FPLNR')),
                    'objtype': self._safe_str(row.get('OBJTYPE')),
                    'ch_proc': self._safe_str(row.get('CH_PROC')),
                    'klvar': self._safe_str(row.get('KLVAR')),
                    'kalnr': self._safe_str(row.get('KALNR')),
                    'fordn': self._safe_str(row.get('FORDN')),
                    'fordp': self._safe_str(row.get('FORDP')),
                    'mat_prkst': self._safe_str(row.get('MAT_PRKST')),
                    'prz01': self._safe_str(row.get('PRZ01')),
                    'rfpnt': self._safe_str(row.get('RFPNT')),
                    'func_area': self._safe_str(row.get('FUNC_AREA')),
                    'techs': self._safe_str(row.get('TECHS')),
                    'adpsp': self._safe_str(row.get('ADPSP')),
                    'rfippnt': self._safe_str(row.get('RFIPPNT')),
                    'mes_operid': self._safe_str(row.get('MES_OPERID')),
                    'mes_stepid': self._safe_str(row.get('MES_STEPID')),
                    'cum_cuguid': self._safe_str(row.get('/CUM/CUGUID')),
                    'isdfps_objnr': self._safe_str(row.get('/ISDFPS/OBJNR')),
                    'afvc_status': self._safe_str(row.get('AFVC_STATUS')),
                    'mill_oc_aufnr_mo': self._safe_str(row.get('MILL_OC_AUFNR_MO')),
                    'wty_ind': self._safe_str(row.get('WTY_IND')),
                    'tplnr': self._safe_str(row.get('TPLNR')),
                    'equnr': self._safe_str(row.get('EQUNR')),
                    'created_at': datetime.now(),
                    'updated_at': datetime.now()
                }
                records.append(record)
            except Exception as e:
                logger.warning(f"解析AFVC第{index}行数据失败: {e}")
                continue
                
        logger.info(f"AFVC解析完成，共{len(records)}条记录")
        return records
    
    def _parse_afvv(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """解析AFVV工作表数据"""
        records = []
        
        for index, row in df.iterrows():
            try:
                record = {
                    'id': str(uuid.uuid4()),
                    'mandt': self._safe_str(row.get('MANDT')),
                    'aufpl': self._safe_str(row.get('AUFPL')),
                    'aplzl': self._safe_str(row.get('APLZL')),
                    'meinh': self._safe_str(row.get('MEINH')),
                    'umren': self._safe_str(row.get('UMREN')),
                    'umrez': self._safe_str(row.get('UMREZ')),
                    'bmsch': self._safe_str(row.get('BMSCH')),
                    'zmerh': self._safe_str(row.get('ZMERH')),
                    'zeier': self._safe_str(row.get('ZEIER')),
                    'vge01': self._safe_str(row.get('VGE01')),
                    'vgw01': self._safe_float(row.get('VGW01')),
                    'vge02': self._safe_str(row.get('VGE02')),
                    'vgw02': self._safe_float(row.get('VGW02')),
                    'vge03': self._safe_str(row.get('VGE03')),
                    'vgw03': self._safe_float(row.get('VGW03')),
                    'vge04': self._safe_str(row.get('VGE04')),
                    'vgw04': self._safe_float(row.get('VGW04')),
                    'vge05': self._safe_str(row.get('VGE05')),
                    'vgw05': self._safe_float(row.get('VGW05')),
                    'vge06': self._safe_str(row.get('VGE06')),
                    'vgw06': self._safe_float(row.get('VGW06')),
                    'zeimu': self._safe_str(row.get('ZEIMU')),
                    'zminu': self._safe_str(row.get('ZMINU')),
                    'minwe': self._safe_str(row.get('MINWE')),
                    'zeimb': self._safe_str(row.get('ZEIMB')),
                    'zminb': self._safe_str(row.get('ZMINB')),
                    'zeilm': self._safe_str(row.get('ZEILM')),
                    'zlmax': self._safe_str(row.get('ZLMAX')),
                    'zeilp': self._safe_str(row.get('ZEILP')),
                    'zlpro': self._safe_str(row.get('ZLPRO')),
                    'zeiwn': self._safe_str(row.get('ZEIWN')),
                    'zwnor': self._safe_str(row.get('ZWNOR')),
                    'zeiwm': self._safe_str(row.get('ZEIWM')),
                    'zwmin': self._safe_str(row.get('ZWMIN')),
                    'zeitn': self._safe_str(row.get('ZEITN')),
                    'ztnor': self._safe_str(row.get('ZTNOR')),
                    'zeitm': self._safe_str(row.get('ZEITM')),
                    'ztmin': self._safe_str(row.get('ZTMIN')),
                    'plifz': self._safe_str(row.get('PLIFZ')),
                    'dauno': self._safe_str(row.get('DAUNO')),
                    'daune': self._safe_str(row.get('DAUNE')),
                    'daumi': self._safe_str(row.get('DAUMI')),
                    'daume': self._safe_str(row.get('DAUME')),
                    'einsa': self._safe_str(row.get('EINSA')),
                    'einse': self._safe_str(row.get('EINSE')),
                    'arbei': self._safe_str(row.get('ARBEI')),
                    'arbeh': self._safe_str(row.get('ARBEH')),
                    'mgvrg': self._safe_str(row.get('MGVRG')),
                    'asvrg': self._safe_str(row.get('ASVRG')),
                    'lmnag': self._safe_str(row.get('LMNGA')),
                    'xmnag': self._safe_str(row.get('XMNGA')),
                    'gmnag': self._safe_str(row.get('GMNGA')),
                    'ism01': self._safe_str(row.get('ISM01')),
                    'ism02': self._safe_str(row.get('ISM02')),
                    'ism03': self._safe_str(row.get('ISM03')),
                    'ism04': self._safe_str(row.get('ISM04')),
                    'ism05': self._safe_str(row.get('ISM05')),
                    'ism06': self._safe_str(row.get('ISM06')),
                    'ismnw': self._safe_str(row.get('ISMNW')),
                    'fsavd': self._safe_date(row.get('FSAVD')),
                    'fsavz': self._safe_str(row.get('FSAVZ')),
                    'fssbd': self._safe_date(row.get('FSSBD')),
                    'fssbz': self._safe_str(row.get('FSSBZ')),
                    'fssad': self._safe_date(row.get('FSSAD')),
                    'fssaz': self._safe_str(row.get('FSSAZ')),
                    'fsedd': self._safe_date(row.get('FSEDD')),
                    'fsedz': self._safe_str(row.get('FSEDZ')),
                    'fssld': self._safe_date(row.get('FSSLD')),
                    'fsslz': self._safe_str(row.get('FSSLZ')),
                    'fseld': self._safe_date(row.get('FSELD')),
                    'fselz': self._safe_str(row.get('FSELZ')),
                    'ssavd': self._safe_date(row.get('SSAVD')),
                    'ssavz': self._safe_str(row.get('SSAVZ')),
                    'sssbd': self._safe_date(row.get('SSSBD')),
                    'sssbz': self._safe_str(row.get('SSSBZ')),
                    'sssad': self._safe_date(row.get('SSSAD')),
                    'sssaz': self._safe_str(row.get('SSSAZ')),
                    'ssedd': self._safe_date(row.get('SSEDD')),
                    'ssedz': self._safe_str(row.get('SSEDZ')),
                    'sssld': self._safe_date(row.get('SSSLD')),
                    'ssslz': self._safe_str(row.get('SSSLZ')),
                    'sseld': self._safe_date(row.get('SSELD')),
                    'sselz': self._safe_str(row.get('SSELZ')),
                    'isavd': self._safe_date(row.get('ISAVD')),
                    'ieavd': self._safe_date(row.get('IEAVD')),
                    'isdd': self._safe_date(row.get('ISDD')),
                    'isdz': self._safe_str(row.get('ISDZ')),
                    'ierd': self._safe_date(row.get('IERD')),
                    'ierz': self._safe_str(row.get('IERZ')),
                    'isbd': self._safe_date(row.get('ISBD')),
                    'isbz': self._safe_str(row.get('ISBZ')),
                    'iebd': self._safe_date(row.get('IEBD')),
                    'iebz': self._safe_str(row.get('IEBZ')),
                    'isad': self._safe_date(row.get('ISAD')),
                    'isaz': self._safe_str(row.get('ISAZ')),
                    'iedd': self._safe_date(row.get('IEDD')),
                    'iedz': self._safe_str(row.get('IEDZ')),
                    'pedd': self._safe_date(row.get('PEDD')),
                    'pedz': self._safe_str(row.get('PEDZ')),
                    'puffr': self._safe_str(row.get('PUFFR')),
                    'pufgs': self._safe_str(row.get('PUFGS')),
                    'ntanf': self._safe_date(row.get('NTANF')),
                    'ntanz': self._safe_str(row.get('NTANZ')),
                    'ntend': self._safe_date(row.get('NTEND')),
                    'ntenz': self._safe_str(row.get('NTENZ')),
                    'ewstd': self._safe_date(row.get('EWSTD')),
                    'ewstz': self._safe_str(row.get('EWSTZ')),
                    'ewend': self._safe_date(row.get('EWEND')),
                    'ewenz': self._safe_str(row.get('EWENZ')),
                    'ewdan': self._safe_str(row.get('EWDAN')),
                    'ewdne': self._safe_str(row.get('EWDNE')),
                    'ewdam': self._safe_str(row.get('EWDAM')),
                    'ewdme': self._safe_str(row.get('EWDME')),
                    'ewste': self._safe_str(row.get('EWSTE')),
                    'ewsta': self._safe_str(row.get('EWSTA')),
                    'wartz': self._safe_str(row.get('WARTZ')),
                    'wrtze': self._safe_str(row.get('WRTZE')),
                    'ruest': self._safe_str(row.get('RUEST')),
                    'rstze': self._safe_str(row.get('RSTZE')),
                    'bearz': self._safe_str(row.get('BEARZ')),
                    'beaze': self._safe_str(row.get('BEAZE')),
                    'abrue': self._safe_str(row.get('ABRUE')),
                    'aruze': self._safe_str(row.get('ARUZE')),
                    'liegz': self._safe_str(row.get('LIEGZ')),
                    'ligze': self._safe_str(row.get('LIGZE')),
                    'tranz': self._safe_str(row.get('TRANZ')),
                    'traze': self._safe_str(row.get('TRAZE')),
                    'iserh': self._safe_str(row.get('ISERH')),
                    'ofm01': self._safe_str(row.get('OFM01')),
                    'ofm02': self._safe_str(row.get('OFM02')),
                    'ofm03': self._safe_str(row.get('OFM03')),
                    'ofm04': self._safe_str(row.get('OFM04')),
                    'ofm05': self._safe_str(row.get('OFM05')),
                    'ofm06': self._safe_str(row.get('OFM06')),
                    'ofmnw': self._safe_str(row.get('OFMNW')),
                    'bzoffb': self._safe_str(row.get('BZOFFB')),
                    'ehoffb': self._safe_str(row.get('EHOFFB')),
                    'offstb': self._safe_str(row.get('OFFSTB')),
                    'offste': self._safe_str(row.get('OFFSTE')),
                    'bzoffe': self._safe_str(row.get('BZOFFE')),
                    'ehoffe': self._safe_str(row.get('EHOFFE')),
                    'fpavd': self._safe_date(row.get('FPAVD')),
                    'fpavz': self._safe_str(row.get('FPAVZ')),
                    'fpedd': self._safe_date(row.get('FPEDD')),
                    'fpedz': self._safe_str(row.get('FPEDZ')),
                    'spavd': self._safe_date(row.get('SPAVD')),
                    'spavz': self._safe_str(row.get('SPAVZ')),
                    'spedd': self._safe_date(row.get('SPEDD')),
                    'spedz': self._safe_str(row.get('SPEDZ')),
                    'beazp': self._safe_str(row.get('BEAZP')),
                    'pufgp': self._safe_str(row.get('PUFGP')),
                    'puffp': self._safe_str(row.get('PUFFP')),
                    'bearp': self._safe_str(row.get('BEARP')),
                    'epanf': self._safe_date(row.get('EPANF')),
                    'epanz': self._safe_str(row.get('EPANZ')),
                    'epend': self._safe_date(row.get('EPEND')),
                    'epenz': self._safe_str(row.get('EPENZ')),
                    'pdau': self._safe_str(row.get('PDAU')),
                    'pdae': self._safe_str(row.get('PDAE')),
                    'knote': self._safe_str(row.get('KNOTE')),
                    'vstzw': self._safe_str(row.get('VSTZW')),
                    'vstga': self._safe_str(row.get('VSTGA')),
                    'qrastzeht': self._safe_str(row.get('QRASTZEHT')),
                    'qrastzfak': self._safe_str(row.get('QRASTZFAK')),
                    'qrastmeng': self._safe_str(row.get('QRASTMENG')),
                    'qrastereh': self._safe_str(row.get('QRASTEREH')),
                    'aufkt': self._safe_str(row.get('AUFKT')),
                    'rmnag': self._safe_str(row.get('RMNGA')),
                    'ile01': self._safe_str(row.get('ILE01')),
                    'ile02': self._safe_str(row.get('ILE02')),
                    'ile03': self._safe_str(row.get('ILE03')),
                    'ile04': self._safe_str(row.get('ILE04')),
                    'ile05': self._safe_str(row.get('ILE05')),
                    'ile06': self._safe_str(row.get('ILE06')),
                    'rwfak': self._safe_str(row.get('RWFAK')),
                    'iprz1': self._safe_str(row.get('IPRZ1')),
                    'ipre1': self._safe_str(row.get('IPRE1')),
                    'iprk1': self._safe_str(row.get('IPRK1')),
                    'takt': self._safe_str(row.get('TAKT')),
                    'oprz1': self._safe_str(row.get('OPRZ1')),
                    'opre1': self._safe_str(row.get('OPRE1')),
                    'pspm_indicator': self._safe_str(row.get('PSPM_INDICATOR')),
                    'created_at': datetime.now(),
                    'updated_at': datetime.now()
                }
                records.append(record)
            except Exception as e:
                logger.warning(f"解析AFVV第{index}行数据失败: {e}")
                continue
                
        logger.info(f"AFVV解析完成，共{len(records)}条记录")
        return records
    
    def _parse_aufk(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """解析AUFK工作表数据"""
        records = []
        
        for index, row in df.iterrows():
            try:
                record = {
                    'id': str(uuid.uuid4()),
                    'mandt': self._safe_str(row.get('MANDT')),
                    'aufnr': self._safe_str(row.get('AUFNR')),
                    'auart': self._safe_str(row.get('AUART')),
                    'autyp': self._safe_str(row.get('AUTYP')),
                    'refnr': self._safe_str(row.get('REFNR')),
                    'ernam': self._safe_str(row.get('ERNAM')),
                    'erdat': self._safe_date(row.get('ERDAT')),
                    'aenam': self._safe_str(row.get('AENAM')),
                    'aedat': self._safe_date(row.get('AEDAT')),
                    'ktext': self._safe_str(row.get('KTEXT')),
                    'ltext': self._safe_str(row.get('LTEXT')),
                    'bukrs': self._safe_str(row.get('BUKRS')),
                    'werks': self._safe_str(row.get('WERKS')),
                    'gsber': self._safe_str(row.get('GSBER')),
                    'kokrs': self._safe_str(row.get('KOKRS')),
                    'cckey': self._safe_str(row.get('CCKEY')),
                    'kostv': self._safe_str(row.get('KOSTV')),
                    'stort': self._safe_str(row.get('STORT')),
                    'sowrk': self._safe_str(row.get('SOWRK')),
                    'astkz': self._safe_str(row.get('ASTKZ')),
                    'waers': self._safe_str(row.get('WAERS')),
                    'astnr': self._safe_str(row.get('ASTNR')),
                    'stdat': self._safe_date(row.get('STDAT')),
                    'estnr': self._safe_str(row.get('ESTNR')),
                    'phas0': self._safe_str(row.get('PHAS0')),
                    'phas1': self._safe_str(row.get('PHAS1')),
                    'phas2': self._safe_str(row.get('PHAS2')),
                    'phas3': self._safe_str(row.get('PHAS3')),
                    'pdat1': self._safe_date(row.get('PDAT1')),
                    'pdat2': self._safe_date(row.get('PDAT2')),
                    'pdat3': self._safe_date(row.get('PDAT3')),
                    'idat1': self._safe_date(row.get('IDAT1')),
                    'idat2': self._safe_date(row.get('IDAT2')),
                    'idat3': self._safe_date(row.get('IDAT3')),
                    'objid': self._safe_str(row.get('OBJID')),
                    'vogrp': self._safe_str(row.get('VOGRP')),
                    'loekz': self._safe_str(row.get('LOEKZ')),
                    'plgkz': self._safe_str(row.get('PLGKZ')),
                    'kvewe': self._safe_str(row.get('KVEWE')),
                    'kappl': self._safe_str(row.get('KAPPL')),
                    'kalsm': self._safe_str(row.get('KALSM')),
                    'zschl': self._safe_str(row.get('ZSCHL')),
                    'abkrs': self._safe_str(row.get('ABKRS')),
                    'kstar': self._safe_str(row.get('KSTAR')),
                    'kostl': self._safe_str(row.get('KOSTL')),
                    'saknr': self._safe_str(row.get('SAKNR')),
                    'setnm': self._safe_str(row.get('SETNM')),
                    'cycle': self._safe_str(row.get('CYCLE')),
                    'sdate': self._safe_date(row.get('SDATE')),
                    'seqnr': self._safe_str(row.get('SEQNR')),
                    'user0': self._safe_str(row.get('USER0')),
                    'user1': self._safe_str(row.get('USER1')),
                    'user2': self._safe_str(row.get('USER2')),
                    'user3': self._safe_str(row.get('USER3')),
                    'user4': self._safe_str(row.get('USER4')),
                    'user5': self._safe_str(row.get('USER5')),
                    'user6': self._safe_str(row.get('USER6')),
                    'user7': self._safe_str(row.get('USER7')),
                    'user8': self._safe_str(row.get('USER8')),
                    'user9': self._safe_str(row.get('USER9')),
                    'objnr': self._safe_str(row.get('OBJNR')),
                    'prctr': self._safe_str(row.get('PRCTR')),
                    'pspel': self._safe_str(row.get('PSPEL')),
                    'awsls': self._safe_str(row.get('AWSLS')),
                    'abgsl': self._safe_str(row.get('ABGSL')),
                    'txjcd': self._safe_str(row.get('TXJCD')),
                    'func_area': self._safe_str(row.get('FUNC_AREA')),
                    'scope': self._safe_str(row.get('SCOPE')),
                    'plint': self._safe_str(row.get('PLINT')),
                    'kdauf': self._safe_str(row.get('KDAUF')),
                    'kdpos': self._safe_str(row.get('KDPOS')),
                    'aufex': self._safe_str(row.get('AUFEX')),
                    'ivpro': self._safe_str(row.get('IVPRO')),
                    'logsystem': self._safe_str(row.get('LOGSYSTEM')),
                    'flg_mltps': self._safe_str(row.get('FLG_MLTPS')),
                    'abukr': self._safe_str(row.get('ABUKR')),
                    'akstl': self._safe_str(row.get('AKSTL')),
                    'sizecl': self._safe_str(row.get('SIZECL')),
                    'izwek': self._safe_str(row.get('IZWEK')),
                    'umwkz': self._safe_str(row.get('UMWKZ')),
                    'kstempf': self._safe_str(row.get('KSTEMPF')),
                    'zschm': self._safe_str(row.get('ZSCHM')),
                    'pkosa': self._safe_str(row.get('PKOSA')),
                    'anfaufnr': self._safe_str(row.get('ANFAUFNR')),
                    'procnr': self._safe_str(row.get('PROCNR')),
                    'proty': self._safe_str(row.get('PROTY')),
                    'rsord': self._safe_str(row.get('RSORD')),
                    'bemot': self._safe_str(row.get('BEMOT')),
                    'adrnra': self._safe_str(row.get('ADRNRA')),
                    'erfzeit': self._safe_str(row.get('ERFZEIT')),
                    'aezeit': self._safe_str(row.get('AEZEIT')),
                    'cstg_vrnt': self._safe_str(row.get('CSTG_VRNT')),
                    'costestnr': self._safe_str(row.get('COSTESTNR')),
                    'veraa_user': self._safe_str(row.get('VERAA_USER')),
                    'zbukrs': self._safe_str(row.get('ZBUKRS')),
                    'zzcpkg': self._safe_str(row.get('ZZCPGK')),
                    'zzkhyq': self._safe_str(row.get('ZZKHYQ')),
                    'zztuhao': self._safe_str(row.get('ZZTUHAO')),
                    'zzjsfa': self._safe_str(row.get('ZZJSFA')),
                    'zzxqbm': self._safe_str(row.get('ZZXQBM')),
                    'zzyfxmh': self._safe_str(row.get('ZZYFXMH')),
                    'zzwxy': self._safe_str(row.get('ZZWXY')),
                    'zzjy': self._safe_str(row.get('ZZJYY')),
                    'zzjyjg': self._safe_str(row.get('ZZJYJG')),
                    'zzgzfx': self._safe_str(row.get('ZZGZFX')),
                    'zzbf': self._safe_str(row.get('ZZBF')),
                    'zzsernr': self._safe_str(row.get('ZZSERNR')),
                    'zzwtms': self._safe_str(row.get('ZZWTMS')),
                    'zzgzdm': self._safe_str(row.get('ZZGZDM')),
                    'zggyq': self._safe_str(row.get('ZGGYQ')),
                    'zxpl': self._safe_str(row.get('ZXPL')),
                    'zgg': self._safe_str(row.get('ZGG')),
                    'zfg': self._safe_str(row.get('ZFG')),
                    'vname': self._safe_str(row.get('VNAME')),
                    'recid': self._safe_str(row.get('RECID')),
                    'etype': self._safe_str(row.get('ETYPE')),
                    'otype': self._safe_str(row.get('OTYPE')),
                    'jv_jibcl': self._safe_str(row.get('JV_JIBCL')),
                    'jv_jibsa': self._safe_str(row.get('JV_JIBSA')),
                    'jv_oco': self._safe_str(row.get('JV_OCO')),
                    'cum_indcu': self._safe_str(row.get('/CUM/INDCU')),
                    'cum_cmnum': self._safe_str(row.get('/CUM/CMNUM')),
                    'cum_auest': self._safe_str(row.get('/CUM/AUEST')),
                    'cum_desnum': self._safe_str(row.get('/CUM/DESNUM')),
                    'vaplz': self._safe_str(row.get('VAPLZ')),
                    'wawrk': self._safe_str(row.get('WAWRK')),
                    'ferc_ind': self._safe_str(row.get('FERC_IND')),
                    'aufk_status': self._safe_str(row.get('AUFK_STATUS')),
                    'claim_control': self._safe_str(row.get('CLAIM_CONTROL')),
                    'update_needed': self._safe_str(row.get('UPDATE_NEEDED')),
                    'update_control': self._safe_str(row.get('UPDATE_CONTROL')),
                    'created_at': datetime.now(),
                    'updated_at': datetime.now()
                }
                records.append(record)
            except Exception as e:
                logger.warning(f"解析AUFK第{index}行数据失败: {e}")
                continue
                
        logger.info(f"AUFK解析完成，共{len(records)}条记录")
        return records
    
    def _parse_jest(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """解析JEST工作表数据"""
        records = []
        
        for index, row in df.iterrows():
            try:
                record = {
                    'id': str(uuid.uuid4()),
                    'mandt': self._safe_str(row.get('MANDT')),
                    'objnr': self._safe_str(row.get('OBJNR')),
                    'stat': self._safe_str(row.get('STAT')),
                    'inact': self._safe_str(row.get('INACT')),
                    'chgnr': self._safe_str(row.get('CHGNR')),
                    'dataaging': self._safe_str(row.get('_DATAAGING')),
                    'created_at': datetime.now(),
                    'updated_at': datetime.now()
                }
                records.append(record)
            except Exception as e:
                logger.warning(f"解析JEST第{index}行数据失败: {e}")
                continue
                
        logger.info(f"JEST解析完成，共{len(records)}条记录")
        return records
    
    def _parse_makt(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """解析MAKT工作表数据"""
        records = []
        
        for index, row in df.iterrows():
            try:
                record = {
                    'id': str(uuid.uuid4()),
                    'mandt': self._safe_str(row.get('MANDT')),
                    'matnr': self._safe_str(row.get('MATNR')),
                    'spras': self._safe_str(row.get('SPRAS')),
                    'maktx': self._safe_str(row.get('MAKTX')),
                    'maktg': self._safe_str(row.get('MAKTG')),
                    'created_at': datetime.now(),
                    'updated_at': datetime.now()
                }
                records.append(record)
            except Exception as e:
                logger.warning(f"解析MAKT第{index}行数据失败: {e}")
                continue
                
        logger.info(f"MAKT解析完成，共{len(records)}条记录")
        return records
    
    def _safe_str(self, value: Any) -> Optional[str]:
        """安全转换为字符串"""
        if pd.isna(value) or value is None:
            return None
        return str(value).strip() if str(value).strip() else None
    
    def _safe_float(self, value: Any) -> Optional[float]:
        """安全转换为浮点数"""
        if pd.isna(value) or value is None:
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None
    
    def _safe_date(self, value: Any) -> Optional[date]:
        """安全转换为日期"""
        if pd.isna(value) or value is None:
            return None
        try:
            if isinstance(value, date):
                return value
            elif isinstance(value, datetime):
                return value.date()
            elif isinstance(value, str):
                # 尝试解析日期字符串
                if '/' in value:
                    return pd.to_datetime(value).date()
                else:
                    return pd.to_datetime(value).date()
            else:
                return pd.to_datetime(value).date()
        except (ValueError, TypeError):
            return None
