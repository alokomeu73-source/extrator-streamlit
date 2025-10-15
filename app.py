import streamlit as st
import pandas as pd
import io
import re
import numpy as np
from datetime import datetime
from PIL import Image

# ==================== IMPORTAR EASYOCR E PYMUPDF ====================
import easyocr
import fitz  # PyMuPDF

# ==================== CONFIGURAÇÃO DA PÁGINA ====================
st.set_page_config(
    page_title="Extração de Dados Médicos - OCR",
    page_icon="🏥",
    layout="wide"
)

st.title("🏥 Extração de Dados de Guias Médicas")

st.success("✅ EasyOCR disponível e configurado corretamente")

st.markdown("""
Extrai automaticamente as seguintes informações de guias médicas:
- **1 - Registro ANS**
- **2 - Número GUIA**
- **4 - Data de Autorização**
- **10 - Nome**
- **Valor da Consulta**
""")

# ==================== INICIALIZAR EASYOCR ====================
@st.cache_resource
def load_ocr_reader():
    """Carrega o leitor EasyOCR (cacheado para não recarregar várias vezes)."""
    with st.spinner('🔄 Carregando EasyOCR pela primeira vez... Isso pode levar alguns minutos.'):
        return easyocr.Reader(['pt'], gpu=False, verbose=False)

reader = load_ocr_reader()

# ==================== FUNÇÕES DE EXTRAÇÃO ====================
def extract_text_from_pdf(pdf_file):
    """Extrai texto de arquivo PDF usando PyMuPDF e EasyOCR"""
    try:
        pdf_bytes = pdf_file.read()
        pdf_document = fitz.open(stream=pdf_bytes, filetype="pdf")
        full_text = ""

        for page_num in range(pdf_document.page_count):
            page = pdf_document[page_num]
            zoom = 2
            mat = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat)
            img_data = pix.tobytes("png")

            img = Image.open(io.BytesIO(img_data))
            img_array = np.array(img)

            result = reader.readtext(img_array, paragraph=True)
            for detection in result:
                text = detection[1]
                full_text += text + " "

            full_text += "\n"

        pdf_document.close()
        return full_text

    except Exception as e:
        st.error(f"Erro ao processar PDF: {str(e)}")
        return None


def extract_text_from_image(image_file):
    """Extrai texto de imagem usando EasyOCR"""
    try:
        img = Image.open(image_file)
        img_array = np.array(img)
        result = reader.readtext(img_array, paragraph=True)
        full_text = " ".join([d[1] for d in result])
        return full_text
    except Exception as e:
        st.error(f"Erro ao processar imagem: {str(e)}")
        return None

# ==================== EXTRAÇÃO DE DADOS ====================
def extract_medical_data(text):
    """Extrai dados específicos do texto da guia médica"""
    data = {
        '1 - Registro ANS': '',
        '2 - Número GUIA': '',
        '4 - Data de Autorização': '',
        '10 - Nome': '',
        'Valor da Consulta': ''
    }

    if not text:
        return data

    text = text.replace('\n', ' ')
    text = re.sub(r'\s+', ' ', text)

    # Registro ANS
    patterns_ans = [
        r'Registro\s*ANS[:\s]*(\d{6,})',
        r'ANS[:\s]*(\d{6,})',
        r'Operadora.*?ANS.*?(\d{6,})'
    ]
    for pattern in patterns_ans:
        if match := re.search(pattern, text, re.IGNORECASE):
            data['1 - Registro ANS'] = match.group(1)
            break

    # Número GUIA
    patterns_guia = [
        r'N[uúü]mero\s*(?:da\s+)?GUIA[:\s]*(\d+)',
        r'GUIA[:\s]*[Nn°º]?\s*(\d{6,})'
    ]
    for pattern in patterns_guia:
        if match := re.search(pattern, text, re.IGNORECASE):
            numero = re.sub(r'\D', '', match.group(1))
            if len(numero) >= 6:
                data['2 - Número GUIA'] = numero
                break

    # Data de Autorização
    patterns_data = [
        r'Data\s+de\s+Autoriza[cç][aã]o[:\s]*(\d{2}[/\-\.]\d{2}[/\-\.]\d{4})',
        r'(\d{2}[/\-\.]\d{2}[/\-\.]\d{4})'
    ]
    for pattern in patterns_data:
        if match := re.search(pattern, text, re.IGNORECASE):
            data['4 - Data de Autorização'] = match.group(1).replace('-', '/').replace('.', '/')
            break

    # Nome
    patterns_nome = [
        r'Nome[:\s]+([A-ZÀ-Ú][A-Za-zÀ-ú\s]{5,100}?)(?=\s*(?:CPF|RG|CNS|Cart|Nasc))',
        r'Paciente[:\s]+([A-ZÀ-Ú][A-Za-zÀ-ú\s]{5,100})'
    ]
    for pattern in patterns_nome:
        if match := re.search(pattern, text):
            nome = re.sub(r'\s+', ' ', match.group(1)).strip()
            if len(nome.split()) >= 2:
                data['10 - Nome'] = nome
                break

    # Valor
    patterns_valor = [
        r'R\$\s*(\d{1,3}(?:\.\d{3})*,\d{2})',
        r'[Vv]alor[:\s]*R?\$?\s*(\d{1,3}(?:\.\d{3})*,\d{2})'
    ]
    for pattern in patterns_valor:
        if match := re.search(pattern, text):
            data['Valor da Consulta'] = match.group(1)
            break

    return data

