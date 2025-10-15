import streamlit as st
import pandas as pd
import re
import io
from PIL import Image
import numpy as np
import fitz  # PyMuPDF
from datetime import datetime

# Configuração da página
st.set_page_config(
    page_title="Extrator de Guias Médicas",
    page_icon="🏥",
    layout="wide"
)

# Variável global para armazenar o reader
if 'ocr_reader' not in st.session_state:
    st.session_state.ocr_reader = None
    st.session_state.ocr_loaded = False


@st.cache_resource
def load_easyocr():
    """Carrega o modelo EasyOCR apenas uma vez e mantém em cache"""
    import easyocr
    reader = easyocr.Reader(['pt'], gpu=False, verbose=False)
    return reader


def extract_text_from_image(image):
    """Extrai texto de uma imagem usando EasyOCR"""
    if st.session_state.ocr_reader is None:
        with st.spinner("🔄 Carregando modelo OCR pela primeira vez... (isso pode levar alguns segundos)"):
            st.session_state.ocr_reader = load_easyocr()
            st.session_state.ocr_loaded = True
    
    # Converte PIL Image para numpy array
    img_array = np.array(image)
    
    # Executa OCR
    results = st.session_state.ocr_reader.readtext(img_array)
    
    # Concatena todos os textos extraídos
    text = ' '.join([result[1] for result in results])
    return text


def extract_text_from_pdf(pdf_file):
    """Extrai texto de um arquivo PDF usando PyMuPDF e OCR"""
    pdf_bytes = pdf_file.read()
    pdf_document = fitz.open(stream=pdf_bytes, filetype="pdf")
    
    full_text = ""
    total_pages = len(pdf_document)
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for page_num in range(total_pages):
        status_text.text(f"Processando página {page_num + 1} de {total_pages}...")
        
        page = pdf_document[page_num]
        
        # Tenta extrair texto direto primeiro
        page_text = page.get_text()
        
        # Se não houver texto, usa OCR
        if not page_text.strip():
            # Converte página para imagem com zoom 2x
            mat = fitz.Matrix(2, 2)
            pix = page.get_pixmap(matrix=mat)
            img_data = pix.tobytes("png")
            img = Image.open(io.BytesIO(img_data))
            page_text = extract_text_from_image(img)
        
        full_text += page_text + "\n"
        progress_bar.progress((page_num + 1) / total_pages)
    
    pdf_document.close()
    progress_bar.empty()
    status_text.empty()
    
    return full_text


def extract_fields_from_text(text, filename):
    """Extrai os campos específicos usando RegEx"""
    
    # Remove quebras de linha e espaços extras para facilitar matching
    text_clean = ' '.join(text.split())
    
    # Dicionário para armazenar os campos extraídos
    data = {
        'Arquivo': filename,
        '1 - Registro ANS': '',
        '2 - Número GUIA': '',
        '4 - Data de Autorização': '',
        '10 - Nome': ''
    }
    
    # RegEx para Registro ANS (vários formatos possíveis)
    ans_patterns = [
        r'(?:Registro\s+ANS|ANS)[:\s]*([0-9]{5,7})',
        r'(?:1\s*[-.\s]*Registro\s+ANS)[:\s]*([0-9]{5,7})',
        r'(?:^|\s)([0-9]{6})(?:\s|$)',  # 6 dígitos isolados
    ]
    for pattern in ans_patterns:
        match = re.search(pattern, text_clean, re.IGNORECASE)
        if match:
            data['1 - Registro ANS'] = match.group(1).strip()
            break
    
    # RegEx para Número da GUIA (vários formatos)
    guia_patterns = [
        r'(?:N[úu]mero\s+(?:da\s+)?GUIA|GUIA)[:\s]*([0-9]{10,20})',
        r'(?:2\s*[-.\s]*N[úu]mero\s+GUIA)[:\s]*([0-9]{10,20})',
        r'(?:N[°º]\s*Guia)[:\s]*([0-9]{10,20})',
        r'(?:GUIA\s*N[°º]?)[:\s]*([0-9]{10,20})',
    ]
    for pattern in guia_patterns:
        match = re.search(pattern, text_clean, re.IGNORECASE)
        if match:
            data['2 - Número GUIA'] = match.group(1).strip()
            break
    
    # RegEx para Data de Autorização (formato DD/MM/YYYY ou DD-MM-YYYY)
    data_patterns = [
        r'(?:Data\s+(?:de\s+)?Autoriza[çc][ãa]o)[:\s]*([0-3]?[0-9][/-][0-1]?[0-9][/-][0-9]{4})',
        r'(?:4\s*[-.\s]*Data\s+(?:de\s+)?Autoriza[çc][ãa]o)[:\s]*([0-3]?[0-9][/-][0-1]?[0-9][/-][0-9]{4})',
        r'(?:Autoriza[çc][ãa]o)[:\s]*([0-3]?[0-9][/-][0-1]?[0-9][/-][0-9]{4})',
    ]
    for pattern in data_patterns:
        match = re.search(pattern, text_clean, re.IGNORECASE)
        if match:
            data['4 - Data de Autorização'] = match.group(1).strip().replace('-', '/')
            break
    
    # RegEx para Nome (campo 10)
    nome_patterns = [
        r'(?:10\s*[-.\s]*Nome)[:\s]*([A-ZÀÁÂÃÄÅÇÈÉÊËÌÍÎÏÑÒÓÔÕÖÙÚÛÜ\s]{3,50})',
        r'(?:Nome\s+(?:do\s+)?(?:Benefici[áa]rio|Paciente))[:\s]*([A-ZÀÁÂÃÄÅÇÈÉÊËÌÍÎÏÑÒÓÔÕÖÙÚÛÜ\s]{3,50})',
        r'(?:Benefici[áa]rio)[:\s]*([A-ZÀÁÂÃÄÅÇÈÉÊËÌÍÎÏÑÒÓÔÕÖÙÚÛÜ\s]{3,50})',
    ]
    for pattern in nome_patterns:
        match = re.search(pattern, text_clean, re.IGNORECASE)
        if match:
            nome_raw = match.group(1).strip()
            # Remove números e caracteres especiais do nome
            nome_clean = re.sub(r'[0-9\-/:]', '', nome_raw).strip()
            data['10 - Nome'] = nome_clean
            break
    
    return data


