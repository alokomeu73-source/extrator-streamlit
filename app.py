import streamlit as st
import pandas as pd
import fitz  # PyMuPDF
import easyocr
import numpy as np
from PIL import Image
import io
import re
from datetime import datetime

# Configuração da página
st.set_page_config(
    page_title="Extrator de Guias Médicas",
    page_icon="📋",
    layout="wide"
)

# Função para carregar o modelo EasyOCR (com cache)
@st.cache_resource
def load_ocr_model():
    """Carrega o modelo EasyOCR uma única vez"""
    return easyocr.Reader(['pt'], gpu=False)

# Função para extrair campos usando RegEx
def extract_fields(text):
    """Extrai os 4 campos obrigatórios do texto usando RegEx"""
    fields = {
        'Registro ANS': '',
        'Número GUIA': '',
        'Data de Autorização': '',
        'Nome': ''
    }
    
    # 1 - Registro ANS (sequência numérica, geralmente 6 dígitos)
    ans_pattern = r'(?:1\s*[-\s]*)?(?:Registro\s*ANS|ANS)[:\s]*(\d{6,})'
    ans_match = re.search(ans_pattern, text, re.IGNORECASE)
    if ans_match:
        fields['Registro ANS'] = ans_match.group(1)
    
    # 2 - Número GUIA (alfanumérico)
    guia_pattern = r'(?:2\s*[-\s]*)?(?:N[úu]mero|N[°º]|Numero)\s*(?:da\s*)?(?:GUIA|Guia)[:\s]*([A-Z0-9\-]+)'
    guia_match = re.search(guia_pattern, text, re.IGNORECASE)
    if guia_match:
        fields['Número GUIA'] = guia_match.group(1)
    
    # 4 - Data de Autorização (formatos: DD/MM/YYYY, DD-MM-YYYY, DD.MM.YYYY)
    data_pattern = r'(?:4\s*[-\s]*)?(?:Data\s*(?:de\s*)?Autoriza[çc][ãa]o)[:\s]*(\d{2}[/\-\.]\d{2}[/\-\.]\d{4})'
    data_match = re.search(data_pattern, text, re.IGNORECASE)
    if data_match:
        fields['Data de Autorização'] = data_match.group(1)
    
    # 10 - Nome (captura texto após "Nome" até quebra de linha ou próximo campo)
    nome_pattern = r'(?:10\s*[-\s]*)?(?:Nome)[:\s]*([A-ZÀÁÂÃÈÉÊÌÍÒÓÔÕÙÚÇ][A-Za-zÀ-ÿ\s]+?)(?:\n|\d+\s*[-\s]|$)'
    nome_match = re.search(nome_pattern, text, re.IGNORECASE)
    if nome_match:
        fields['Nome'] = nome_match.group(1).strip()
    
    return fields

# Função para processar imagem com EasyOCR
def process_image_ocr(image, reader):
    """Processa uma imagem PIL e retorna o texto extraído"""
    # Converter PIL Image para numpy array
    img_array = np.array(image)
    
    # Realizar OCR
    results = reader.readtext(img_array)
    
    # Concatenar todo o texto
    text = ' '.join([result[1] for result in results])
    return text

# Função para processar PDF
def process_pdf(pdf_file, reader):
    """Processa um arquivo PDF e extrai dados de cada página"""
    extracted_data = []
    
    # Abrir o PDF
    pdf_document = fitz.open(stream=pdf_file.read(), filetype="pdf")
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    total_pages = len(pdf_document)
    
    for page_num in range(total_pages):
        status_text.text(f"Processando página {page_num + 1} de {total_pages}...")
        
        # Carregar a página
        page = pdf_document[page_num]
        
        # Converter página para imagem (zoom 2x para melhor qualidade)
        mat = fitz.Matrix(2, 2)
        pix = page.get_pixmap(matrix=mat)
        
        # Converter para PIL Image
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        
        # Realizar OCR
        text = process_image_ocr(img, reader)
        
        # Extrair campos
        fields = extract_fields(text)
        fields['Página'] = page_num + 1
        fields['Arquivo'] = pdf_file.name
        
        extracted_data.append(fields)
        
        # Atualizar barra de progresso
        progress_bar.progress((page_num + 1) / total_pages)
    
    pdf_document.close()
    status_text.empty()
    progress_bar.empty()
    
    return extracted_data

