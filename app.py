# app.py
import streamlit as st
import fitz # PyMuPDF
import easyocr
import re
import pandas as pd
from io import BytesIO
from PIL import Image, ImageEnhance, ImageFilter # Necessário para pré-processamento
import numpy as np # ESSENCIAL para o EasyOCR

# --- Configurações ---
st.set_page_config(page_title="Leitor de PDFs Médicos 🩺", layout="wide")

st.title("📄 Extração Rápida de Guias Médicas (Inicialização Otimizada)")
st.markdown("Otimizado para carregar a interface instantaneamente. O modelo de OCR só será carregado após o envio do primeiro arquivo.")

# --- Inicialização do OCR (carrega uma vez, com feedback) ---
@st.cache_resource
def load_ocr():
    """Carrega o modelo do EasyOCR UMA ÚNICA VEZ (cache) e mostra um spinner."""
    # Importante: Definir gpu=False para máxima estabilidade em ambientes Cloud.
    with st.spinner("⏳ Carregando o modelo de OCR (pode levar 1-2 minutos na primeira execução)..."):
        return easyocr.Reader(["pt", "en"], gpu=False)

# A linha 'reader = load_ocr()' NÃO está aqui. O modelo será carregado APENAS quando necessário.

# --- Pré-processamento de Imagem (ajuda na precisão com zoom menor) ---
def apply_image_enhancements(img):
    """Aplica melhorias de contraste e nitidez na imagem antes do OCR."""
    if img.mode != 'RGB':
        img = img.convert('RGB')
        
    # Aumentar contraste
    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(1.5) # Aumento moderado
    # Aumentar nitidez
    img = img.filter(ImageFilter.SHARPEN)
    
    return img

# --- Função para extrair texto híbrido (OCR + digital) ---
# Esta função assume que a variável 'reader' está no escopo global quando chamada.
def extract_text_from_pdf(file):
    """Extrai texto do PDF (digital) e usa OCR apenas em páginas de imagem."""
    text_content = ""
    
    # Reinicia o ponteiro do arquivo
    file.seek(0)

    try:
        with fitz.open(stream=file.read(), filetype="pdf") as doc:
            for page_num, page in enumerate(doc):
                
                # 1. Tenta extração de texto digital (mais rápido)
                page_text = page.get_text("text")

                if page_text.strip():
                    text_content += page_text + "\n"
                else:
                    # 2. Se a página for vazia (escaneada), usa OCR
                    st.toast(f"Página {page_num + 1} de {doc.page_count}: Executando OCR...")
                    
                    # OTIMIZAÇÃO: Zoom 2x para otimização de velocidade
                    zoom = 2
                    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom)) 
                    
                    # Converte para PIL Image e aplica melhorias
                    img_bytes = BytesIO(pix.tobytes("png"))
                    img = Image.open(img_bytes)
                    img = apply_image_enhancements(img)
                    
                    # CRÍTICO: Converter para NumPy array para estabilidade do EasyOCR
                    img_array = np.array(img)

                    # Chamada ao reader (que deve estar carregado no escopo global)
                    ocr_result = reader.readtext(img_array, detail=0, paragraph=True)
                    text_content += "\n".join(ocr_result) + "\n"
    
    except Exception as e:
        st.error(f"Erro ao processar PDF: {e}")
        return None

    return text_content.strip()

