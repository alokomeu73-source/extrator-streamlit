import streamlit as st
import pandas as pd
from PIL import Image
import pytesseract
import io
import re
from datetime import datetime
import os

# Importação condicional do PyMuPDF
try:
    import fitz  # PyMuPDF
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False
    st.warning("PyMuPDF não está disponível. PDFs serão convertidos para imagem.")

# Configuração da página
st.set_page_config(
    page_title="Extração de Dados Médicos - OCR",
    page_icon="🏥",
    layout="wide"
)

# Título e descrição
st.title("🏥 Extração de Dados de Guias Médicas")
st.markdown("""
Este aplicativo extrai automaticamente informações de guias médicas usando OCR:
- **Data de atendimento**
- **Número da guia**
- **Número de atendimento**
- **Nome do paciente**
- **Valor da consulta**
""")

# Função para extrair texto de PDF
def extract_text_from_pdf(pdf_file):
    try:
        pdf_bytes = pdf_file.read()
        pdf_document = fitz.open(stream=pdf_bytes, filetype="pdf")
        text = ""
        for page_num in range(pdf_document.page_count):
            page = pdf_document[page_num]
            text += page.get_text()
        pdf_document.close()
        return text
    except Exception as e:
        st.error(f"Erro ao processar PDF: {str(e)}")
        return None

# Função para extrair texto de imagem
def extract_text_from_image(image_file):
    try:
        image = Image.open(image_file)
        text = pytesseract.image_to_string(image, lang='por')
        return text
    except Exception as e:
        st.error(f"Erro ao processar imagem: {str(e)}")
        return None

# Função para extrair informações usando regex
def extract_information(text):
    info = {
        'Data de Atendimento': '',
        'Número da Guia': '',
        'Número de Atendimento': '',
        'Nome do Paciente': '',
        'Valor da Consulta': ''
    }
    
    if not text:
        return info
    
    # Extração de data (formatos: DD/MM/YYYY, DD-MM-YYYY, DD.MM.YYYY)
    date_patterns = [
        r'\b(\d{2}[/-]\d{2}[/-]\d{4})\b',
        r'\b(\d{2}\.\d{2}\.\d{4})\b',
        r'data[:\s]+(\d{2}[/-]\d{2}[/-]\d{4})',
        r'atendimento[:\s]+(\d{2}[/-]\d{2}[/-]\d{4})'
    ]
    for pattern in date_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            info['Data de Atendimento'] = match.group(1)
            break
    
    # Extração de número da guia
    guia_patterns = [
        r'(?:guia|n[úu]mero da guia)[:\s]+(\d+)',
        r'(?:n[°º]|num\.?)\s*guia[:\s]+(\d+)',
        r'guia[:\s]*(\d{6,})'
    ]
    for pattern in guia_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            info['Número da Guia'] = match.group(1)
            break
    
    # Extração de número de atendimento
    atend_patterns = [
        r'(?:atendimento|n[úu]mero de atendimento)[:\s]+(\d+)',
        r'(?:n[°º]|num\.?)\s*atend\.?[:\s]+(\d+)',
        r'atend\.?[:\s]*(\d{6,})'
    ]
    for pattern in atend_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            info['Número de Atendimento'] = match.group(1)
            break
    
    # Extração de nome do paciente
    nome_patterns = [
        r'(?:paciente|nome)[:\s]+([A-ZÀÁÂÃÇÉÊÍÓÔÕÚ][a-zàáâãçéêíóôõú]+(?:\s+[A-ZÀÁÂÃÇÉÊÍÓÔÕÚ][a-zàáâãçéêíóôõú]+)+)',
        r'(?:benefici[áa]rio|titular)[:\s]+([A-ZÀÁÂÃÇÉÊÍÓÔÕÚ][a-zàáâãçéêíóôõú]+(?:\s+[A-ZÀÁÂÃÇÉÊÍÓÔÕÚ][a-zàáâãçéêíóôõú]+)+)'
    ]
    for pattern in nome_patterns:
        match = re.search(pattern, text)
        if match:
            info['Nome do Paciente'] = match.group(1)
            break
    
    # Extração de valor
    valor_patterns = [
        r'(?:valor|total|consulta)[:\s]*R?\$?\s*(\d{1,3}(?:\.\d{3})*(?:,\d{2})?)',
        r'R\$\s*(\d{1,3}(?:\.\d{3})*(?:,\d{2})?)',
        r'(\d{1,3}(?:\.\d{3})*,\d{2})'
    ]
    for pattern in valor_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            info['Valor da Consulta'] = match.group(1)
            break
    
    return info

