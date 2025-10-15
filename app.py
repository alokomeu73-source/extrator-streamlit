# app.py
import streamlit as st
import fitz # PyMuPDF
import easyocr
import re
import pandas as pd
from io import BytesIO
from PIL import Image, ImageEnhance, ImageFilter
import numpy as np

# --- Requisito: Adicione 'openpyxl' ao seu requirements.txt ---
# import openpyxl # Necessário para download XLSX

# --- Configurações ---
st.set_page_config(page_title="Leitor de PDFs e Imagens Médicos 🩺", layout="wide")

st.title("📄 Extração Universal de Guias Médicas")
st.markdown("Extrai dados de **PDFs** (escaneados ou digitais) e **Imagens** (`.jpg`, `.png`).")

# --- Inicialização do OCR (carrega uma vez, com feedback) ---
@st.cache_resource
def load_ocr():
    """Carrega o modelo do EasyOCR UMA ÚNICA VEZ (cache) e mostra um spinner."""
    # Importante: Definir gpu=False para máxima estabilidade em ambientes Cloud.
    with st.spinner("⏳ Carregando o modelo de OCR (pode levar 1-2 minutos na primeira execução)..."):
        return easyocr.Reader(["pt", "en"], gpu=False)

# --- Pré-processamento de Imagem (ajuda na precisão com zoom menor) ---
def apply_image_enhancements(img):
    """Aplica melhorias de contraste e nitidez na imagem antes do OCR."""
    if img.mode != 'RGB':
        img = img.convert('RGB')
        
    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(1.5)
    img = img.filter(ImageFilter.SHARPEN)
    
    return img

# --- Função para extrair texto de Imagem (Novo) ---
def extract_text_from_image(file, reader):
    """Extrai texto de um arquivo de imagem diretamente usando OCR."""
    try:
        # A PIL já consegue abrir o BytesIO do arquivo de upload do Streamlit
        img = Image.open(file)
        img = apply_image_enhancements(img)
        
        # Converte para NumPy array
        img_array = np.array(img)
        
        ocr_result = reader.readtext(img_array, detail=0, paragraph=True)
        return "\n".join(ocr_result).strip()
    except Exception as e:
        st.error(f"Erro ao processar imagem: {e}")
        return None

# --- Função para extrair texto híbrido de PDF (Adaptado) ---
def extract_text_from_pdf(file, reader):
    """Extrai texto do PDF (digital) e usa OCR apenas em páginas de imagem."""
    text_content = ""
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
                    
                    zoom = 2
                    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom)) 
                    
                    img_bytes = BytesIO(pix.tobytes("png"))
                    img = Image.open(img_bytes)
                    img = apply_image_enhancements(img)
                    
                    # CRÍTICO: Converter para NumPy array para estabilidade do EasyOCR
                    img_array = np.array(img)

                    ocr_result = reader.readtext(img_array, detail=0, paragraph=True)
                    text_content += "\n".join(ocr_result) + "\n"
    
    except Exception as e:
        # st.error(f"Erro ao processar PDF: {e}") # Evita erro de Streamlit na extração
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
    
    # Processamento e padrões RegEx (inalterado)
    text = text.replace('\n', ' ')
    text = re.sub(r'\s+', ' ', text)
    
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


# --- Função para download XLSX ---
@st.cache_data
def convert_df_to_xlsx(df):
    """Converte o DataFrame para um objeto BytesIO XLSX."""
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Dados Extraídos')
    return output.getvalue()


# --- Upload dos arquivos (Aceitando PDF e Imagens) ---
uploaded_files = st.file_uploader(
    "Envie PDFs (.pdf) ou Imagens (.png, .jpg) 📎", 
    type=["pdf", "png", "jpg", "jpeg"], 
    accept_multiple_files=True
)

if uploaded_files:
    # 1. CARREGA O MODELO DE OCR
    reader = load_ocr() 
    
    if reader is None:
        st.error("Falha ao carregar o modelo de OCR.")
        st.stop()

    all_data = []
    file_contents = {} 
    
    # 2. EXECUTA O PROCESSAMENTO NO BLOCO ST.STATUS
    with st.status("Preparando o ambiente e processando arquivos...", expanded=True) as status:
        
        for file_index, file in enumerate(uploaded_files):
            status.update(label=f"Processando arquivo {file_index + 1}/{len(uploaded_files)}: **{file.name}**")
            
            # Decide se usa o extrator de PDF ou de Imagem
            mime_type = file.type
            
            if 'pdf' in mime_type:
                text = extract_text_from_pdf(file, reader)
            elif 'image' in mime_type or file.name.lower().endswith(('.png', '.jpg', '.jpeg')):
                text = extract_text_from_image(file, reader)
            else:
                st.warning(f"Tipo de arquivo não suportado: {file.name}")
                continue
            
            if text:
                file_contents[file.name] = text 
                info = extract_info(text)
                info["Arquivo"] = file.name
                all_data.append(info)
            else:
                st.warning(f"Não foi possível extrair texto de {file.name}")

        status.update(label="✅ Extração concluída! Revisando dados.", state="complete", expanded=False)

    
    # 3. EXIBE OS RESULTADOS E O DOWNLOAD XLSX
    if all_data:
        df = pd.DataFrame(all_data)
        st.success("✅ Extração de dados finalizada! Revise a tabela abaixo.")

        # --- Exibe o Expander Agora (fora do st.status) ---
        st.subheader("Conteúdo Extraído por Arquivo")
        for filename, text in file_contents.items():
             with st.expander(f"📘 Texto extraído de {filename}", expanded=False):
                st.text_area("Conteúdo detectado:", text[:5000], height=200, key=f"text_area_{filename}")
        
        # --- Exibe a Tabela ---
        column_order = ['Arquivo', '1 - Registro ANS', '2 - Número GUIA', '4 - Data de Autorização', '10 - Nome', 'Valor da Consulta']
        if all(col in df.columns for col in column_order):
             df = df[column_order]

        st.subheader("📋 Tabela de Dados (Edite para Corrigir OCR)")
        edited_df = st.data_editor(df, use_container_width=True, num_rows="dynamic")

        # --- DOWNLOAD XLSX (Excel) ---
        xlsx_data = convert_df_to_xlsx(edited_df)
        st.download_button(
            "💾 Baixar resultado (.xlsx)", 
            xlsx_data, 
            "dados_extraidos.xlsx", 
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    
else:
    st.info("Envie um ou mais arquivos (PDF ou Imagem) para começar.")
    st.markdown("---")
