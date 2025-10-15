# app.py
import streamlit as st
import pandas as pd
from PIL import Image, ImageEnhance, ImageFilter # Inclui as classes de melhoria de imagem
import pytesseract
import io
import re
from datetime import datetime
import os

# --- Configuração de Caminho do Tesseract (Necessário para Ambientes Linux/Streamlit Cloud) ---
# Tenta configurar o caminho, que deve ser /usr/bin/tesseract no ambiente padrão do Streamlit Cloud
if os.path.exists('/usr/bin/tesseract'):
    pytesseract.pytesseract.tesseract_cmd = '/usr/bin/tesseract'
elif os.path.exists('/usr/local/bin/tesseract'):
    pytesseract.pytesseract.tesseract_cmd = '/usr/local/bin/tesseract'

# --- Importar PyMuPDF (fitz) para PDFs ---
try:
    import fitz
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False
    st.warning("PyMuPDF não está instalado. Apenas imagens serão processadas.")

# ==================== CONFIGURAÇÃO DA PÁGINA ====================
st.set_page_config(
    page_title="Extração de Dados Médicos - OCR",
    page_icon="🏥",
    layout="wide"
)

st.title("🏥 Extração de Dados de Guias Médicas (OCR Avançado)")
st.markdown("""
Esta ferramenta utiliza OCR e pré-processamento de imagem para extrair com alta precisão as informações
das Guias: **Registro ANS**, **Número GUIA**, **Data de Autorização**, **Nome do Paciente** e **Valor da Consulta**.
""")

# ==================== FUNÇÕES DE EXTRAÇÃO DE TEXTO ====================

def apply_image_enhancements(img):
    """Aplica melhorias de contraste e nitidez na imagem para otimizar o OCR."""
    
    # Conversão para RGB se necessário
    if img.mode != 'RGB':
        img = img.convert('RGB')
        
    # Aumentar contraste
    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(2)
    
    # Melhorar nitidez
    img = img.filter(ImageFilter.SHARPEN)
    
    return img

def extract_text_from_pdf(pdf_file):
    """Extrai texto de PDF, usando OCR apenas se o texto nativo for escasso (PDF escaneado)."""
    if not PYMUPDF_AVAILABLE:
        return None
    
    try:
        pdf_bytes = pdf_file.read()
        pdf_document = fitz.open(stream=pdf_bytes, filetype="pdf")
        full_text = ""
        custom_config = r'--oem 3 --psm 6 -c preserve_interword_spaces=1'
        
        for page_num in range(pdf_document.page_count):
            page = pdf_document[page_num]
            page_text = page.get_text()
            
            # Condição para tentar OCR (se o texto nativo for muito curto)
            if len(page_text.strip()) < 50:
                try:
                    # Aumentar resolução (zoom 3x)
                    zoom = 3
                    mat = fitz.Matrix(zoom, zoom)
                    pix = page.get_pixmap(matrix=mat)
                    img_data = pix.tobytes("png")
                    
                    img = Image.open(io.BytesIO(img_data))
                    img = apply_image_enhancements(img)
                    
                    page_text = pytesseract.image_to_string(img, lang='por', config=custom_config)
                except Exception as e:
                    st.warning(f"OCR falhou na página {page_num + 1} de {pdf_file.name}: {str(e)}")
            
            full_text += page_text + "\n"
            
        pdf_document.close()
        return full_text
            
    except Exception as e:
        st.error(f"Erro crítico ao processar PDF {pdf_file.name}: {str(e)}")
        return None


def extract_text_from_image(image_file):
    """Extrai texto de imagem usando Tesseract OCR com pré-processamento."""
    try:
        # Tesseract check
        try:
            pytesseract.get_tesseract_version()
        except Exception:
            st.error("Tesseract OCR não está disponível. Verifique o arquivo packages.txt")
            return None
        
        image = Image.open(image_file)
        
        # Otimização de redimensionamento para imagens de baixa qualidade
        width, height = image.size
        if width < 2000:
            scale = 2000 / width
            new_size = (int(width * scale), int(height * scale))
            image = image.resize(new_size, Image.LANCZOS)
        
        # Aplicar pré-processamento
        image = apply