# Interface de upload
st.sidebar.header("📤 Upload de Arquivos")
uploaded_files = st.sidebar.file_uploader(
    "Selecione PDFs ou Imagens",
    type=['pdf', 'png', 'jpg', 'jpeg'],
    accept_multiple_files=True
)

# Processar arquivos
if uploaded_files:
    st.subheader(f"📊 Processando {len(uploaded_files)} arquivo(s)...")
    
    all_data = []
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for idx, file in enumerate(uploaded_files):
        status_text.text(f"Processando: {file.name}")
        
        # Determinar tipo de arquivo e extrair texto
        if file.name.lower().endswith('.pdf'):
            text = extract_text_from_pdf(file)
        else:
            text = extract_text_from_image(file)
        
        if text:
            # Extrair informações
            info = extract_information(text)
            info['Arquivo'] = file.name
            all_data.append(info)
        
        # Atualizar barra de progresso
        progress_bar.progress((idx + 1) / len(uploaded_files))
    
    status_text.text("✅ Processamento concluído!")
    
    # Criar DataFrame
    if all_data:
        df = pd.DataFrame(all_data)
        
        # Reordenar colunas
        columns_order = ['Arquivo', 'Data de Atendimento', 'Número da Guia', 
                        'Número de Atendimento', 'Nome do Paciente', 'Valor da Consulta']
        df = df[columns_order]
        
        # Mostrar resultados
        st.subheader("📋 Dados Extraídos")
        st.dataframe(df, use_container_width=True)
        
        # Estatísticas
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total de Arquivos", len(df))
        with col2:
            campos_preenchidos = df.apply(lambda x: x.str.strip().ne('').sum()).sum()
            total_campos = len(df) * (len(df.columns) - 1)  # -1 para não contar 'Arquivo'
            st.metric("Taxa de Extração", f"{(campos_preenchidos/total_campos*100):.1f}%")
        with col3:
            if df['Valor da Consulta'].str.strip().ne('').any():
                st.metric("Valores Extraídos", df['Valor da Consulta'].str.strip().ne('').sum())
        
        # Gerar Excel
        st.subheader("💾 Download")
        
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='Dados Extraídos')
            
            # Formatar planilha
            workbook = writer.book
            worksheet = writer.sheets['Dados Extraídos']
            
            # Formato para cabeçalho
            header_format = workbook.add_format({
                'bold': True,
                'bg_color': '#4CAF50',
                'font_color': 'white',
                'border': 1
            })
            
            # Aplicar formato ao cabeçalho
            for col_num, value in enumerate(df.columns.values):
                worksheet.write(0, col_num, value, header_format)
            
            # Ajustar largura das colunas
            for i, col in enumerate(df.columns):
                max_len = max(df[col].astype(str).apply(len).max(), len(col)) + 2
                worksheet.set_column(i, i, max_len)
        
        excel_data = output.getvalue()
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        st.download_button(
            label="📥 Baixar Planilha Excel",
            data=excel_data,
            file_name=f"dados_medicos_{timestamp}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        
        # Opção de edição manual
        st.subheader("✏️ Edição Manual (Opcional)")
        st.info("Você pode copiar e colar os dados abaixo em uma planilha ou editá-los conforme necessário.")
        st.text_area("Dados em CSV", df.to_csv(index=False), height=200)
    else:
        st.warning("Nenhum dado foi extraído dos arquivos.")
else:
    st.info("👈 Faça upload de arquivos PDF ou imagens na barra lateral para começar.")
    
    # Exemplo de uso
    with st.expander("ℹ️ Como usar"):
        st.markdown("""
        1. **Faça upload** de um ou mais arquivos (PDF ou imagens)
        2. **Aguarde** o processamento automático
        3. **Revise** os dados extraídos na tabela
        4. **Baixe** a planilha Excel com os resultados
        
        **Dicas:**
        - Certifique-se de que as imagens têm boa qualidade e resolução
        - PDFs com texto selecionável funcionam melhor
        - O aplicativo busca por palavras-chave comuns em guias médicas
        """)

# Rodapé
st.sidebar.markdown("---")
st.sidebar.markdown("### ℹ️ Sobre")
st.sidebar.info("Aplicativo de OCR para extração automática de dados de guias médicas usando Tesseract e PyMuPDF.")