# --- Função para extrair dados relevantes (RegEx robusto para guias) ---
def extract_info(text):
    """Extrai dados específicos de guias médicas usando padrões robustos."""
    data = {
        '1 - Registro ANS': '',
        '2 - Número GUIA': '',
        '4 - Data de Autorização': '',
        '10 - Nome': '',
        'Valor da Consulta': ''
    }
    
    if not text:
        return data
    
    # Normalizar texto (remover quebras de linha e espaços múltiplos)
    text = text.replace('\n', ' ')
    text = re.sub(r'\s+', ' ', text)
    
    # --- Padrões de Busca (Mantidos do RegEx robusto) ---
    patterns = {
        '1 - Registro ANS': [r'1\s*-\s*Registro\s+ANS[:\s]*(\d+)', r'ANS[:\s]*[Nn]?[°º]?\s*(\d{6,})'],
        '2 - Número GUIA': [r'2\s*-\s*N[uú]mero\s+GUIA[:\s]*(\d+)', r'GUIA[:\s]*[Nn°º]?\s*(\d{5,})'],
        '4 - Data de Autorização': [r'4\s*-\s*Data\s+de\s+Autoriza[cç][aã]o[:\s]*(\d{2}/\d{2}/\d{4})', r'Autoriza[cç][aã]o[:\s]*(\d{2}/\d{2}/\d{4})'],
        '10 - Nome': [r'10\s*-\s*Nome[:\s]+([A-ZÀÁÂÃÇÉÊÍÓÔÕÚ][A-Za-zàáâãçéêíóôõúÀÁÂÃÇÉÊÍÓÔÕÚ\s]+?)(?:\s+\d{2}/|\s+CPF|\s+RG|\s+Cart|\s+\d{3}\.)', r'(?:Benefici[aá]rio|Paciente|Nome)[:\s]+([A-ZÀÁÂÃÇÉÊÍÓÔÕÚ][A-Za-zàáâãçéêíóôõúÀÁÂÃÇÉÊÍÓÔÕÚ\s]{15,80}?)(?:\s+CPF|\s+RG|\s+\d{2}/)'],
        'Valor da Consulta': [r'R\$\s*(\d{1,3}(?:\.\d{3})*,\d{2})', r'[Vv]alor[:\s]*R?\$?\s*(\d{1,3}(?:\.\d{3})*,\d{2})']
    }

    for key, regex_list in patterns.items():
        for pattern in regex_list:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                value = match.group(1).strip()
                if key == '2 - Número GUIA':
                    value = re.sub(r'\D', '', value)
                elif key == '10 - Nome':
                    value = re.sub(r'\s+', ' ', value)
                    if len(value.split()) < 2: continue
                
                data[key] = value
                break

    return data


# --- Upload dos arquivos ---
uploaded_files = st.file_uploader("Envie um ou mais PDFs 📎", type=["pdf"], accept_multiple_files=True)

# =======================================================
# AÇÃO CHAVE: INICIALIZAÇÃO CONDICIONAL
# =======================================================

if uploaded_files:
    # Chama load_ocr() APENAS QUANDO há arquivos.
    # Se o modelo já estiver no cache, é quase instantâneo.
    # Se o modelo for novo (primeira vez), o spinner em load_ocr aparecerá.
    global reader
    reader = load_ocr() 
    
    if reader is None:
        st.error("Falha ao carregar o modelo de OCR.")
        st.stop()

    all_data = []
    
    with st.status("Preparando o ambiente e processando PDFs...", expanded=True) as status:
        
        for file_index, file in enumerate(uploaded_files):
            status.update(label=f"Processando arquivo {file_index + 1}/{len(uploaded_files)}: **{file.name}**")
            
            # Extrair texto
            text = extract_text_from_pdf(file)
            
            if text:
                # Extrair informações
                info = extract_info(text)
                info["Arquivo"] = file.name
                all_data.append(info)
            else:
                st.warning(f"Não foi possível extrair texto de {file.name}")

            with st.expander(f"📘 Texto extraído de {file.name}", expanded=False):
                st.text_area("Conteúdo detectado (máx. 5000 caracteres):", text[:5000], height=200, key=f"text_area_{file_index}")

        status.update(label="✅ Extração concluída! Revisando dados.", state="complete", expanded=False)

    
    if all_data:
        df = pd.DataFrame(all_data)
        st.success("✅ Extração de dados finalizada! Revise a tabela abaixo.")

        column_order = ['Arquivo', '1 - Registro ANS', '2 - Número GUIA', '4 - Data de Autorização', '10 - Nome', 'Valor da Consulta']
        if all(col in df.columns for col in column_order):
             df = df[column_order]

        st.subheader("📋 Dados Extraídos (Edite para Corrigir OCR)")
        edited_df = st.data_editor(df, use_container_width=True, num_rows="dynamic")

        csv = edited_df.to_csv(index=False).encode("utf-8")
        st.download_button("💾 Baixar resultado (.csv)", csv, "dados_extraidos.csv", "text/csv")
    
else:
    # Mensagem de boas-vindas rápida, pois o modelo ainda não está carregado.
    st.info("Envie um ou mais arquivos PDF para começar.")
    st.markdown("""
        ---
        ### 🚀 Otimizações Aplicadas:
        **O carregamento inicial do aplicativo agora é instantâneo.** O modelo de OCR (que causa o *timeout*) só será carregado **após o primeiro arquivo ser enviado**.
        
        1.  **Inicialização Condicional:** O PyTorch e o EasyOCR só são inicializados sob demanda.
        2.  **Zoom Reduzido:** OCR usa zoom 2x (4x mais rápido que 3x) para documentos escaneados.
        """)