# Função para processar imagem única
def process_single_image(image_file, reader):
    """Processa um arquivo de imagem único"""
    # Abrir imagem
    image = Image.open(image_file)
    
    # Realizar OCR
    text = process_image_ocr(image, reader)
    
    # Extrair campos
    fields = extract_fields(text)
    fields['Página'] = 1
    fields['Arquivo'] = image_file.name
    
    return [fields]

# Interface principal
def main():
    st.title("📋 Extrator de Guias Médicas")
    st.markdown("### Extraia dados de guias médicas em PDF ou Imagem")
    
    st.info("ℹ️ **Formato suportado:** PDF, PNG, JPG, JPEG")
    
    # Upload de arquivos
    uploaded_files = st.file_uploader(
        "Envie um ou mais arquivos",
        type=['pdf', 'png', 'jpg', 'jpeg'],
        accept_multiple_files=True
    )
    
    if uploaded_files:
        # Inicializar o modelo OCR APENAS após o upload
        with st.spinner("🔄 Carregando modelo OCR (primeira execução pode levar alguns minutos)..."):
            reader = load_ocr_model()
        
        st.success("✅ Modelo OCR carregado!")
        
        if st.button("🚀 Processar Arquivos", type="primary"):
            all_data = []
            
            for uploaded_file in uploaded_files:
                st.subheader(f"📄 Processando: {uploaded_file.name}")
                
                try:
                    # Verificar tipo de arquivo
                    if uploaded_file.type == "application/pdf":
                        data = process_pdf(uploaded_file, reader)
                    else:
                        data = process_single_image(uploaded_file, reader)
                    
                    all_data.extend(data)
                    st.success(f"✅ {uploaded_file.name} processado com sucesso!")
                    
                except Exception as e:
                    st.error(f"❌ Erro ao processar {uploaded_file.name}: {str(e)}")
            
            if all_data:
                # Criar DataFrame
                df = pd.DataFrame(all_data)
                
                # Reordenar colunas
                columns_order = ['Arquivo', 'Página', 'Registro ANS', 'Número GUIA', 
                               'Data de Autorização', 'Nome']
                df = df[columns_order]
                
                st.success(f"🎉 Total de {len(df)} registro(s) extraído(s)!")
                
                # Editor de dados
                st.subheader("✏️ Edite os dados extraídos (se necessário)")
                edited_df = st.data_editor(
                    df,
                    num_rows="dynamic",
                    use_container_width=True,
                    hide_index=True
                )
                
                # Preparar download
                st.subheader("💾 Download")
                
                # Converter para Excel
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    edited_df.to_excel(writer, index=False, sheet_name='Guias Médicas')
                
                excel_data = output.getvalue()
                
                # Botão de download
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                st.download_button(
                    label="📥 Baixar planilha XLSX",
                    data=excel_data,
                    file_name=f"guias_medicas_{timestamp}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
    else:
        st.warning("⚠️ Faça upload de pelo menos um arquivo para começar")
    
    # Rodapé com instruções
    with st.expander("ℹ️ Instruções de Uso"):
        st.markdown("""
        **Como usar:**
        1. Faça upload de um ou mais arquivos (PDF ou Imagem)
        2. Clique em "Processar Arquivos"
        3. Aguarde o processamento (pode levar alguns minutos)
        4. Edite os dados extraídos se necessário
        5. Baixe a planilha XLSX
        
        **Campos extraídos:**
        - Registro ANS
        - Número GUIA
        - Data de Autorização
        - Nome
        
        **Observações:**
        - O modelo OCR é carregado apenas na primeira execução
        - PDFs são processados página por página
        - A qualidade da extração depende da qualidade da imagem/PDF
        """)

if __name__ == "__main__":
    main()
