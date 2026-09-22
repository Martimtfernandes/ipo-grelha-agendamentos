# =====================================================================
# IPO PORTO - PLATAFORMA INTEGRADA DE GESTÃO, TRIAGEM & CROMO DIGITAL
# Ficheiro: app.py
# =====================================================================

import io
import math
import sqlite3
from datetime import datetime, timedelta
import pandas as pd
import streamlit as st

# ---------------------------------------------------------------------
# 1. CONFIGURAÇÃO DA APLICAÇÃO & DESIGN DO SISTEMA (IPO PORTO)
# ---------------------------------------------------------------------
st.set_page_config(
    page_title="IPO Porto - Gestão Integrada de Pedidos & Cromo Digital",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded"
)

DB_NAME = "ipo_database.db"

# Mapeamento Clínico Institucional (Cores de Triagem & SLA Alvo)
COLOR_MAP = {
    'Crítico': {'score': 5.0, 'sla': 3, 'nivel': 'N6', 'badge_color': '#b30000', 'text_color': '#ffffff'},
    'Muito Alto': {'score': 4.2, 'sla': 7, 'nivel': 'N5', 'badge_color': '#d9534f', 'text_color': '#ffffff'},
    'Alto': {'score': 3.5, 'sla': 14, 'nivel': 'N4', 'badge_color': '#f0ad4e', 'text_color': '#ffffff'},
    'Moderado': {'score': 2.8, 'sla': 30, 'nivel': 'N3', 'badge_color': '#ffc107', 'text_color': '#212529'},
    'Baixo': {'score': 2.0, 'sla': 60, 'nivel': 'N2', 'badge_color': '#17a2b8', 'text_color': '#ffffff'},
    'Rotina': {'score': 1.0, 'sla': 90, 'nivel': 'N1', 'badge_color': '#6c757d', 'text_color': '#ffffff'}
}

# Hierarquia de Prioridade por Etapa Oncológica (H_MAP)
H_MAP = {
    'Diagnostico': 5.0,
    'Estadiamento': 4.0,
    'Decisao_terapeutica': 3.0,
    'Tratamento': 2.0,
    'Follow_up': 1.0
}

# Fator multiplicador de remarcação consoante a proveniência
ORIGEM_REMARCACAO = {
    'equipa_clinica': 1.5,
    'doente': 0.75,
    'outros': 1.0
}

