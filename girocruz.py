import pandas as pd
import streamlit as st
import plotly.express as px
import pygsheets
import os
from google.oauth2 import service_account

st.set_page_config(layout="wide")

@st.cache_data(ttl=5)
def carregar_v5(): # Mudei o nome aqui
    escopos = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]

    info_dict = {
        "type": st.secrets["controle"]["type"],
        "project_id": st.secrets["controle"]["project_id"],
        "private_key_id": st.secrets["controle"]["private_key_id"],
        # O .replace abaixo é essencial para converter os \n de texto em quebras de linha reais
        "private_key": st.secrets["controle"]["private_key"].replace("\\n", "\n"),
        "client_email": st.secrets["controle"]["client_email"],
        "client_id": st.secrets["controle"]["client_id"],
        "auth_uri": st.secrets["controle"]["auth_uri"],
        "token_uri": st.secrets["controle"]["token_uri"],
        "auth_provider_x509_cert_url": st.secrets["controle"]["auth_provider_x509_cert_url"],
        "client_x509_cert_url": st.secrets["controle"]["client_x509_cert_url"],
        "universe_domain": st.secrets.get("controle", {}).get("universe_domain", "googleapis.com")
    }

    creds = service_account.Credentials.from_service_account_info(info_dict, scopes=escopos)
    client = pygsheets.client.Client(creds)

    sheet_id = "1ZDjG_6rmGTImx2cs_0Fsf0V6TO1AJhqrMeS2GczkXAw"
    
    try:
        arquivo = client.open_by_key(sheet_id)
        aba = arquivo.worksheet_by_title("Base_Cruz")
        return aba.get_as_df()
    except Exception as e:
        st.error(f"Erro ao acessar a planilha: {e}")
        return None

# ATENÇÃO: Lá embaixo no seu código, onde você chama a função, mude para:
df = carregar_v5()
df = df.loc[:, df.columns != ''] 
df = df.loc[:, ~df.columns.duplicated()]


df.columns = df.columns.str.strip()
df = df.dropna(subset=["GV", "Tipo Giro Mensal", "Setor"])
opcao_gv = sorted([x for x in df["GV"].dropna().unique() if x != "#N/A"])
opcao_giro = sorted(df["Tipo Giro Mensal"].unique())
colunas_remover = "Unnamed|INICIO DO MÊS|HOJE|INICIO DO MÊS - HOJE"
df_filtrado = df.loc[:, ~df.columns.str.contains(colunas_remover)]

# parte com o streamlit

st.title("Análise de Giro")
gv_fil = st.sidebar.selectbox("GV:", opcao_gv)
giro_fil = st.sidebar.multiselect("Tipo de Giro:", options=opcao_giro)
df_filtrado = df_filtrado[(df_filtrado["GV"] == gv_fil) & (df_filtrado["Tipo Giro Mensal"].isin(giro_fil))]

# visualizando as metas
meta_fixa = 30
inicio_mes = df["INICIO DO MÊS - HOJE"].iloc[0]
df["Quantidade"] = pd.to_numeric(df["Quantidade"], errors="coerce")
df["Quantidade"] = df["Quantidade"].fillna(0)
df["Tipo Giro Mensal"] = df["Tipo Giro Mensal"].astype(str).str.strip()
soma_ok = df.loc[df["Tipo Giro Mensal"] == "OK", "Quantidade"].sum()
soma_quant = df["Quantidade"].sum()
resultado_parcial = (soma_ok / soma_quant * 100) if soma_quant > 0 else 0
tendencia = (resultado_parcial/inicio_mes)*31
delta_parcial =  meta_fixa - resultado_parcial
delta_tend=  tendencia - meta_fixa

col1, col2, col3 = st.columns(3)
with col1:
    st.metric(label="Meta", value=f"{meta_fixa: .2f}%")
with col2:
    st.metric(label="Resultado Parcial", value=f"{resultado_parcial: .2f}%", delta=f"{resultado_parcial: .2f}%")
with col3:
    st.metric(label="Tendência", value=f"{tendencia: .2f}%", delta=f"{delta_tend: .2f}%")
st.divider()

st.subheader(f"Detalhamento por GV: {gv_fil}")
df_filtrado.columns = [str(c).strip().upper() for c in df_filtrado.columns]
colunas_alvo = ["CLIENTE", "NOME FANTASIA", "SETOR", "TIPO DE VASILHAME", "CAIXAS COMODATAS","GV", "COMPROU", "FALTA COMPRAR", "META", "TENDÊNCIA"]
df_exibir = df_filtrado[[c for c in colunas_alvo if c in df_filtrado.columns]].copy()
col_real = next((c for c in df_exibir.columns if "TENDEN" in c), None)

df_graf = df_filtrado.copy()
df_graf["META"] = pd.to_numeric(df_graf["META"].astype(str).str.replace(",", "."), errors="coerce").fillna(0)
def definir_cor(status):
    status = str(status).upper().strip()
    if status == "BATE":
        return "BATEU A META"
    elif status == "ABAIXO":
      return "ABAIXO DA META"
    else:
        return "-"
    
df_graf["Status_Visual"] = df_graf["TENDÊNCIA"].apply(definir_cor)
fig = px.bar(df_graf, y="NOME FANTASIA", x="META", color="Status_Visual", orientation="h", title="Meta por Cliente (Colorido por Status de Tendência)", color_discrete_map={"BATEU A META": "#00C853",
        "ABAIXO DA META": "#FF5252",  
        "Pendente / Outros": "#B0BEC5"}, labels={"META": "Valor da Meta", "Status_Visual": "Tendência"})
fig.update_layout(yaxis={'categoryorder':'total ascending'}, height=600)

st.plotly_chart(fig, use_container_width=True)
st.table(df_exibir)
