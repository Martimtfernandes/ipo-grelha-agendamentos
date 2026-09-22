# ipo-grelha-agendamentos

import streamlit as st
import pandas as pd
import numpy as np
import math
from datetime import datetime, timedelta

# =====================================================================
# 1. CONFIGURAÇÃO DA PÁGINA & CONSTANTES CLÍNICAS (HEALTH TECH - IPO)
# =====================================================================
st.set_page_config(
    page_title="IPO - Grelha Administrativa de Agendamentos",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Mapeamento oficial de Rótulos / Triagem Oncológica
COLOR_MAP = {
    'Crítico': {'score': 5.0, 'sla': 3, 'nivel': 'N6', 'badge_color': '#b30000', 'text_color': '#ffffff'},
    'Muito Alto': {'score': 4.2, 'sla': 7, 'nivel': 'N5', 'badge_color': '#d9534f', 'text_color': '#ffffff'},
    'Alto': {'score': 3.5, 'sla': 14, 'nivel': 'N4', 'badge_color': '#f0ad4e', 'text_color': '#ffffff'},
    'Moderado': {'score': 2.8, 'sla': 30, 'nivel': 'N3', 'badge_color': '#ffd200', 'text_color': '#000000'},
    'Baixo': {'score': 2.0, 'sla': 60, 'nivel': 'N2', 'badge_color': '#5bc0de', 'text_color': '#ffffff'},
    'Rotina': {'score': 1.0, 'sla': 90, 'nivel': 'N1', 'badge_color': '#6c757d', 'text_color': '#ffffff'}
}

# Hierarquia Clínica (H_MAP)
H_MAP = {
    'Diagnostico': 5.0,
    'Estadiamento': 4.0,
    'Decisao_terapeutica': 3.0,
    'Tratamento': 2.0,
    'Follow_up': 1.0
}

# Fatores de Ponderação para Remarcações
ORIGEM_REMARCACAO = {
    'equipa_clinica': 1.5,
    'doente': 0.75,
    'outros': 1.0
}

# =====================================================================
# 2. MOTOR DE CÁLCULO E PIPELINE ETL
# =====================================================================
def calcular_metricas_paciente(p: dict) -> dict:
    res = p.copy()
    cor = res.get('cor')
    
    # 1. Rótulo e SLA
    if cor in COLOR_MAP:
        score_val = COLOR_MAP[cor]['score']
        sla_alvo = COLOR_MAP[cor]['sla']
        res['nivel'] = COLOR_MAP[cor]['nivel']
    else:
        score_val = 0.0
        sla_alvo = 30
        res['nivel'] = 'N0 (Indefinido)'
        cor = None
        res['cor'] = 'Sem Cor'

    res['sla_alvo_dias'] = sla_alvo

    # Componentes normalizados [0.0 - 1.0]
    S = score_val / 5.0
    
    etapa = res.get('etapa_clinica', 'Follow_up')
    H = H_MAP.get(etapa, 1.0) / 5.0
    
    dias_espera = res.get('dias_espera', 0)
    W = min(1.0, dias_espera / max(1, sla_alvo))
    
    M = res.get('complexidade_m', 0.5)
    
    # Cálculo de R (Remarcações)
    remarcacoes = res.get('remarcacoes', 0)
    if remarcacoes > 0:
        origem = res.get('origem_remarcacao', 'outros')
        origem_factor = ORIGEM_REMARCACAO.get(origem, 1.0)
        dias_desde_ultima = res.get('dias_desde_ultima_remarcacao', 0)
        R_base = min(1.0, remarcacoes / 3.0) * origem_factor * math.exp(-0.05 * dias_desde_ultima)
    else:
        R_base = 0.0
    res['r_score'] = round(R_base, 3)

    # Fórmula de Prioridade Final (PF)
    PF_raw = (0.55 * S) + (0.18 * H) + (0.12 * W) + (0.05 * M) + (0.10 * R_base)
    res['prioridade_final'] = round(max(0.0, min(1.0, PF_raw)) * 100, 1)

    # Regra de Semáforo e Estado C (Completude)
    if res.get('estado') == 'agendado':
        res['semaforo'] = 'Azul'
    elif not res.get('completo', True):
        res['estado'] = 'bloqueado_pendencia'
        res['semaforo'] = 'Vermelho'
    elif res.get('cor') == 'Sem Cor' or cor is None:
        res['estado'] = 'em_validacao_medica'
        res['semaforo'] = 'Vermelho'
    else:
        res['estado'] = 'pronto_para_marcar'
        res['semaforo'] = 'Verde'

    return res

def atualizar_base_dados():
    novos_dados = []
    for p in st.session_state.doentes:
        novos_dados.append(calcular_metricas_paciente(p))
    st.session_state.doentes = novos_dados

# =====================================================================
# 3. DADOS DE TESTE (MOCK DATA IPO)
# =====================================================================
def inicializar_dados():
    if "doentes" not in st.session_state:
        dados_iniciais = [
            {
                'id': 'IPO-2026-001',
                'nome': 'João Manuel Silva',
                'idade': 68,
                'patologia': 'Adenocarcinoma do Cólon',
                'estadiamento': 'T4N2M1 (Estádio IV)',
                'ecog': 1,
                'cor': 'Crítico',
                'etapa_clinica': 'Tratamento',
                'dias_espera': 4,
                'remarcacoes': 1,
                'origem_remarcacao': 'equipa_clinica',
                'dias_desde_ultima_remarcacao': 2,
                'completo': True,
                'motivo_pendencia': '',
                'medico_prescritor': 'Dr. António Santos',
                'complexidade_m': 0.85,
                'estado': 'pronto_para_marcar'
            },
            {
                'id': 'IPO-2026-002',
                'nome': 'Maria Helena Fernandes',
                'idade': 54,
                'patologia': 'Carcinoma Ductal Invasivo Mama',
                'estadiamento': 'T2N1M0 (Estádio IIB)',
                'ecog': 0,
                'cor': 'Muito Alto',
                'etapa_clinica': 'Decisao_terapeutica',
                'dias_espera': 6,
                'remarcacoes': 0,
                'origem_remarcacao': 'outros',
                'dias_desde_ultima_remarcacao': 0,
                'completo': True,
                'motivo_pendencia': '',
                'medico_prescritor': 'Dra. Clara Meireles',
                'complexidade_m': 0.60,
                'estado': 'pronto_para_marcar'
            },
            {
                'id': 'IPO-2026-003',
                'nome': 'Carlos Alberto Pereira',
                'idade': 72,
                'patologia': 'Neoplasia Maligna do Pulmão (CPNPC)',
                'estadiamento': 'T3N2M0 (Estádio IIIA)',
                'ecog': 2,
                'cor': 'Crítico',
                'etapa_clinica': 'Diagnostico',
                'dias_espera': 5,
                'remarcacoes': 2,
                'origem_remarcacao': 'doente',
                'dias_desde_ultima_remarcacao': 8,
                'completo': False,
                'motivo_pendencia': 'Falta TC Torácica com Contraste e Prova Renal',
                'medico_prescritor': 'Dr. António Santos',
                'complexidade_m': 0.90,
                'estado': 'bloqueado_pendencia'
            },
            {
                'id': 'IPO-2026-004',
                'nome': 'Ana Paula Ramos',
                'idade': 49,
                'patologia': 'Linfoma Difuso de Grandes Células B',
                'estadiamento': 'Estádio III',
                'ecog': 1,
                'cor': 'Alto',
                'etapa_clinica': 'Estadiamento',
                'dias_espera': 12,
                'remarcacoes': 1,
                'origem_remarcacao': 'outros',
                'dias_desde_ultima_remarcacao': 5,
                'completo': True,
                'motivo_pendencia': '',
                'medico_prescritor': 'Dr. Rui Carreira',
                'complexidade_m': 0.50,
                'estado': 'pronto_para_marcar'
            },
            {
                'id': 'IPO-2026-005',
                'nome': 'Manuel Ferreira Costa',
                'idade': 61,
                'patologia': 'Adenocarcinoma da Próstata',
                'estadiamento': 'ISUP 3 (Gleason 4+3)',
                'ecog': 0,
                'cor': 'Moderado',
                'etapa_clinica': 'Decisao_terapeutica',
                'dias_espera': 22,
                'remarcacoes': 0,
                'origem_remarcacao': 'outros',
                'dias_desde_ultima_remarcacao': 0,
                'completo': True,
                'motivo_pendencia': '',
                'medico_prescritor': 'Dra. Clara Meireles',
                'complexidade_m': 0.35,
                'estado': 'pronto_para_marcar'
            },
            {
                'id': 'IPO-2026-006',
                'nome': 'Teresa Guimarães Vilar',
                'idade': 58,
                'patologia': 'Sarcoma Pleomórfico Extremidade',
                'estadiamento': 'Estádio II',
                'ecog': 1,
                'cor': 'Sem Cor',
                'etapa_clinica': 'Diagnostico',
                'dias_espera': 3,
                'remarcacoes': 0,
                'origem_remarcacao': 'outros',
                'dias_desde_ultima_remarcacao': 0,
                'completo': True,
                'motivo_pendencia': 'Pedido submetido sem triagem de cor / validação médica',
                'medico_prescritor': 'Dr. António Santos',
                'complexidade_m': 0.70,
                'estado': 'em_validacao_medica'
            },
            {
                'id': 'IPO-2026-007',
                'nome': 'António Henriques Lima',
                'idade': 76,
                'patologia': 'Carcinoma Gástrico Antral',
                'estadiamento': 'cT3N1M0',
                'ecog': 2,
                'cor': 'Muito Alto',
                'etapa_clinica': 'Tratamento',
                'dias_espera': 9,
                'remarcacoes': 1,
                'origem_remarcacao': 'equipa_clinica',
                'dias_desde_ultima_remarcacao': 1,
                'completo': False,
                'motivo_pendencia': 'Ausência de Consentimento Informado Assinado',
                'medico_prescritor': 'Dr. António Santos',
                'complexidade_m': 0.85,
                'estado': 'bloqueado_pendencia'
            },
            {
                'id': 'IPO-2026-008',
                'nome': 'Sandra Batista Pinto',
                'idade': 42,
                'patologia': 'Melanoma Nodular Ulcerado',
                'estadiamento': 'Breslow 3.2mm, Clark IV',
                'ecog': 0,
                'cor': 'Crítico',
                'etapa_clinica': 'Diagnostico',
                'dias_espera': 3,
                'remarcacoes': 0,
                'origem_remarcacao': 'outros',
                'dias_desde_ultima_remarcacao': 0,
                'completo': True,
                'motivo_pendencia': '',
                'medico_prescritor': 'Dra. Sofia Lourenço',
                'complexidade_m': 0.75,
                'estado': 'pronto_para_marcar'
            },
            {
                'id': 'IPO-2026-009',
                'nome': 'Fernando Jorge Sousa',
                'idade': 65,
                'patologia': 'Carcinoma Hepatocelular',
                'estadiamento': 'Child-Pugh A, BCLC B',
                'ecog': 1,
                'cor': 'Alto',
                'etapa_clinica': 'Tratamento',
                'dias_espera': 15,
                'remarcacoes': 2,
                'origem_remarcacao': 'equipa_clinica',
                'dias_desde_ultima_remarcacao': 4,
                'completo': True,
                'motivo_pendencia': '',
                'medico_prescritor': 'Dr. Rui Carreira',
                'complexidade_m': 0.80,
                'estado': 'pronto_para_marcar'
            },
            {
                'id': 'IPO-2026-010',
                'nome': 'Beatriz Carvalho Neto',
                'idade': 51,
                'patologia': 'Carcinoma do Colo do Útero',
                'estadiamento': 'FIGO IIB',
                'ecog': 0,
                'cor': 'Moderado',
                'etapa_clinica': 'Estadiamento',
                'dias_espera': 28,
                'remarcacoes': 0,
                'origem_remarcacao': 'outros',
                'dias_desde_ultima_remarcacao': 0,
                'completo': False,
                'motivo_pendencia': 'Parecer da Comissão de Tumores Ginecológicos em atraso',
                'medico_prescritor': 'Dr. Rui Carreira',
                'complexidade_m': 0.45,
                'estado': 'bloqueado_pendencia'
            },
            {
                'id': 'IPO-2026-011',
                'nome': 'José Agostinho Morgado',
                'idade': 69,
                'patologia': 'Neoplasia da Bexiga Não Músculo-Invasiva',
                'estadiamento': 'TaG1 Alto Risco',
                'ecog': 1,
                'cor': 'Baixo',
                'etapa_clinica': 'Follow_up',
                'dias_espera': 45,
                'remarcacoes': 1,
                'origem_remarcacao': 'doente',
                'dias_desde_ultima_remarcacao': 18,
                'completo': True,
                'motivo_pendencia': '',
                'medico_prescritor': 'Dra. Sofia Lourenço',
                'complexidade_m': 0.30,
                'estado': 'pronto_para_marcar'
            },
            {
                'id': 'IPO-2026-012',
                'nome': 'Helena Maria Dias',
                'idade': 60,
                'patologia': 'Carcinoma Papilar da Tiroideia',
                'estadiamento': 'T1bN0M0 (Pós-Tiroidectomia)',
                'ecog': 0,
                'cor': 'Rotina',
                'etapa_clinica': 'Follow_up',
                'dias_espera': 75,
                'remarcacoes': 0,
                'origem_remarcacao': 'outros',
                'dias_desde_ultima_remarcacao': 0,
                'completo': True,
                'motivo_pendencia': '',
                'medico_prescritor': 'Dra. Sofia Lourenço',
                'complexidade_m': 0.20,
                'estado': 'pronto_para_marcar'
            },
            {
                'id': 'IPO-2026-013',
                'nome': 'Rodrigo Manuel Esteves',
                'idade': 63,
                'patologia': 'Carcinoma Epidermoide Laringe',
                'estadiamento': 'cT4aN1M0',
                'ecog': 2,
                'cor': 'Crítico',
                'etapa_clinica': 'Tratamento',
                'dias_espera': 3,
                'remarcacoes': 1,
                'origem_remarcacao': 'equipa_clinica',
                'dias_desde_ultima_remarcacao': 1,
                'completo': True,
                'motivo_pendencia': '',
                'medico_prescritor': 'Dr. António Santos',
                'complexidade_m': 0.90,
                'estado': 'agendado',
                'slot_info': '24/Set 09:30 - Bloco C / TAC Oncológico 2'
            },
            {
                'id': 'IPO-2026-014',
                'nome': 'Luísa Fontes Mendes',
                'idade': 57,
                'patologia': 'Carcinoma Ovariano Seroso Alto Grau',
                'estadiamento': 'Estádio IIIC',
                'ecog': 1,
                'cor': 'Muito Alto',
                'etapa_clinica': 'Decisao_terapeutica',
                'dias_espera': 7,
                'remarcacoes': 0,
                'origem_remarcacao': 'outros',
                'dias_desde_ultima_remarcacao': 0,
                'completo': True,
                'motivo_pendencia': '',
                'medico_prescritor': 'Dr. António Santos',
                'complexidade_m': 0.70,
                'estado': 'agendado',
                'slot_info': '24/Set 14:00 - Gabinete 12 / Oncologia Médica'
            }
        ]
        st.session_state.doentes = [calcular_metricas_paciente(p) for p in dados_iniciais]
    
    if "slots_vagos" not in st.session_state:
        st.session_state.slots_vagos = []

    if "cromo_selecionado" not in st.session_state:
        st.session_state.cromo_selecionado = None

inicializar_dados()

# =====================================================================
# 4. COMPONENTES VISUAIS & ESTILIZAÇÃO CSS
# =====================================================================
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(90deg, #002b49 0%, #005a9c 100%);
        padding: 18px 24px;
        border-radius: 8px;
        color: white;
        margin-bottom: 20px;
    }
    .header-title {
        font-size: 26px;
        font-weight: 700;
        margin: 0;
    }
    .header-sub {
        font-size: 14px;
        opacity: 0.9;
        margin: 4px 0 0 0;
    }
    .cromo-box {
        background-color: #f8f9fa;
        border: 1px solid #dee2e6;
        border-radius: 8px;
        padding: 20px;
        margin-top: 10px;
        margin-bottom: 15px;
    }
    .cromo-title {
        color: #002b49;
        font-weight: 700;
        font-size: 18px;
        border-bottom: 2px solid #005a9c;
        padding-bottom: 6px;
        margin-bottom: 12px;
    }
</style>
""", unsafe_allow_html=True)

# Top Banner
st.markdown("""
<div class="main-header">
    <div class="header-title">🏛️ IPO - Grelha Administrativa de Agendamentos</div>
    <div class="header-sub">Plataforma de Otimização de Fluxo e Triagem Oncológica Multidimensional | Modelo H-W-M-R</div>
</div>
""", unsafe_allow_html=True)

# =====================================================================
# 5. BARRA SUPERIOR: MÉTRICAS EM TEMPO REAL
# =====================================================================
doentes_todos = st.session_state.doentes
total_doentes = len(doentes_todos)
verdes = sum(1 for d in doentes_todos if d['semaforo'] == 'Verde')
perc_verde = round((verdes / total_doentes) * 100, 1) if total_doentes > 0 else 0

criticos_n5_n6 = sum(1 for d in doentes_todos if d.get('cor') in ['Crítico', 'Muito Alto'])
slots_vagos_count = len(st.session_state.slots_vagos)

mcol1, mcol2, mcol3, mcol4 = st.columns(4)
with mcol1:
    st.metric(label="👥 Total de Pedidos Ativos", value=total_doentes)
with mcol2:
    st.metric(label="🟢 % Semáforo Verde (Aptos)", value=f"{perc_verde}%")
with mcol3:
    st.metric(label="🚨 Casos N5 / N6 (Crítico & M.Alto)", value=criticos_n5_n6)
with mcol4:
    st.metric(label="🪑 Vagas Livres (Desmarcações)", value=slots_vagos_count)

st.markdown("---")

# =====================================================================
# 6. ESTRUTURA DE ABAS
# =====================================================================
aba1, aba2, aba3, aba4 = st.tabs([
    "📋 Fila de Agendamento (Pronto a Marcar)",
    "⚠️ Aba Prioritária de Pendências (Semáforo Vermelho)",
    "🔄 Reaproveitamento de Vagas (Desmarcações)",
    "📊 Dashboard de Gestão & Alertas Clínicos"
])

def render_badge_nivel(nivel: str, cor_nome: str):
    cfg = COLOR_MAP.get(cor_nome, {'badge_color': '#6c757d', 'text_color': '#ffffff'})
    return f"<span style='background-color:{cfg['badge_color']}; color:{cfg['text_color']}; padding:3px 8px; border-radius:4px; font-weight:600; font-size:12px;'>{nivel} - {cor_nome}</span>"

# ABA 1: FILA DE AGENDAMENTO
with aba1:
    st.subheader("🎯 Fila Prioritária de Agendamento")
    st.caption("Doentes com documentação completa (`completo == True`) e triagem validada, ordenados estritamente pela Prioridade Final (PF).")

    if st.session_state.cromo_selecionado:
        p_cromo = next((d for d in st.session_state.doentes if d['id'] == st.session_state.cromo_selecionado), None)
        if p_cromo:
            with st.container():
                st.markdown("""<div class="cromo-box">""", unsafe_allow_html=True)
                c_header, c_close = st.columns([0.88, 0.12])
                with c_header:
                    st.markdown(f"<div class='cromo-title'>📋 Cromo Digital do Doente: {p_cromo['nome']} ({p_cromo['id']})</div>", unsafe_allow_html=True)
                with c_close:
                    if st.button("✖ Fechar", key="btn_close_cromo"):
                        st.session_state.cromo_selecionado = None
                        st.rerun()
                
                c1, c2, c3 = st.columns(3)
                with c1:
                    st.markdown(f"**Idade:** {p_cromo['idade']} anos")
                    st.markdown(f"**Patologia Primária:** {p_cromo['patologia']}")
                    st.markdown(f"**Estadiamento TNM:** {p_cromo['estadiamento']}")
                    st.markdown(f"**Performance Status (ECOG):** {p_cromo['ecog']}")
                with c2:
                    st.markdown(f"**Etapa do Percurso:** `{p_cromo['etapa_clinica']}`")
                    st.markdown(f"**Médico Assistente:** {p_cromo['medico_prescritor']}")
                    st.markdown(f"**Dias em Espera:** {p_cromo['dias_espera']} dias (SLA: {p_cromo['sla_alvo_dias']} dias)")
                    st.markdown(f"**Complexidade Médica (M):** {p_cromo['complexidade_m'] * 100:.0f}%")
                with c3:
                    st.markdown(f"**Remarcações Anteriores:** {p_cromo['remarcacoes']} ({p_cromo['origem_remarcacao']})")
                    st.markdown(f"**Dias desde Última Remarcação:** {p_cromo['dias_desde_ultima_remarcacao']} dias")
                    st.markdown(f"**Fator R Calculado:** `{p_cromo['r_score']}`")
                    st.markdown(f"### PF Calculada: **{p_cromo['prioridade_final']}%**")
                st.markdown("</div>", unsafe_allow_html=True)

    aptos = [d for d in st.session_state.doentes if d['estado'] == 'pronto_para_marcar']
    aptos = sorted(aptos, key=lambda x: x['prioridade_final'], reverse=True)

    if not aptos:
        st.info("Não existem doentes em fila de espera imediata para agendamento.")
    else:
        col_h1, col_h2, col_h3, col_h4, col_h5, col_h6 = st.columns([0.15, 0.25, 0.15, 0.15, 0.15, 0.15])
        col_h1.markdown("**Prioridade Final**")
        col_h2.markdown("**Doente & Patologia**")
        col_h3.markdown("**Nível / Cor**")
        col_h4.markdown("**Etapa / Espera**")
        col_h5.markdown("**Cromo Digital**")
        col_h6.markdown("**Ação de Agendamento**")
        st.markdown("---")

        for doente in aptos:
            col1, col2, col3, col4, col5, col6 = st.columns([0.15, 0.25, 0.15, 0.15, 0.15, 0.15])
            
            with col1:
                pf = doente['prioridade_final']
                cor_pf = "#b30000" if pf >= 80 else ("#d9534f" if pf >= 65 else "#005a9c")
                st.markdown(f"<span style='font-size:18px; font-weight:700; color:{cor_pf};'>{pf}%</span>", unsafe_allow_html=True)
                st.caption(f"Semáforo: 🟢 Verde")

            with col2:
                st.markdown(f"**{doente['nome']}**")
                st.caption(f"{doente['id']} | {doente['patologia']}")

            with col3:
                st.markdown(render_badge_nivel(doente['nivel'], doente['cor']), unsafe_allow_html=True)
                if doente['remarcacoes'] > 0:
                    st.caption(f"⚠️ Remarcado: {doente['remarcacoes']}x")

            with col4:
                st.write(f"{doente['etapa_clinica']}")
                sla_diff = doente['dias_espera'] - doente['sla_alvo_dias']
                if sla_diff > 0:
                    st.markdown(f"<span style='color:#dc3545; font-weight:600;'>{doente['dias_espera']}d (Excedeu +{sla_diff}d)</span>", unsafe_allow_html=True)
                else:
                    st.caption(f"{doente['dias_espera']}d / SLA {doente['sla_alvo_dias']}d")

            with col5:
                if st.button("🔍 Abrir Cromo", key=f"cromo_{doente['id']}"):
                    st.session_state.cromo_selecionado = doente['id']
                    st.rerun()

            with col6:
                if st.button("📅 Agendar", key=f"marcar_{doente['id']}", type="primary"):
                    doente['estado'] = 'agendado'
                    doente['slot_info'] = f"{datetime.now().strftime('%d/%b')} - Vaga Regulada Central"
                    atualizar_base_dados()
                    st.success(f"Exame/Consulta marcado para {doente['nome']}!")
                    st.rerun()
            st.markdown("<hr style='margin:4px 0 8px 0; border:0; border-top:1px solid #eee;'>", unsafe_allow_html=True)

# ABA 2: ABA PRIORITÁRIA DE PENDÊNCIAS
with aba2:
    st.subheader("⚠️ Aba Prioritária de Pendências Clínico-Administrativas")
    st.markdown("""
    **Regra Institucional**: Processos com pendências documentais (`completo == False`) ou sem rótulo clínico de triagem são retidos preventivamente.
    *A Prioridade Final (PF) NÃO é reduzida*, mantendo a posição justa do doente assim que o bloqueio for resolvido.
    """)

    pendentes = [d for d in st.session_state.doentes if d['semaforo'] == 'Vermelho']
    
    if not pendentes:
        st.success("🎉 Não existem pendências clínicas ou administrativas em aberto. Todos os processos estão conformes!")
    else:
        st.markdown(f"**Total de Casos Bloqueados:** `{len(pendentes)}`")
        
        for p in pendentes:
            with st.expander(f"🔴 {p['id']} - {p['nome']} | Pendência: {p['motivo_pendencia'] or 'Falta Validação de Triagem Médica'}", expanded=True):
                pcol1, pcol2, pcol3 = st.columns([0.4, 0.35, 0.25])
                
                with pcol1:
                    st.markdown(f"**Patologia:** {p['patologia']}")
                    st.markdown(f"**Médico Requisitante:** {p['medico_prescritor']}")
                    st.markdown(f"**Estado Atual:** `{p['estado']}`")
                    st.markdown(f"**Motivo Detalhado:** `{p['motivo_pendencia']}`")
                
                with pcol2:
                    st.markdown(f"**Prioridade Final Congelada:** `{p['prioridade_final']}%`")
                    progresso_sla = min(1.0, p['dias_espera'] / max(1, p['sla_alvo_dias']))
                    st.write(f"**Relógio de SLA:** {p['dias_espera']} dias decorridos de {p['sla_alvo_dias']} dias permitidos")
                    st.progress(progresso_sla)
                    if p['dias_espera'] >= p['sla_alvo_dias']:
                        st.markdown("<span style='color:red; font-weight:bold;'>⚠️ SLA ULTRAPASSADO - RISCO DE PROGRESSÃO</span>", unsafe_allow_html=True)
                
                with pcol3:
                    st.markdown("**Resolução Imediata**")
                    nova_cor = p['cor']
                    if p['cor'] == 'Sem Cor':
                        nova_cor = st.selectbox(
                            "Atribuir Cor de Triagem:",
                            options=['Crítico', 'Muito Alto', 'Alto', 'Moderado', 'Baixo', 'Rotina'],
                            key=f"sel_cor_{p['id']}"
                        )
                    
                    doc_ok = st.checkbox("Documentos / Exames validados", key=f"chk_doc_{p['id']}")
                    
                    if st.button("🔓 Resolver & Desbloquear", key=f"btn_resolve_{p['id']}"):
                        if p['cor'] == 'Sem Cor':
                            p['cor'] = nova_cor
                        p['completo'] = True
                        p['motivo_pendencia'] = ''
                        atualizar_base_dados()
                        st.success(f"Processo de {p['nome']} desbloqueado com sucesso! Entrou na Fila Ativa.")
                        st.rerun()

# ABA 3: REAPROVEITAMENTO DE SLOTS
with aba3:
    st.subheader("🔄 Reaproveitamento Inteligente de Vagas por Desmarcação")
    st.caption("Combate ao desperdício de recursos oncológicos. O sistema sugere automaticamente o Top 3 de doentes aptos com maior Prioridade Final.")

    col_desm1, col_desm2 = st.columns([0.45, 0.55])

    with col_desm1:
        st.markdown("#### 1. Simular Desmarcação / Cancelamento")
        agendados = [d for d in st.session_state.doentes if d['estado'] == 'agendado']
        
        if agendados:
            opcoes_agendados = {f"{d['id']} - {d['nome']} ({d.get('slot_info', 'Slot sem info')})": d['id'] for d in agendados}
            escolha = st.selectbox("Selecione o doente agendado que cancelou/desmarcou:", options=list(opcoes_agendados.keys()))
            motivo_desm = st.selectbox("Origem do Cancelamento:", ["Doente (Imprevisto/Saúde)", "Equipa Clínica / Intercorrência", "Outros/Transporte"])
            
            if st.button("🚨 Registar Desmarcação e Libertar Vaga", type="secondary"):
                id_desm = opcoes_agendados[escolha]
                d_alvo = next(x for x in st.session_state.doentes if x['id'] == id_desm)
                
                nova_vaga = {
                    'id_slot': f"SLOT-{len(st.session_state.slots_vagos) + 1}",
                    'info': d_alvo.get('slot_info', 'Slot Clínico Vago'),
                    'horario': datetime.now().strftime("%d/%m/%Y %H:%M"),
                    'libertado_por': d_alvo['nome']
                }
                st.session_state.slots_vagos.append(nova_vaga)
                
                d_alvo['estado'] = 'pronto_para_marcar'
                d_alvo['remarcacoes'] += 1
                d_alvo['origem_remarcacao'] = 'doente' if 'Doente' in motivo_desm else ('equipa_clinica' if 'Equipa' in motivo_desm else 'outros')
                d_alvo['dias_desde_ultima_remarcacao'] = 0
                d_alvo['slot_info'] = ''
                atualizar_base_dados()
                st.warning(f"Vaga libertada! Doente {d_alvo['nome']} retornou à lista com atualização da taxa R.")
                st.rerun()
        else:
            st.info("Não existem doentes agendados no momento para simular cancelamento.")
            if st.button("➕ Gerar Vaga de Urgência no Sistema"):
                st.session_state.slots_vagos.append({
                    'id_slot': f"SLOT-URG-{len(st.session_state.slots_vagos) + 1}",
                    'info': '25/Set 11:30 - Sala de Exames TAC 1',
                    'horario': datetime.now().strftime("%d/%m/%Y %H:%M"),
                    'libertado_por': 'Adição Manual'
                })
                st.rerun()

    with col_desm2:
        st.markdown("#### 2. Vagas Disponíveis e Matching Clínico")
        if not st.session_state.slots_vagos:
            st.success("Nenhuma vaga por reaproveitar no momento. Todas as janelas de consulta estão preenchidas.")
        else:
            for idx_slot, vaga in enumerate(st.session_state.slots_vagos):
                st.markdown(f"""
                <div style='background-color: #e8f4fd; border: 1px solid #b8daff; border-radius: 6px; padding: 10px; margin-bottom: 8px;'>
                    <strong>🎯 Vaga Vaga:</strong> {vaga['info']} <br>
                    <small>Libertada por: {vaga['libertado_por']} às {vaga['horario']}</small>
                </div>
                """, unsafe_allow_html=True)
                
                elegiveis = [d for d in st.session_state.doentes if d['estado'] == 'pronto_para_marcar']
                elegiveis_ordenados = sorted(elegiveis, key=lambda x: x['prioridade_final'], reverse=True)[:3]
                
                if not elegiveis_ordenados:
                    st.warning("Não há doentes aptos na fila para ocupar este slot.")
                else:
                    st.markdown("**Top 3 Candidatos Recomendados pelo Algoritmo:**")
                    for rank, cand in enumerate(elegiveis_ordenados, start=1):
                        scol1, scol2, scol3 = st.columns([0.15, 0.60, 0.25])
                        scol1.markdown(f"**#{rank} ({cand['prioridade_final']}%)**")
                        scol2.markdown(f"{cand['nome']} | {cand['patologia']} ({cand['cor']})")
                        if scol3.button("⚡ Encaixar Vaga", key=f"encaixe_{vaga['id_slot']}_{cand['id']}"):
                            cand['estado'] = 'agendado'
                            cand['slot_info'] = f"{vaga['info']} (Reaproveitamento de Vaga)"
                            st.session_state.slots_vagos.pop(idx_slot)
                            atualizar_base_dados()
                            st.success(f"Doente {cand['nome']} alocado com sucesso à vaga {vaga['id_slot']}!")
                            st.rerun()
                st.markdown("---")

# ABA 4: DASHBOARD DE GESTÃO & ALERTAS
with aba4:
    st.subheader("📊 Auditoria Clínica & Deteção de Sobretriagem")
    st.caption("Painel de controlo analítico para prevenção da inflação artificial de prioridades ('Gaming' de cores de triagem).")

    df_medicos = []
    for p in st.session_state.doentes:
        df_medicos.append({
            'medico': p['medico_prescritor'],
            'id': p['id'],
            'cor': p['cor'],
            'critico_alto': 1 if p['cor'] in ['Crítico', 'Muito Alto'] else 0
        })
    
    df_m = pd.DataFrame(df_medicos)
    
    resumo_medicos = df_m.groupby('medico').agg(
        total_pedidos=('id', 'count'),
        pedidos_criticos=('critico_alto', 'sum')
    ).reset_index()
    
    resumo_medicos['taxa_inflacao'] = round((resumo_medicos['pedidos_criticos'] / resumo_medicos['total_pedidos']) * 100, 1)
    
    medicos_alerta = resumo_medicos[resumo_medicos['taxa_inflacao'] > 30.0]
    
    if not medicos_alerta.empty:
        st.error("### ⚠️ ALERTA DE AUDITORIA: Suspeita de Inflação de Prioridades Clínicas!")
        st.markdown("Os seguintes médicos prescritores ultrapassaram o teto estatístico aceitável de **30%** de pedidos classificados como `Crítico` ou `Muito Alto`:")
        for _, row in medicos_alerta.iterrows():
            st.markdown(f"- **{row['medico']}**: `{row['taxa_inflacao']}%` de pedidos críticos ({row['pedidos_criticos']} de {row['total_pedidos']} requisições)")
    else:
        st.success("✅ Conformidade total: Nenhum médico apresenta taxas desproporcionais de sobrediagnóstico de urgência.")

    col_dash1, col_dash2 = st.columns(2)
    
    with col_dash1:
        st.markdown("#### Distribuição de Cores por Prescritor (%)")
        st.dataframe(
            resumo_medicos.rename(columns={
                'medico': 'Médico Prescritor',
                'total_pedidos': 'Total Requisições',
                'pedidos_criticos': 'Crítico / Muito Alto',
                'taxa_inflacao': '% Críticos'
            }),
            use_container_width=True
        )

    with col_dash2:
        st.markdown("#### Resumo da Lista Geral por Patologia e Estágio")
        df_geral = pd.DataFrame([{
            'Etapa Clínica': d['etapa_clinica'],
            'Prioridade Média': d['prioridade_final'],
            'Dias Espera Médios': d['dias_espera']
        } for d in st.session_state.doentes])
        
        resumo_etapas = df_geral.groupby('Etapa Clínica').mean().round(1).reset_index()
        st.dataframe(resumo_etapas, use_container_width=True)
        
    st.markdown("---")
    st.markdown("**Distribuição Institucional dos Níveis de Triagem Atuais:**")
    contagem_cores = pd.Series([d['cor'] for d in st.session_state.doentes]).value_counts()
    st.bar_chart(contagem_cores)
