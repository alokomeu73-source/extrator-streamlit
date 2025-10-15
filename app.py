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
        if match := re.search(pattern, text, re.IGNOREC