# Estilização CSS inspirada no template do Cromo Digital
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(135deg, #002b49 0%, #0056b3 100%);
        padding: 20px 25px;
        border-radius: 10px;
        color: white;
        margin-bottom: 22px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.12);
    }
    .header-title {
        font-size: 26px;
        font-weight: 800;
        letter-spacing: -0.5px;
        margin: 0;
    }
    .header-sub {
        font-size: 14px;
        opacity: 0.92;
        margin-top: 5px;
    }
    .cromo-paper {
        background: #ffffff;
        border: 2px solid #0056b3;
        border-radius: 10px;
        padding: 24px;
        box-shadow: 0 8px 24px rgba(0,0,0,0.08);
        margin-bottom: 20px;
    }
    .cromo-header-banner {
        border-bottom: 3px double #0056b3;
        padding-bottom: 12px;
        margin-bottom: 20px;
    }
    .cromo-section-title {
        background-color: #e9ecef;
        color: #0056b3;
        font-size: 0.88rem;
        font-weight: 700;
        padding: 6px 12px;
        border-left: 5px solid #0056b3;
        border-radius: 0 4px 4px 0;
        margin-top: 15px;
        margin-bottom: 12px;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    .field-box {
        background-color: #f8f9fa;
        border: 1px solid #e2e8f0;
        border-radius: 6px;
        padding: 8px 12px;
        margin-bottom: 10px;
    }
    .field-label {
        font-size: 0.72rem;
        color: #64748b;
        font-weight: 700;
        text-transform: uppercase;
        display: block;
        margin-bottom: 3px;
    }
    .field-value {
        font-size: 0.95rem;
        color: #0f172a;
        font-weight: 600;
    }
    .badge-semaforo-verde {
        background-color: #28a745;
        color: white;
        padding: 4px 10px;
        border-radius: 12px;
        font-weight: 700;
        font-size: 12px;
    }
    .badge-semaforo-vermelho {
        background-color: #dc3545;
        color: white;
        padding: 4px 10px;
        border-radius: 12px;
        font-weight: 700;
        font-size: 12px;
    }
    .badge-semaforo-azul {
        background-color: #007bff;
        color: white;
        padding: 4px 10px;
        border-radius: 12px;
        font-weight: 700;
        font-size: 12px;
    }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------
# 2. CAMADA DE BASE DE DADOS & MIGRAÇÕES AUTOMÁTICAS (SQLITE)
# ---------------------------------------------------------------------
def get_connection():
    conn = sqlite3.connect(DB_NAME, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def inicializar_e_migrar_bd():
    """
    Garante a existência da tabela 'cromos' e aplica migrações
    dinâmicas para suportar os campos da fórmula matemática e SLA.
    """
    conn = get_connection()
    cur = conn.cursor()
    
    cur.execute('''
        CREATE TABLE IF NOT EXISTS cromos (
            id_pedido INTEGER PRIMARY KEY AUTOINCREMENT,
            id_doente TEXT,
            etiqueta_doente TEXT, 
            servico_requisitante TEXT,
            chk_prox_consulta TEXT DEFAULT '0', 
            dt_prox_consulta TEXT DEFAULT '',
            chk_cons_processo TEXT DEFAULT '0', 
            dt_cons_processo TEXT DEFAULT '',
            chk_ce_outra TEXT DEFAULT '0', 
            ce_esp1 TEXT DEFAULT '', 
            ce_dt1 TEXT DEFAULT '', 
            ce_esp2 TEXT DEFAULT '', 
            ce_dt2 TEXT DEFAULT '',
            chk_cons_grupo TEXT DEFAULT '0', 
            cg_esp_tipo TEXT DEFAULT '', 
            cg_dt TEXT DEFAULT '', 
            chk_cg_sem_doente TEXT DEFAULT '0', 
            chk_cg_com_doente TEXT DEFAULT '0',
            chk_hosp_dia TEXT DEFAULT '0', 
            hd_tratamento TEXT DEFAULT '', 
            hd_dt TEXT DEFAULT '',
            chk_exames_mural TEXT DEFAULT '0', 
            chk_analises_mural TEXT DEFAULT '0', 
            chk_sem_jejum TEXT DEFAULT '0', 
            chk_com_jejum TEXT DEFAULT '0',
            chk_outros_exames TEXT DEFAULT '0', 
            oe_exame1 TEXT DEFAULT '', 
            oe_dt1 TEXT DEFAULT '', 
            oe_exame2 TEXT DEFAULT '', 
            oe_dt2 TEXT DEFAULT '',
            chk_credencial_transp TEXT DEFAULT '0', 
            chk_outros TEXT DEFAULT '0', 
            outros_desc TEXT DEFAULT '',
            chk_alta_consulta TEXT DEFAULT '0', 
            chk_alta_inst TEXT DEFAULT '0', 
            chk_inq_reg_onco TEXT DEFAULT '0',
            data_emissao TEXT DEFAULT '', 
            requisitante TEXT DEFAULT '',
            estado TEXT DEFAULT 'Pendente',
            motivo_rejeicao TEXT DEFAULT '',
            nova_data_proposta TEXT DEFAULT ''
        )
    ''')
    
    # Obter colunas existentes
    cur.execute("PRAGMA table_info(cromos)")
    colunas_existentes = [c['name'] for c in cur.fetchall()]
    
    novas_colunas = {
        'cor': "TEXT DEFAULT 'Sem Cor'",
        'etapa_clinica': "TEXT DEFAULT 'Diagnostico'",
        'dias_espera': "INTEGER DEFAULT 0",
        'remarcacoes': "INTEGER DEFAULT 0",
        'origem_remarcacao': "TEXT DEFAULT 'outros'",
        'dias_desde_ultima_remarcacao': "INTEGER DEFAULT 0",
        'completo': "INTEGER DEFAULT 1",
        'motivo_pendencia': "TEXT DEFAULT ''",
        'complexidade_m': "REAL DEFAULT 0.5",
        'patologia': "TEXT DEFAULT 'Neoplasia em Investigação'",
        'estadiamento': "TEXT DEFAULT 'Indeterminado'",
        'ecog': "INTEGER DEFAULT 0",
        'slot_info': "TEXT DEFAULT ''"
    }
    
    for col, tipo in novas_colunas.items():
        if col not in colunas_existentes:
            cur.execute(f"ALTER TABLE cromos ADD COLUMN {col} {tipo}")
            
    conn.commit()
    
    # Se a tabela estiver vazia, carrega casos clínicos representativos
    cur.execute("SELECT COUNT(*) AS total FROM cromos")
    if cur.fetchone()['total'] == 0:
        popular_dados_iniciais(conn)
        
    conn.close()

def popular_dados_iniciais(conn):
    """Insere pedidos de teste com diferentes graus de gravidade e prescritores."""
    hoje = datetime(2026, 9, 22)
    dados = [
        (
            '36058', 'João Silva - Proc. 36058', 'Oncologia Médica',
            '1', (hoje + timedelta(days=2)).strftime('%d/%m/%Y'), '0', '', '0', '', '', '', '',
            '0', '', '', '0', '0', '1', 'Quimioterapia FOLFOX', (hoje + timedelta(days=2)).strftime('%d/%m/%Y'),
            '1', '1', '0', '1', '1', 'TAC Torácica', (hoje + timedelta(days=1)).strftime('%d/%m/%Y'), '', '',
            '1', '0', 'Transporte em maca', '0', '0', '0',
            (hoje - timedelta(days=4)).strftime('%d/%m/%Y'), 'Dr. António Santos - Mec 4821',
            'Aceite', '', '', 'Crítico', 'Tratamento', 4, 1, 'equipa_clinica', 2, 1, '', 0.85,
            'Adenocarcinoma do Cólon Metastático', 'cT4N2M1 (Estádio IV)', 1, 'Slot 09:30 - Sala 4'
        ),
        (
            '42109', 'Maria Fernandes - Proc. 42109', 'Cirurgia Oncológica',
            '1', (hoje + timedelta(days=5)).strftime('%d/%m/%Y'), '0', '', '0', '', '', '', '',
            '1', 'Mama Multidisciplinar', (hoje + timedelta(days=4)).strftime('%d/%m/%Y'), '0', '1',
            '0', '', '', '1', '1', '1', '0', '1', 'Mamografia Bilateral', (hoje + timedelta(days=3)).strftime('%d/%m/%Y'), '', '',
            '0', '0', '', '0', '0', '0',
            (hoje - timedelta(days=6)).strftime('%d/%m/%Y'), 'Dra. Clara Meireles - Mec 5120',
            'Aceite', '', '', 'Muito Alto', 'Decisao_terapeutica', 6, 0, 'outros', 0, 1, '', 0.60,
            'Carcinoma Ductal Invasivo Mama', 'cT2N1M0 (Estádio IIB)', 0, ''
        ),
        (
            '51980', 'Carlos Pereira - Proc. 51980', 'Pneumologia Oncológica',
            '1', (hoje + timedelta(days=8)).strftime('%d/%m/%Y'), '0', '', '0', '', '', '', '',
            '0', '', '', '0', '0', '0', '', '',
            '1', '1', '0', '1', '1', 'TAC Torácica c/ Contraste', (hoje + timedelta(days=7)).strftime('%d/%m/%Y'), '', '',
            '1', '0', 'Necessita O2 suplementar', '0', '0', '0',
            (hoje - timedelta(days=5)).strftime('%d/%m/%Y'), 'Dr. António Santos - Mec 4821',
            'Pendente', '', '', 'Crítico', 'Diagnostico', 5, 2, 'doente', 8, 0, 'Falta Prova de Função Renal e TC Atualizada', 0.90,
            'Neoplasia Maligna do Pulmão (CPNPC)', 'cT3N2M0 (Estádio IIIA)', 2, ''
        ),
        (
            '60234', 'Teresa Vilar - Proc. 60234', 'Cirurgia Oncológica',
            '1', '', '0', '', '0', '', '', '', '',
            '0', '', '', '0', '0', '0', '', '',
            '0', '0', '0', '0', '1', 'Ressonância Magnética', (hoje + timedelta(days=10)).strftime('%d/%m/%Y'), '', '',
            '0', '0', '', '0', '0', '0',
            (hoje - timedelta(days=3)).strftime('%d/%m/%Y'), 'Dr. António Santos - Mec 4821',
            'Pendente', '', '', 'Sem Cor', 'Diagnostico', 3, 0, 'outros', 0, 1, 'Pedido submetido sem cor/SLA médico atribuído', 0.70,
            'Sarcoma de Partes Moles', 'Suspeita Recidiva', 1, ''
        ),
        (
            '71245', 'António Henriques - Proc. 71245', 'Gastrenterologia Oncológica',
            '1', (hoje + timedelta(days=15)).strftime('%d/%m/%Y'), '0', '', '0', '', '', '', '',
            '0', '', '', '0', '0', '0', '', '',
            '1', '1', '0', '1', '1', 'Ecoendoscopia Alta', (hoje + timedelta(days=12)).strftime('%d/%m/%Y'), '', '',
            '0', '0', '', '0', '0', '0',
            (hoje - timedelta(days=9)).strftime('%d/%m/%Y'), 'Dr. António Santos - Mec 4821',
            'Pendente', '', '', 'Muito Alto', 'Tratamento', 9, 1, 'equipa_clinica', 1, 0, 'Consentimento Informado em Falta', 0.85,
            'Carcinoma Gástrico Antral', 'cT3N1M0', 2, ''
        ),
        (
            '80412', 'Ana Paula Ramos - Proc. 80412', 'Hematologia',
            '1', (hoje + timedelta(days=14)).strftime('%d/%m/%Y'), '0', '', '0', '', '', '', '',
            '1', 'Hematologia - Grupo Linfomas', (hoje + timedelta(days=10)).strftime('%d/%m/%Y'), '0', '1',
            '0', '', '', '1', '1', '0', '1', '1', 'PET Scan Corporal', (hoje + timedelta(days=9)).strftime('%d/%m/%Y'), '', '',
            '0', '0', '', '0', '0', '0',
            (hoje - timedelta(days=12)).strftime('%d/%m/%Y'), 'Dr. Rui Carreira - Mec 3940',
            'Aceite', '', '', 'Alto', 'Estadiamento', 12, 1, 'outros', 5, 1, '', 0.50,
            'Linfoma Difuso Grandes Células B', 'Estádio III', 1, ''
        ),
        (
            '91834', 'Sandra Batista - Proc. 91834', 'Dermatologia / Dermato-Oncologia',
            '1', (hoje + timedelta(days=3)).strftime('%d/%m/%Y'), '0', '', '0', '', '', '', '',
            '0', '', '', '0', '0', '0', '', '',
            '0', '0', '0', '0', '0', '', '', '', '',
            '0', '0', '', '0', '0', '0',
            (hoje - timedelta(days=3)).strftime('%d/%m/%Y'), 'Dra. Sofia Lourenço - Mec 6211',
            'Aceite', '', '', 'Crítico', 'Diagnostico', 3, 0, 'outros', 0, 1, '', 0.75,
            'Melanoma Nodular Ulcerado', 'Breslow 3.5mm Clark IV', 0, ''
        ),
        (
            '95123', 'Rodrigo Esteves - Proc. 95123', 'Otorrinolaringologia Oncológica',
            '1', (hoje + timedelta(days=4)).strftime('%d/%m/%Y'), '0', '', '0', '', '', '', '',
            '0', '', '', '0', '0', '0', '', '',
            '1', '1', '1', '0', '1', 'TAC Pescoço com Contraste', (hoje + timedelta(days=2)).strftime('%d/%m/%Y'), '', '',
            '1', '0', '', '0', '0', '0',
            (hoje - timedelta(days=4)).strftime('%d/%m/%Y'), 'Dr. António Santos - Mec 4821',
            'Aceite', '', '', 'Crítico', 'Tratamento', 4, 1, 'equipa_clinica', 1, 1, '', 0.90,
            'Carcinoma Epidermoide Laringe', 'cT4aN1M0', 2, '24/Set 10:00 - TAC 2'
        ),
        (
            '33491', 'Helena Maria Dias - Proc. 33491', 'Endocrinologia Oncológica',
            '1', (hoje + timedelta(days=20)).strftime('%d/%m/%Y'), '0', '', '0', '', '', '', '',
            '0', '', '', '0', '0', '0', '', '',
            '0', '1', '1', '0', '0', '', '', '', '',
            '0', '0', '', '0', '0', '0',
            (hoje - timedelta(days=70)).strftime('%d/%m/%Y'), 'Dra. Sofia Lourenço - Mec 6211',
            'Aceite', '', '', 'Rotina', 'Follow_up', 70, 0, 'outros', 0, 1, '', 0.20,
            'Carcinoma Papilar da Tiroideia', 'T1bN0M0', 0, ''
        ),
        (
            '22874', 'Manuel Ferreira - Proc. 22874', 'Urologia',
            '1', (hoje + timedelta(days=15)).strftime('%d/%m/%Y'), '0', '', '0', '', '', '', '',
            '0', '', '', '0', '0', '0', '', '',
            '0', '1', '0', '1', '0', '', '', '', '',
            '0', '0', '', '0', '0', '0',
            (hoje - timedelta(days=18)).strftime('%d/%m/%Y'), 'Dra. Clara Meireles - Mec 5120',
            'Rejeitado', 'Sem vaga disponível na data solicitada', '', 'Moderado', 'Decisao_terapeutica', 18, 0, 'outros', 0, 1, '', 0.35,
            'Adenocarcinoma da Próstata', 'ISUP 3 (Gleason 4+3)', 0, ''
        ),
        (
            '77102', 'Beatriz Carvalho - Proc. 77102', 'Ginecologia Oncológica',
            '1', (hoje + timedelta(days=25)).strftime('%d/%m/%Y'), '0', '', '0', '', '', '', '',
            '0', '', '', '0', '0', '0', '', '',
            '1', '1', '0', '1', '1', 'RM Pélvica', (hoje + timedelta(days=20)).strftime('%d/%m/%Y'), '', '',
            '0', '0', '', '0', '0', '0',
            (hoje - timedelta(days=28)).strftime('%d/%m/%Y'), 'Dr. Rui Carreira - Mec 3940',
            'Proposta_Data', '', '15/10/2026', 'Moderado', 'Estadiamento', 28, 0, 'outros', 0, 0, 'Aguardar vaga de RM Pélvica', 0.45,
            'Carcinoma do Colo do Útero', 'FIGO IIB', 0, ''
        )
    ]
    
    cur = conn.cursor()
    cur.executemany('''
        INSERT INTO cromos (
            id_doente, etiqueta_doente, servico_requisitante,
            chk_prox_consulta, dt_prox_consulta,
            chk_cons_processo, dt_cons_processo,
            chk_ce_outra, ce_esp1, ce_dt1, ce_esp2, ce_dt2,
            chk_cons_grupo, cg_esp_tipo, cg_dt, chk_cg_sem_doente, chk_cg_com_doente,
            chk_hosp_dia, hd_tratamento, hd_dt,
            chk_exames_mural, chk_analises_mural, chk_sem_jejum, chk_com_jejum,
            chk_outros_exames, oe_exame1, oe_dt1, oe_exame2, oe_dt2,
            chk_credencial_transp, chk_outros, outros_desc,
            chk_alta_consulta, chk_alta_inst, chk_inq_reg_onco,
            data_emissao, requisitante,
            estado, motivo_rejeicao, nova_data_proposta,
            cor, etapa_clinica, dias_espera, remarcacoes, origem_remarcacao,
            dias_desde_ultima_remarcacao, completo, motivo_pendencia, complexidade_m,
            patologia, estadiamento, ecog, slot_info
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    ''', dados)
    conn.commit()

# ---------------------------------------------------------------------
# 3. MOTOR DE CÁLCULO E PIPELINE ETL (INTEGRADO COM SQLITE)
# ---------------------------------------------------------------------
def calcular_prioridade_doente(row: dict) -> dict:
    """
    Fórmula Oficial do IPO:
    PF_raw = (0.55 * S) + (0.18 * H) + (0.12 * W) + (0.05 * M) + (0.10 * R)
    PrioridadeFinal = max(0, min(1, PF_raw)) * 100
    """
    res = dict(row)
    cor = res.get('cor')
    if cor in COLOR_MAP:
        score_val = COLOR_MAP[cor]['score']
        sla_alvo = COLOR_MAP[cor]['sla']
        res['nivel'] = COLOR_MAP[cor]['nivel']
    else:
        score_val = 0.0
        sla_alvo = 30
        res['nivel'] = 'N0'
        res['cor'] = 'Sem Cor'

    res['sla_alvo_dias'] = sla_alvo
    S = score_val / 5.0
    
    etapa = res.get('etapa_clinica', 'Diagnostico')
    H = H_MAP.get(etapa, 1.0) / 5.0
    
    dias_espera = res.get('dias_espera', 0) or 0
    W = min(1.0, dias_espera / max(1, sla_alvo))
    
    M = res.get('complexidade_m', 0.5) or 0.5
    
    remarcacoes = res.get('remarcacoes', 0) or 0
    if remarcacoes > 0:
        origem = res.get('origem_remarcacao', 'outros')
        origem_factor = ORIGEM_REMARCACAO.get(origem, 1.0)
        dias_desde = res.get('dias_desde_ultima_remarcacao', 0) or 0
        R_base = min(1.0, remarcacoes / 3.0) * origem_factor * math.exp(-0.05 * dias_desde)
    else:
        R_base = 0.0
        
    res['r_score'] = round(R_base, 3)
    
    PF_raw = (0.55 * S) + (0.18 * H) + (0.12 * W) + (0.05 * M) + (0.10 * R_base)
    res['prioridade_final'] = round(max(0.0, min(1.0, PF_raw)) * 100, 1)
    
    # Regras de Semáforo e Estado de Completude
    estado_db = res.get('estado', 'Pendente')
    completo = bool(res.get('completo', 1))
    slot = res.get('slot_info', '')
    
    if estado_db == 'Rejeitado':
        res['semaforo'] = 'Vermelho'
        res['estado_calculado'] = 'Rejeitado'
    elif not completo:
        res['semaforo'] = 'Vermelho'
        res['estado_calculado'] = 'bloqueado_pendencia'
    elif res['cor'] == 'Sem Cor' or estado_db == 'Proposta_Data':
        res['semaforo'] = 'Vermelho'
        res['estado_calculado'] = 'em_validacao_medica'
    elif slot and slot.strip():
        res['semaforo'] = 'Azul'
        res['estado_calculado'] = 'agendado'
    elif estado_db == 'Aceite':
        res['semaforo'] = 'Verde'
        res['estado_calculado'] = 'pronto_para_marcar'
    else:
        res['semaforo'] = 'Verde'
        res['estado_calculado'] = 'pronto_para_marcar'
        
    return res

def carregar_todos_pedidos():
    conn = get_connection()
    rows = conn.execute("SELECT * FROM cromos ORDER BY id_pedido DESC").fetchall()
    conn.close()
    return [calcular_prioridade_doente(r) for r in rows]

# Iniciar infraestrutura
inicializar_e_migrar_bd()

if "slots_vagos" not in st.session_state:
    st.session_state.slots_vagos = []
if "cromo_id_ativo" not in st.session_state:
    st.session_state.cromo_id_ativo = None

# ---------------------------------------------------------------------
# 4. BARRA SUPERIOR: PAINEL DE MÉTRICAS OPERACIONAIS
# ---------------------------------------------------------------------
pedidos = carregar_todos_pedidos()
total = len(pedidos)
verdes = sum(1 for p in pedidos if p['semaforo'] == 'Verde')
perc_verde = round((verdes / total) * 100, 1) if total > 0 else 0
criticos = sum(1 for p in pedidos if p.get('cor') in ['Crítico', 'Muito Alto'])
vagas_livres = len(st.session_state.slots_vagos)
rejeitados_cnt = sum(1 for p in pedidos if p['estado'] == 'Rejeitado')

st.markdown("""
<div class="main-header">
    <div class="header-title">🏛️ IPO Porto - Grelha Central de Agendamentos & Cromo Digital</div>
    <div class="header-sub">Gestão Operacional de Consultas, Exames e Bloco Ambulatório | Triagem Clínica Multidimensional</div>
</div>
""", unsafe_allow_html=True)

m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("📁 Pedidos Totais", total)
m2.metric("🟢 Semáforo Verde (Aptos)", f"{perc_verde}%")
m3.metric("🚨 N5 / N6 (Urgência)", criticos)
m4.metric("🪑 Vagas de Desmarcação", vagas_livres)
m5.metric("❌ Pedidos Rejeitados", rejeitados_cnt)

st.write("")

# ---------------------------------------------------------------------
# 5. ESTRUTURA DE ABAS DE TRABALHO
# ---------------------------------------------------------------------
tabs = st.tabs([
    "📋 Fila de Agendamento (Pronto a Marcar)",
    "⚠️ Pendências & Validação Médica",
    "📄 Ficha de Cromo Digital Oficial",
    "❌ Pedidos Rejeitados",
    "🔄 Reaproveitamento de Vagas",
    "📊 Dashboard & Auditoria de Inflação"
])

# =====================================================================
# ABA 1: FILA DE AGENDAMENTO (PRONTO A MARCAR)
# =====================================================================
with tabs[0]:
    st.subheader("🎯 Fila Prioritária de Agendamento (Ordenação por Prioridade Final)")
    st.caption("Apenas pedidos aprovados e completos (`completo == 1`), ordenados de forma decrescente pela Prioridade Final (PF).")
    
    prontos = [p for p in pedidos if p['estado_calculado'] == 'pronto_para_marcar']
    prontos = sorted(prontos, key=lambda x: x['prioridade_final'], reverse=True)
    
    if not prontos:
        st.info("Não existem doentes em fila imediata para marcação de consulta/exame.")
    else:
        ch1, ch2, ch3, ch4, ch5, ch6 = st.columns([0.15, 0.30, 0.15, 0.15, 0.12, 0.13])
        ch1.markdown("**Prioridade Final**")
        ch2.markdown("**Doente & Diagnóstico**")
        ch3.markdown("**Nível / SLA**")
        ch4.markdown("**Etapa & Espera**")
        ch5.markdown("**Cromo**")
        ch6.markdown("**Ação**")
        st.markdown("---")
        
        for d in prontos:
            c1, c2, c3, c4, c5, c6 = st.columns([0.15, 0.30, 0.15, 0.15, 0.12, 0.13])
            with c1:
                pf = d['prioridade_final']
                cor_txt = "#b30000" if pf >= 80 else ("#d9534f" if pf >= 65 else "#0056b3")
                st.markdown(f"<span style='font-size:18px; font-weight:800; color:{cor_txt};'>{pf}%</span>", unsafe_allow_html=True)
                st.markdown("<span class='badge-semaforo-verde'>🟢 Pronto</span>", unsafe_allow_html=True)
            with c2:
                st.markdown(f"**{d['etiqueta_doente']}**")
                st.caption(f"{d['patologia']} | Estadiamento: {d['estadiamento']}")
            with c3:
                cfg = COLOR_MAP.get(d['cor'], {'badge_color': '#6c757d', 'text_color': '#ffffff'})
                st.markdown(f"<span style='background-color:{cfg['badge_color']}; color:{cfg['text_color']}; padding:3px 8px; border-radius:4px; font-weight:700; font-size:11px;'>{d['nivel']} - {d['cor']}</span>", unsafe_allow_html=True)
                if d['remarcacoes'] > 0:
                    st.caption(f"⚠️ Remarcações: {d['remarcacoes']}x ({d['origem_remarcacao']})")
            with c4:
                st.write(f"{d['etapa_clinica']}")
                atraso = d['dias_espera'] - d['sla_alvo_dias']
                if atraso > 0:
                    st.markdown(f"<span style='color:red; font-weight:700;'>{d['dias_espera']}d (+{atraso}d fora SLA)</span>", unsafe_allow_html=True)
                else:
                    st.caption(f"{d['dias_espera']}d decorridos (SLA {d['sla_alvo_dias']}d)")
            with c5:
                if st.button("🔍 Abrir", key=f"open_cromo_{d['id_pedido']}"):
                    st.session_state.cromo_id_ativo = d['id_pedido']
                    st.rerun()
            with c6:
                if st.button("📅 Agendar", key=f"agendar_{d['id_pedido']}", type="primary"):
                    conn = get_connection()
                    conn.execute("UPDATE cromos SET slot_info = ?, estado = 'Aceite' WHERE id_pedido = ?", (
                        f"{datetime.now().strftime('%d/%m')} - Gabinete Central", d['id_pedido']
                    ))
                    conn.commit()
                    conn.close()
                    st.success(f"Pedido #{d['id_pedido']} marcado com sucesso!")
                    st.rerun()
            st.markdown("<hr style='margin:4px 0 8px 0; border:0; border-top:1px solid #f0f0f0;'>", unsafe_allow_html=True)

# =====================================================================
# ABA 2: PENDÊNCIAS & VALIDAÇÃO MÉDICA (SEMÁFORO VERMELHO)
# =====================================================================
with tabs[1]:
    st.subheader("⚠️ Pedidos Retidos: Pendências Documentais & Validação Médica")
    st.caption("Processos com Semáforo Vermelho. A Prioridade Final NÃO é reduzida, garantindo equidade após a resolução da pendência.")
    
    pendentes = [p for p in pedidos if p['semaforo'] == 'Vermelho' and p['estado'] != 'Rejeitado']
    
    if not pendentes:
        st.success("✅ Excelente! Não existem pedidos pendentes de validação ou documentação em atraso.")
    else:
        for p in pendentes:
            with st.expander(f"🔴 Pedido #{p['id_pedido']} - {p['etiqueta_doente']} | Motivo: {p['motivo_pendencia'] or 'Aguardar Triagem de Cor / Validação de Data'}", expanded=True):
                pc1, pc2, pc3 = st.columns([0.4, 0.35, 0.25])
                with pc1:
                    st.markdown(f"**Serviço:** {p['servico_requisitante']}")
                    st.markdown(f"**Médico:** {p['requisitante']}")
                    st.markdown(f"**Patologia:** {p['patologia']}")
                    st.markdown(f"**Motivo Pendência:** `{p['motivo_pendencia'] or 'Validação de Triagem ou Proposta de Data'}`")
                    if p.get('nova_data_proposta'):
                        st.info(f"Nova Data Sugerida: **{p['nova_data_proposta']}**")
                with pc2:
                    st.markdown(f"**Prioridade Final Congelada:** `{p['prioridade_final']}%`")
                    progresso = min(1.0, p['dias_espera'] / max(1, p['sla_alvo_dias']))
                    st.write(f"Relógio SLA: {p['dias_espera']} de {p['sla_alvo_dias']} dias permitidos")
                    st.progress(progresso)
                    if p['dias_espera'] >= p['sla_alvo_dias']:
                        st.error("⚠️ SLA expirado! Pedido carece de decisão urgente para mitigar risco clínico.")
                with pc3:
                    st.markdown("**Ação de Desbloqueio:**")
                    nova_cor = p['cor']
                    if p['cor'] == 'Sem Cor':
                        nova_cor = st.selectbox("Validar Cor Triagem:", list(COLOR_MAP.keys()), key=f"sel_cor_{p['id_pedido']}")
                    doc_validada = st.checkbox("Documentação Conforme", value=True, key=f"chk_doc_{p['id_pedido']}")
                    
                    if st.button("🔓 Desbloquear & Aceitar", key=f"btn_unblock_{p['id_pedido']}"):
                        conn = get_connection()
                        conn.execute("""
                            UPDATE cromos 
                            SET completo = 1, cor = ?, motivo_pendencia = '', estado = 'Aceite'
                            WHERE id_pedido = ?
                        """, (nova_cor, p['id_pedido']))
                        conn.commit()
                        conn.close()
                        st.success(f"Pedido #{p['id_pedido']} regularizado com sucesso!")
                        st.rerun()

# =====================================================================
# ABA 3: FICHA DE CROMO DIGITAL OFICIAL DO IPO PORTO
# =====================================================================
with tabs[2]:
    st.subheader("📄 Visualização & Auditoria do Cromo Digital")
    st.caption("Formulário digital integral com todos os campos requisitados na folha clínica oficial.")
    
    lista_ids = [p['id_pedido'] for p in pedidos]
    idx_default = 0
    if st.session_state.cromo_id_ativo and st.session_state.cromo_id_ativo in lista_ids:
        idx_default = lista_ids.index(st.session_state.cromo_id_ativo)
        
    id_selecionado = st.selectbox("Selecione o Pedido para consulta / auditoria detalhada:", options=lista_ids, index=idx_default)
    cromo = next((p for p in pedidos if p['id_pedido'] == id_selecionado), None)
    
    if cromo:
        st.markdown(f"""
        <div class="cromo-paper">
            <div class="cromo-header-banner d-flex justify-content-between align-items-center">
                <div>
                    <h3 style="color:#0056b3; margin:0; font-weight:800;">📋 CROMO DIGITAL DE MARCAÇÃO #{cromo['id_pedido']}</h3>
                    <span style="color:#64748b; font-weight:600;">Instituto Português de Oncologia do Porto Francisco Gentil, EPE</span>
                </div>
            </div>
        """, unsafe_allow_html=True)
        
        col_st1, col_st2 = st.columns([0.7, 0.3])
        with col_st1:
            st.write(f"**Estado Atual no Sistema:** `{cromo['estado']}` | **Semáforo:** `{cromo['semaforo']}`")
        with col_st2:
            cfg_cor = COLOR_MAP.get(cromo['cor'], {'badge_color': '#6c757d', 'text_color': '#ffffff'})
            st.markdown(f"<div style='text-align:right;'><span style='background-color:{cfg_cor['badge_color']}; color:{cfg_cor['text_color']}; padding:6px 14px; border-radius:6px; font-weight:bold;'>Triagem: {cromo['nivel']} ({cromo['cor']})</span></div>", unsafe_allow_html=True)
        
        # SECÇÃO 1: IDENTIFICAÇÃO GERAL
        st.markdown("<div class='cromo-section-title'>Secção 1: Identificação Geral do Doente & Requisitante</div>", unsafe_allow_html=True)
        s1_c1, s1_c2, s1_c3 = st.columns(3)
        with s1_c1:
            st.markdown(f"<div class='field-box'><span class='field-label'>Nº Processo</span><span class='field-value'>{cromo['id_doente']}</span></div>", unsafe_allow_html=True)
            st.markdown(f"<div class='field-box'><span class='field-label'>Patologia Primária</span><span class='field-value'>{cromo['patologia']}</span></div>", unsafe_allow_html=True)
        with s1_c2:
            st.markdown(f"<div class='field-box'><span class='field-label'>Etiqueta Completa</span><span class='field-value'>{cromo['etiqueta_doente']}</span></div>", unsafe_allow_html=True)
            st.markdown(f"<div class='field-box'><span class='field-label'>Estadiamento / ECOG</span><span class='field-value'>{cromo['estadiamento']} (ECOG {cromo['ecog']})</span></div>", unsafe_allow_html=True)
        with s1_c3:
            st.markdown(f"<div class='field-box'><span class='field-label'>Serviço Requisitante</span><span class='field-value'>{cromo['servico_requisitante']}</span></div>", unsafe_allow_html=True)
            st.markdown(f"<div class='field-box'><span class='field-label'>Médico Requisitante</span><span class='field-value'>{cromo['requisitante']}</span></div>", unsafe_allow_html=True)

        # SECÇÃO 2: MARCAÇÃO DE CONSULTAS
        st.markdown("<div class='cromo-section-title'>Secção 2: Marcação de Consultas</div>", unsafe_allow_html=True)
        s2_c1, s2_c2, s2_c3 = st.columns(3)
        with s2_c1:
            st.checkbox("Próxima Consulta", value=(cromo['chk_prox_consulta'] == '1'), disabled=True)
            st.write(f"Data Solicitada: **{cromo['dt_prox_consulta'] or 'N/D'}**")
        with s2_c2:
            st.checkbox("Consulta p/ Processo", value=(cromo['chk_cons_processo'] == '1'), disabled=True)
            st.write(f"Data: **{cromo['dt_cons_processo'] or 'N/D'}**")
        with s2_c3:
            st.checkbox("Consulta de Grupo", value=(cromo['chk_cons_grupo'] == '1'), disabled=True)
            st.write(f"Grupo: **{cromo['cg_esp_tipo'] or 'N/D'}** ({cromo['cg_dt'] or 'Sem data'})")

        # SECÇÃO 3: HOSPITAL DE DIA
        st.markdown("<div class='cromo-section-title'>Secção 3: Hospital de Dia & Tratamentos Sistémicos</div>", unsafe_allow_html=True)
        s3_c1, s3_c2 = st.columns(2)
        with s3_c1:
            st.checkbox("Hospital de Dia Requisitado", value=(cromo['chk_hosp_dia'] == '1'), disabled=True)
            st.write(f"Protocolo / Tratamento: **{cromo['hd_tratamento'] or 'Nenhum'}**")
        with s3_c2:
            st.write(f"Data Pretendida para Início: **{cromo['hd_dt'] or 'Não especificada'}**")

        # SECÇÃO 4: EXAMES E ANÁLISES CLÍNICAS
        st.markdown("<div class='cromo-section-title'>Secção 4: Exames e Análises Clínicas</div>", unsafe_allow_html=True)
        s4_c1, s4_c2, s4_c3 = st.columns(3)
        with s4_c1:
            st.checkbox("Exames no Mural", value=(cromo['chk_exames_mural'] == '1'), disabled=True)
            st.checkbox("Análises no Mural", value=(cromo['chk_analises_mural'] == '1'), disabled=True)
            if cromo['chk_com_jejum'] == '1':
                st.warning("⚠️ Requer Jejum")
            if cromo['chk_sem_jejum'] == '1':
                st.info("ℹ️ Sem Jejum")
        with s4_c2:
            st.checkbox("Outros Exames / Imagiologia", value=(cromo['chk_outros_exames'] == '1'), disabled=True)
            if cromo['oe_exame1']:
                st.write(f"1. **{cromo['oe_exame1']}** ({cromo['oe_dt1']})")
        with s4_c3:
            if cromo['oe_exame2']:
                st.write(f"2. **{cromo['oe_exame2']}** ({cromo['oe_dt2']})")

        # SECÇÃO 5: TRANSPORTE & OBSERVAÇÕES
        st.markdown("<div class='cromo-section-title'>Secção 5: Transporte & Outros Requisitos</div>", unsafe_allow_html=True)
        s5_c1, s5_c2 = st.columns(2)
        with s5_c1:
            st.checkbox("Credencial de Transporte Requisitada", value=(cromo['chk_credencial_transp'] == '1'), disabled=True)
        with s5_c2:
            st.write(f"Observações: **{cromo['outros_desc'] or 'Sem notas adicionais'}**")

        # SECÇÃO 6: MOTOR MATEMÁTICO & AUDITORIA DE PRIORIDADE
        st.markdown("<div class='cromo-section-title'>Secção 6: Decomposição da Prioridade Final (PF)</div>", unsafe_allow_html=True)
        sf1, sf2, sf3, sf4, sf5 = st.columns(5)
        sf1.metric("Score Triagem (S)", f"{COLOR_MAP.get(cromo['cor'], {}).get('score', 0.0)} / 5.0")
        sf2.metric("Hierarquia (H)", f"{H_MAP.get(cromo['etapa_clinica'], 1.0)} / 5.0")
        sf3.metric("Espera / SLA (W)", f"{cromo['dias_espera']}d / {cromo['sla_alvo_dias']}d")
        sf4.metric("Fator R (Remarcação)", cromo['r_score'])
        sf5.metric("PRIORIDADE FINAL", f"{cromo['prioridade_final']}%")

        st.markdown("</div>", unsafe_allow_html=True)

        # BOTÕES DE DECISÃO CLÍNICA DO CROMO
        st.markdown("#### ⚖️ Decisão Operacional sobre o Pedido")
        bcol1, bcol2, bcol3 = st.columns(3)
        
        with bcol1:
            if st.button("✅ Aceitar Pedido", key=f"cromo_aceitar_{cromo['id_pedido']}", use_container_width=True, type="primary"):
                conn = get_connection()
                conn.execute("UPDATE cromos SET estado = 'Aceite', motivo_rejeicao = '' WHERE id_pedido = ?", (cromo['id_pedido'],))
                conn.commit()
                conn.close()
                st.success(f"Pedido #{cromo['id_pedido']} marcado como ACEITE!")
                st.rerun()
                
        with bcol2:
            with st.popover("❌ Rejeitar Pedido", use_container_width=True):
                st.write("**Motivo Formal de Rejeição:**")
                motivo = st.selectbox(
                    "Selecione o motivo: ",
                    [
                        "Sem vaga disponível na data solicitada", 
                        "Aguardar resultados de exames pendentes", 
                        "Incompatibilidade com protocolo clínico", 
                        "Pedido duplicado no sistema", 
                        "Critérios de urgência não fundamentados"
                    ],
                    key=f"rej_mot_{cromo['id_pedido']}"
                )
                if st.button("Confirmar Rejeição", key=f"conf_rej_{cromo['id_pedido']}"):
                    conn = get_connection()
                    conn.execute("UPDATE cromos SET estado = 'Rejeitado', motivo_rejeicao = ? WHERE id_pedido = ?", (motivo, cromo['id_pedido']))
                    conn.commit()
                    conn.close()
                    st.warning(f"Pedido #{cromo['id_pedido']} rejeitado.")
                    st.rerun()

        with bcol3:
            with st.popover("📅 Propor Nova Data", use_container_width=True):
                st.write("**Submeter Contraproposta ao Requisitante:**")
                nova_data = st.text_input("Nova Data Proposta (DD/MM/AAAA):", value=(datetime.now() + timedelta(days=14)).strftime('%d/%m/%Y'), key=f"nd_{cromo['id_pedido']}")
                if st.button("Enviar para Validação Médica", key=f"btn_sub_nd_{cromo['id_pedido']}"):
                    conn = get_connection()
                    conn.execute("UPDATE cromos SET estado = 'Proposta_Data', nova_data_proposta = ?, dt_prox_consulta = ? WHERE id_pedido = ?", (nova_data, nova_data, cromo['id_pedido']))
                    conn.commit()
                    conn.close()
                    st.info(f"Proposta enviada para o pedido #{cromo['id_pedido']}!")
                    st.rerun()

# =====================================================================
# ABA 4: HISTÓRICO DE PEDIDOS REJEITADOS
# =====================================================================
with tabs[3]:
    st.subheader("❌ Repositório de Pedidos Rejeitados")
    st.caption("Registo histórico de auditoria hospitalar com motivos formais de recusa e opção de reabertura.")
    
    rejeitados = [p for p in pedidos if p['estado'] == 'Rejeitado']
    
    if not rejeitados:
        st.info("Nenhum pedido se encontra atualmente no estado Rejeitado.")
    else:
        df_rej = pd.DataFrame([{
            'ID': p['id_pedido'],
            'Doente': p['etiqueta_doente'],
            'Serviço': p['servico_requisitante'],
            'Médico': p['requisitante'],
            'Motivo da Rejeição': p['motivo_rejeicao'],
            'Data Emissão': p['data_emissao'],
            'Prioridade': f"{p['prioridade_final']}%"
        } for p in rejeitados])
        
        st.dataframe(df_rej, use_container_width=True)
        
        st.write("**Reavaliação de Casos:**")
        id_reabrir = st.selectbox("Selecione um pedido para reabrir / retificar:", options=[p['id_pedido'] for p in rejeitados])
        if st.button("♻️ Reabrir Pedido (Retornar a Pendente)"):
            conn = get_connection()
            conn.execute("UPDATE cromos SET estado = 'Pendente', motivo_rejeicao = '' WHERE id_pedido = ?", (id_reabrir,))
            conn.commit()
            conn.close()
            st.success(f"Pedido #{id_reabrir} reaberto com sucesso!")
            st.rerun()

# =====================================================================
# ABA 5: REAPROVEITAMENTO INTELIGENTE DE VAGAS (DESMARCAÇÕES)
# =====================================================================
with tabs[4]:
    st.subheader("🔄 Sistema de Recuperação e Matching Imediato de Vagas")
    st.caption("Combate o desperdício de tempos de bloco/consulta: sugere de imediato o Top 3 da fila apta para ocupar vagas libertadas.")
    
    c_slot1, c_slot2 = st.columns([0.45, 0.55])
    
    with c_slot1:
        st.markdown("#### 1. Libertar Vaga (Desmarcação / Falta)")
        agendados = [p for p in pedidos if p['slot_info'] and p['slot_info'].strip()]
        
        if agendados:
            mapa_ag = {f"#{p['id_pedido']} - {p['etiqueta_doente']} ({p['slot_info']})": p['id_pedido'] for p in agendados}
            escolhido_str = st.selectbox("Selecione o doente que desmarcou:", list(mapa_ag.keys()))
            motivo_cancel = st.selectbox("Origem do Cancelamento:", ["equipa_clinica", "doente", "outros"])
            
            if st.button("🚨 Registar Desmarcação & Libertar Vaga", type="secondary"):
                id_canc = mapa_ag[escolhido_str]
                p_canc = next(x for x in pedidos if x['id_pedido'] == id_canc)
                
                nova_vaga = {
                    'id': f"VAGA-{len(st.session_state.slots_vagos) + 1}",
                    'info': p_canc['slot_info'],
                    'libertado_por': p_canc['etiqueta_doente'],
                    'timestamp': datetime.now().strftime("%d/%m/%Y %H:%M")
                }
                st.session_state.slots_vagos.append(nova_vaga)
                
                conn = get_connection()
                conn.execute("""
                    UPDATE cromos 
                    SET slot_info = '', remarcacoes = remarcacoes + 1, origem_remarcacao = ?, dias_desde_ultima_remarcacao = 0
                    WHERE id_pedido = ?
                """, (motivo_cancel, id_canc))
                conn.commit()
                conn.close()
                st.warning("Vaga disponibilizada! Doente atualizado na base de dados.")
                st.rerun()
        else:
            st.info("Nenhum doente com vaga alocada no momento.")
            if st.button("➕ Simular Vaga de Encaixe de Urgência"):
                st.session_state.slots_vagos.append({
                    'id': f"VAGA-URG-{len(st.session_state.slots_vagos) + 1}",
                    'info': 'Amanhã 09:15 - Gabinete 4 (Exames Imagiologia)',
                    'libertado_por': 'Encaixe de Urgência',
                    'timestamp': datetime.now().strftime("%d/%m/%Y %H:%M")
                })
                st.rerun()
                
    with c_slot2:
        st.markdown("#### 2. Vagas Disponíveis & Matching Algorítmico")
        if not st.session_state.slots_vagos:
            st.success("Sem vagas por reaproveitar no momento. Ocupação a 100%.")
        else:
            for idx_v, v in enumerate(st.session_state.slots_vagos):
                st.markdown(f"""
                <div style='background-color:#e0f2fe; border:1px solid #7dd3fc; padding:12px; border-radius:8px; margin-bottom:12px;'>
                    <strong>🎯 Vaga Aberta:</strong> {v['info']}<br>
                    <small style='color:#0369a1;'>Origem: {v['libertado_por']} | Criada em: {v['timestamp']}</small>
                </div>
                """, unsafe_allow_html=True)
                
                candidatos = [p for p in pedidos if p['estado_calculado'] == 'pronto_para_marcar']
                top3 = sorted(candidatos, key=lambda x: x['prioridade_final'], reverse=True)[:3]
                
                if not top3:
                    st.warning("Não há doentes elegíveis na fila.")
                else:
                    st.markdown("**Top 3 Doentes Recomendados pelo Algoritmo:**")
                    for rank, cand in enumerate(top3, start=1):
                        sc1, sc2, sc3 = st.columns([0.15, 0.60, 0.25])
                        sc1.markdown(f"**#{rank} ({cand['prioridade_final']}%)**")
                        sc2.markdown(f"{cand['etiqueta_doente']} | {cand['patologia']} ({cand['cor']})")
                        if sc3.button("⚡ Alocar", key=f"alocar_{v['id']}_{cand['id_pedido']}"):
                            conn = get_connection()
                            conn.execute("UPDATE cromos SET slot_info = ?, estado = 'Aceite' WHERE id_pedido = ?", (v['info'], cand['id_pedido']))
                            conn.commit()
                            conn.close()
                            st.session_state.slots_vagos.pop(idx_v)
                            st.success(f"Doente {cand['etiqueta_doente']} marcado no slot!")
                            st.rerun()
                st.markdown("---")

# =====================================================================
# ABA 6: DASHBOARD DE GESTÃO & ALERTA DE INFLAÇÃO DE CORES
# =====================================================================
with tabs[5]:
    st.subheader("📊 Auditoria Clínica: Deteção de Inflação de Cores de Triagem")
    st.caption("Prevenção de sobretriagem: alerta médicos com >30% de pedidos classificados como 'Crítico' ou 'Muito Alto'.")
    
    df_auditoria = pd.DataFrame([{
        'medico': p['requisitante'],
        'id': p['id_pedido'],
        'critico': 1 if p['cor'] in ['Crítico', 'Muito Alto'] else 0
    } for p in pedidos])
    
    if not df_auditoria.empty:
        resumo_med = df_auditoria.groupby('medico').agg(
            Total_Pedidos=('id', 'count'),
            Pedidos_Criticos=('critico', 'sum')
        ).reset_index()
        
        resumo_med['% Inflação (Críticos)'] = ((resumo_med['Pedidos_Criticos'] / resumo_med['Total_Pedidos']) * 100).round(1)
        
        medicos_inflacao = resumo_med[resumo_med['% Inflação (Críticos)'] > 30.0]
        
        if not medicos_inflacao.empty:
            st.error("### 🚨 ALERTA DE AUDITORIA: Sobretriagem Detetada!")
            st.markdown("Os seguintes clínicos ultrapassaram o teto de **30%** em pedidos de prioridade máxima:")
            for _, r in medicos_inflacao.iterrows():
                st.markdown(f"- **{r['medico']}**: `{r['% Inflação (Críticos)']}%` pedidos críticos ({r['Pedidos_Criticos']} em {r['Total_Pedidos']})")
        else:
            st.success("✅ Todos os prescritores respeitam os limiares estatísticos normais do IPO Porto.")
            
        dcol1, dcol2 = st.columns(2)
        with dcol1:
            st.markdown("**Tabela de Auditoria por Prescritor:**")
            st.dataframe(resumo_med, use_container_width=True)
        with dcol2:
            st.markdown("**Distribuição Geral de Cores de Triagem:**")
            contagem = pd.Series([p['cor'] for p in pedidos]).value_counts()
            st.bar_chart(contagem)
            
    st.markdown("---")
    st.subheader("💾 Exportação de Dados")
    csv_buffer = io.StringIO()
    pd.DataFrame(pedidos).to_csv(csv_buffer, index=False)
    st.download_button(
        label="📥 Exportar Base de Dados Completa (CSV)",
        data=csv_buffer.getvalue(),
        file_name="ipo_porto_dados_completos.csv",
        mime="text/csv"
    )