# ==================== INTERFACE STREAMLIT ====================
st.sidebar.header("📤 Upload de Arquivos")
show_debug = st.sidebar.checkbox("🔍 Mostrar texto extraído (Debug)", value=False)

uploaded_files = st.sidebar.file_uploader(
    "Selecione arquivos PDF ou imagens",
    type=['pdf', 'png', 'jpg', 'jpeg'],
    accept_multiple_files=True
)

if uploaded_files:
    st.subheader(f"📊 Processando {len(uploaded_files)} arquivo(s)...")

    results = []
    debug_texts = []

    progress_bar = st.progress(0)
    status_text = st.empty()

    for idx, file in enumerate(uploaded_files):
        status_text.text(f"Processando: {file.name}")

        if file.name.lower().endswith('.pdf'):
            text = extract_text_from_pdf(file)
        else:
            text = extract_text_from_image(file)

        if text:
            debug_texts.append({'Arquivo': file.name, 'Texto': text})
            extracted_data = extract_medical_data(text)
            extracted_data['Arquivo'] = file.name
            results.append(extracted_data)
        else:
            st.warning(f"Não foi possível extrair texto de {file.name}")

        progress_bar.progress((idx + 1) / len(uploaded_files))

    status_text.text("✅ Processamento concluído!")

    if show_debug:
        st.subheader("🔍 Texto Extraído (Debug)")
        for item in debug_texts:
            with st.expander(f"📄 {item['Arquivo']}"):
                st.text_area("Texto completo extraído pelo EasyOCR", item['Texto'], height=300)

    if results:
        df = pd.DataFrame(results)
        col_order = ['Arquivo', '1 - Registro ANS', '2 - Número GUIA', '4 - Data de Autorização', '10 - Nome', 'Valor da Consulta']
        df = df[col_order]

        st.subheader("📋 Dados Extraídos")
        edited_df = st.data_editor(df, use_container_width=True, num_rows="dynamic")

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("📁 Arquivos Processados", len(edited_df))
        with col2:
            total = len(edited_df) * 5
            preenchidos = sum(edited_df[c].astype(str).str.strip().ne('').sum() for c in col_order[1:])
            taxa = (preenchidos / total * 100) if total > 0 else 0
            st.metric("📊 Taxa de Extração", f"{taxa:.1f}%")
        with col3:
            valores = edited_df['Valor da Consulta'].astype(str).str.strip().ne('').sum()
            st.metric("💰 Valores Extraídos", valores)

        st.subheader("💾 Download dos Resultados")
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            edited_df.to_excel(writer, index=False, sheet_name='Dados Médicos')
        excel_data = output.getvalue()
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        st.download_button(
            "📥 Baixar Planilha Excel",
            excel_data,
            file_name=f"guias_medicas_{ts}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )

        csv_data = edited_df.to_csv(index=False).encode('utf-8-sig')
        st.download_button(
            "📄 Baixar CSV",
            csv_data,
            file_name=f"guias_medicas_{ts}.csv",
            mime="text/csv",
            use_container_width=True
        )
    else:
        st.warning("⚠️ Nenhum dado foi extraído.")
else:
    st.info("👈 Faça upload de arquivos na barra lateral para começar.")