def process_image_file(image_file):
    """Processa um arquivo de imagem"""
    img = Image.open(image_file)
    
    # Converte para RGB se necessário
    if img.mode != 'RGB':
        img = img.convert('RGB')
    
    with st.spinner(f"🔍 Extraindo texto de {image_file.name}..."):
        text = extract_text_from_image(img)
    
    return extract_fields_from_text(text, image_file.name)


def process_pdf_file(pdf_file):
    """Processa um arquivo PDF"""
    with st.spinner(f"📄 Processando PDF {pdf_file.name}..."):
        text = extract_text_from_pdf(pdf_file)
    
    return extract_fields_from_text(text, pdf_file.name)


def convert_df_to_excel(df):
    """Converte DataFrame para arquivo Excel em bytes"""
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Guias Médicas')
    output.seek(0)
    return output


# Interface do Streamlit
st.title("🏥 Extrator de Dados de Guias Médicas")
st.markdown("""
Este aplicativo extrai automaticamente informações de guias médicas em formato **PDF** ou **Imagem**.

**Campos extraídos:**
- 1 - Registro ANS
- 2 - Número GUIA  
- 4 - Data de Autorização
- 10 - Nome
""")

st.divider()

# Upload de arquivos
uploaded_files = st.file_uploader(
    "📤 Faça upload das guias médicas (PDF ou Imagem)",
    type=['pdf', 'png', 'jpg', 'jpeg'],
    accept_multiple_files=True,
    help="Você pode selecionar múltiplos arquivos de uma vez"
)

if uploaded_files:
    st.success(f"✅ {len(uploaded_files)} arquivo(s) carregado(s)")
    
    if st.button("🚀 Processar Arquivos", type="primary", use_container_width=True):
        results = []
        
        # Processa cada arquivo
        for idx, file in enumerate(uploaded_files):
            st.write(f"**Processando {idx + 1}/{len(uploaded_files)}: {file.name}**")
            
            try:
                if file.type == "application/pdf":
                    data = process_pdf_file(file)
                else:
                    data = process_image_file(file)
                
                results.append(data)
                st.success(f"✓ {file.name} processado com sucesso!")
                
            except Exception as e:
                st.error(f"❌ Erro ao processar {file.name}: {str(e)}")
                # Adiciona linha vazia em caso de erro
                results.append({
                    'Arquivo': file.name,
                    '1 - Registro ANS': 'ERRO',
                    '2 - Número GUIA': 'ERRO',
                    '4 - Data de Autorização': 'ERRO',
                    '10 - Nome': 'ERRO'
                })
        
        # Cria DataFrame
        if results:
            df = pd.DataFrame(results)
            st.session_state.df_results = df
            st.success("🎉 Processamento concluído!")

# Exibe e permite edição dos resultados
if 'df_results' in st.session_state:
    st.divider()
    st.subheader("📊 Resultados Extraídos")
    st.info("💡 Você pode editar os dados na tabela abaixo antes de fazer o download")
    
    # Editor de dados
    edited_df = st.data_editor(
        st.session_state.df_results,
        use_container_width=True,
        num_rows="dynamic",
        column_config={
            "Arquivo": st.column_config.TextColumn("Arquivo", width="medium"),
            "1 - Registro ANS": st.column_config.TextColumn("Registro ANS", width="small"),
            "2 - Número GUIA": st.column_config.TextColumn("Número GUIA", width="medium"),
            "4 - Data de Autorização": st.column_config.TextColumn("Data Autorização", width="small"),
            "10 - Nome": st.column_config.TextColumn("Nome", width="large"),
        }
    )
    
    # Botão de download
    st.divider()
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        excel_file = convert_df_to_excel(edited_df)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        st.download_button(
            label="📥 Download Excel (XLSX)",
            data=excel_file,
            file_name=f"guias_medicas_{timestamp}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
            type="primary"
        )
    
    # Estatísticas
    st.divider()
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total de Guias", len(edited_df))
    with col2:
        ans_preenchidos = edited_df['1 - Registro ANS'].astype(str).str.strip().ne('').sum()
        st.metric("ANS Extraídos", ans_preenchidos)
    with col3:
        guia_preenchidos = edited_df['2 - Número GUIA'].astype(str).str.strip().ne('').sum()
        st.metric("GUIA Extraídos", guia_preenchidos)
    with col4:
        nome_preenchidos = edited_df['10 - Nome'].astype(str).str.strip().ne('').sum()
        st.metric("Nomes Extraídos", nome_preenchidos)

# Rodapé
st.divider()
st.caption("🔒 Os arquivos são processados localmente e não são armazenados no servidor")
