import streamlit as st
import fitz  # PyMuPDF
import easyocr
import re
import pandas as pd
from io import BytesIO

# --- Configurações ---
st.set_page_config(page_title="Leitor de PDFs Médicos 🩺", layout="wide")

st.title("📄 Leitor Inteligente de PDFs Médicos")
st.write("Extraia informações automaticamente de PDFs — escaneados ou digitais.")

# --- Inicialização do OCR (carrega uma vez) ---
@st.cache_resource
def load_ocr():
    return easyocr.Reader(["pt", "en"])

reader = load_ocr()

# --- Função para extrair texto híbrido (OCR + digital) ---
def extract_text_from_pdf(file):
    text_content = ""

    with fitz.open(stream=file.read(), filetype="pdf") as doc:
        for page_num, page in enumerate(doc):
            page_text = page.get_text("text")

            if page_text.strip():
                text_content += page_text + "\n"
            else:
                # Se a página for uma imagem, usa OCR
                pix = page.get_pixmap(matrix=fitz.Matrix(3, 3))  # Zoom 3x para melhor qualidade
                img_bytes = BytesIO(pix.tobytes("png"))
                ocr_result = reader.readtext(img_bytes.getvalue(), detail=0)
                text_content += "\n".join(ocr_result) + "\n"

    return text_content.strip()

# --- Função para extrair dados relevantes ---
def extract_info(text):
    data = {}

    # Padrões comuns (ajustáveis)
    patterns = {
        "Nome do Paciente": r"(?i)(?:nome\s*[:\-]?\s*)([A-ZÁÉÍÓÚÂÊÔÃÕÇ][A-Za-zÁÉÍÓÚÂÊÔÃÕÇ\s]+)",
        "Data": r"(?i)(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4})",
        "Procedimento": r"(?i)(?:procedimento\s*[:\-]?\s*)([A-Za-zÁÉÍÓÚÂÊÔÃÕÇ\s]+)",
        "Médico": r"(?i)(?:médico\s*[:\-]?\s*)([A-Za-zÁÉÍÓÚÂÊÔÃÕÇ\s]+)",
        "CRM": r"(?i)\bCRM[:\-]?\s*([A-Z]{0,2}\s*\d{3,6})\b"
    }

    for key, pattern in patterns.items():
        match = re.search(pattern, text)
        data[key] = match.group(1).strip() if match else ""

    return data

# --- Upload dos arquivos ---
uploaded_files = st.file_uploader("Envie um ou mais PDFs 📎", type=["pdf"], accept_multiple_files=True)

if uploaded_files:
    all_data = []
    for file in uploaded_files:
        with st.spinner(f"Processando {file.name}..."):
            text = extract_text_from_pdf(file)
            info = extract_info(text)
            info["Arquivo"] = file.name
            all_data.append(info)

            with st.expander(f"📘 Texto extraído de {file.name}"):
                st.text_area("Conteúdo detectado:", text[:5000], height=200)

    df = pd.DataFrame(all_data)
    st.success("✅ Extração concluída!")

    st.dataframe(df)

    # Download CSV
    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button("💾 Baixar resultado (.csv)", csv, "dados_extraidos.csv", "text/csv")

else:
    st.info("Envie um ou mais arquivos PDF para começar.")
