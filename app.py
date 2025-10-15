import streamlit as st
import pandas as pd
from PIL import Image
import pytesseract
import io
import re
from datetime import datetime
import os
import sys

# Configurar caminho do Tesseract para diferentes ambientes
if os.path.exists('/usr/bin/tesseract'):
    pytesseract.pytesseract.tesseract_cmd = '/usr/bin/tesseract'
elif os.path.exists('/usr/local/bin/tesseract'):
    pytesseract.pytesseract.tesseract_cmd = '/usr/local/bin/tesseract'

# Importação condicional do PyMuPDF
try:
    import fitz  # PyMuPDF
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False
    st.warning("⚠️ PyMuPDF não está disponível. Instale com: pip install PyMuPDF")

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
- **1 - Registro ANS**
- **2 - Número GUIA**
- **4 - Data de Autorização**
- **10 - Nome**
- **Valor da Consulta**
""")

# Função para extrair texto de PDF (com OCR se necessário)
def extract_text_from_pdf(pdf_file):
    if not PYMUPDF_AVAILABLE:
        st.error("❌ PyMuPDF não está instalado. Instale com: pip install PyMuPDF")
        return None
    
    try:
        # Verificar se Tesseract está disponível para OCR
        tesseract_available = True
        try:
            pytesseract.get_tesseract_version()
        except:
            tesseract_available = False
            st.warning("⚠️ Tesseract não disponível. PDFs escaneados podem não funcionar.")
        
        pdf_bytes = pdf_file.read()
        pdf_document = fitz.open(stream=pdf_bytes, filetype="pdf")
        text = ""
        
        for page_num in range(pdf_document.page_count):
            page = pdf_document[page_num]
            
            # Tentar extrair texto direto
            page_text = page.get_text()
            
            # Se não houver texto ou texto muito curto, fazer OCR da imagem
            if tesseract_available and len(page_text.strip()) < 50:
                # Converter página para imagem
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))  # 2x zoom para melhor qualidade
                img_data = pix.tobytes("png")
                img = Image.open(io.BytesIO(img_data))
                
                # Fazer OCR
                try:
                    page_text = pytesseract.image_to_string(img, lang='por')
                except:
                    pass  # Manter texto original se OCR falhar
            
            text += page_text + "\n"
        
        pdf_document.close()
        return text
    except Exception as e:
        st.error(f"Erro ao processar PDF: {str(e)}")
        return None

# Função para extrair texto de imagem
def extract_text_from_image(image_file):
    try:
        # Verificar se Tesseract está disponível
        try:
            pytesseract.get_tesseract_version()
        except Exception as e:
            st.error("❌ Tesseract OCR não está instalado. Verifique o arquivo packages.txt")
            st.info("""
            **Para executar localmente:**
            - Ubuntu/Debian: `sudo apt-get install tesseract-ocr tesseract-ocr-por`
            - macOS: `brew install tesseract tesseract-lang`
            - Windows: Baixe em https://github.com/UB-Mannheim/tesseract/wiki
            
            **Para Streamlit Cloud:**
            - Certifique-se de que o arquivo `packages.txt` existe com o conteúdo correto
            """)
            return None
        
        image = Image.open(image_file)
        # Configurar OCR com opções para melhor resultado
        custom_config = r'--oem 3 --psm 6'
        text = pytesseract.image_to_string(image, lang='por', config=custom_config)
        return text
    except pytesseract.TesseractNotFoundError:
        st.error("❌ Tesseract não encontrado no sistema")
        return None
    except Exception as e:
        st.error(f"Erro ao processar imagem: {str(e)}")
        return None

# Função para extrair informações usando regex (melhorada)
def extract_information(text):
    info = {
        '1 - Registro ANS': '',
        '2 - Número GUIA': '',
        '4 - Data de Autorização': '',
        '10 - Nome': '',
        'Valor da Consulta': ''
    }
    
    if not text:
        return info
    
    # Normalizar texto
    text_normalized = text.replace('\n', ' ').replace('  ', ' ')
    
    # === EXTRAÇÃO DE REGISTRO ANS ===
    ans_patterns = [
        r'1\s*[-–—]\s*Registro\s+ANS[:\s]*(\d+)',
        r'Registro\s+ANS[:\s]*(\d+)',
        r'ANS[:\s]*[Nn]?[°º]?\s*(\d{5,})',
        r'(?:Operadora|Registro).*?ANS[:\s]*(\d{5,})'
    ]
    for pattern in ans_patterns:
        match = re.search(pattern, text_normalized, re.IGNORECASE)
        if match:
            info['1 - Registro ANS'] = match.group(1)
            break
    
    # === EXTRAÇÃO DE NÚMERO GUIA ===
    guia_patterns = [
        r'2\s*[-–—]\s*N[úu]mero\s+GUIA[:\s]*(\d+[\d\s.\-]*\d+)',
        r'N[úu]mero\s+GUIA[:\s]*(\d+[\d\s.\-]*\d+)',
        r'GUIA[:\s]*[Nn]?[°º]?\s*(\d+[\d\s.\-]*\d+)',
        r'(?:n[úuº°]?\.?\s*(?:da\s+)?guia|guia\s+n[úuº°]?\.?)[:\s]*(\d[\d\s.\-]{5,})',
        r'guia[:\s]*[n°º]?[:\s]*(\d[\d\s.\-]{5,})'
    ]
    for pattern in guia_patterns:
        match = re.search(pattern, text_normalized, re.IGNORECASE)
        if match:
            numero = re.sub(r'[^\d]', '', match.group(1))
            if len(numero) >= 4:
                info['2 - Número GUIA'] = numero
                break
    
    # === EXTRAÇÃO DE DATA DE AUTORIZAÇÃO ===
    data_patterns = [
        r'4\s*[-–—]\s*Data\s+de\s+Autoriza[çc][ãa]o[:\s]*(\d{2}[/.\-]\d{2}[/.\-]\d{4})',
        r'Data\s+de\s+Autoriza[çc][ãa]o[:\s]*(\d{2}[/.\-]\d{2}[/.\-]\d{4})',
        r'Autoriza[çc][ãa]o[:\s]*(\d{2}[/.\-]\d{2}[/.\-]\d{4})',
        r'data.*?autoriza[çc][ãa]o.*?[:\s]?(\d{2}[/.\-]\d{2}[/.\-]\d{4})',
        r'(?:em|realizado.*?em)[:\s]+(\d{2}[/.\-]\d{2}[/.\-]\d{4})',
        r'\b(\d{2}[/.\-]\d{2}[/.\-]\d{4})\b'
    ]
    for pattern in data_patterns:
        match = re.search(pattern, text_normalized, re.IGNORECASE | re.DOTALL)
        if match:
            info['4 - Data de Autorização'] = match.group(1).replace('.', '/').replace('-', '/')
            break
    
    # === EXTRAÇÃO DE NOME (Campo 10) ===
    nome_patterns = [
        r'10\s*[-–—]\s*Nome[:\s]+([A-ZÀÁÂÃÇÉÊÍÓÔÕÚ][A-Za-zàáâãçéêíóôõúÀÁÂÃÇÉÊÍÓÔÕÚ\s]{3,100}?)(?:\s+\d{2}[/.\-]\d{2}|\s+CPF|\s+RG|\s+Carteira|\s+Cart\.|\s+\n|$)',
        r'10\s*[-–—]\s*Nome[:\s]+([A-ZÀÁÂÃÇÉÊÍÓÔÕÚ][^\n\d]{10,80}?)(?=\s*\d|\s*CPF|\s*RG|\n|$)',
        r'Nome[:\s]+([A-ZÀÁÂÃÇÉÊÍÓÔÕÚ][A-Za-zàáâãçéêíóôõúÀÁÂÃÇÉÊÍÓÔÕÚ\s]{10,80}?)(?:\s+CPF|\s+RG|\s+\d{2}[/.\-]|\s+Carteira|\n)',
        r'(?:Benefici[áa]rio|Paciente)[:\s]+([A-ZÀÁÂÃÇÉÊÍÓÔÕÚ][A-Za-zàáâãçéêíóôõúÀÁÂÃÇÉÊÍÓÔÕÚ\s]{10,80}?)(?:\s+CPF|\s+RG|\s+\d{2}[/.\-]|\n)'
    ]
    for pattern in nome_patterns:
        match = re.search(pattern, text_normalized, re.IGNORECASE)
        if match:
            nome = match.group(1).strip()
            # Limpar nome
            nome = re.sub(r'\s{2,}', ' ', nome)
            # Remover caracteres indesejados do final
            nome = re.sub(r'[:\-–—]+$', '', nome).strip()
            if len(nome.split()) >= 2:  # Pelo menos nome e sobrenome
                info['10 - Nome'] = nome
                break


# Interface de upload
st.sidebar.header("📤 Upload de Arquivos")

# Opções de visualização
show_text = st.sidebar.checkbox("Mostrar texto extraído (Debug)", value=False)

uploaded_files = st.sidebar.file_uploader(
    "Selecione PDFs ou Imagens",
    type=['pdf', 'png', 'jpg', 'jpeg'],
    accept_multiple_files=True
)

# Processar arquivos
if uploaded_files:
    st.subheader(f"📊 Processando {len(uploaded_files)} arquivo(s)...")
    
    all_data = []
    all_texts = []
    
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
            all_texts.append({'Arquivo': file.name, 'Texto': text})
            
            # Extrair informações
            info = extract_information(text)
            info['Arquivo'] = file.name
            all_data.append(info)
        
        # Atualizar barra de progresso
        progress_bar.progress((idx + 1) / len(uploaded_files))
    
    status_text.text("✅ Processamento concluído!")
    
    # Mostrar texto extraído se solicitado
    if show_text and all_texts:
        st.subheader("🔍 Texto Extraído (Debug)")
        for item in all_texts:
            with st.expander(f"📄 {item['Arquivo']}"):
                st.text_area("Texto completo", item['Texto'], height=300)
    
    # Criar DataFrame
    if all_data:
        df = pd.DataFrame(all_data)
        
        # Reordenar colunas
        columns_order = ['Arquivo', '1 - Registro ANS', '2 - Número GUIA', 
                        '4 - Data de Autorização', '10 - Nome', 'Valor da Consulta']
        df = df[columns_order]
        
        # Mostrar resultados
        st.subheader("📋 Dados Extraídos")
        
        # Editor de dados
        edited_df = st.data_editor(
            df,
            use_container_width=True,
            num_rows="dynamic"
        )
        
        # Estatísticas
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total de Arquivos", len(edited_df))
        with col2:
            campos_preenchidos = edited_df.apply(lambda x: x.str.strip().ne('').sum()).sum()
            total_campos = len(edited_df) * (len(edited_df.columns) - 1)
            taxa = (campos_preenchidos/total_campos*100) if total_campos > 0 else 0
            st.metric("Taxa de Extração", f"{taxa:.1f}%")
        with col3:
            valores_extraidos = edited_df['Valor da Consulta'].str.strip().ne('').sum()
            st.metric("Valores Extraídos", valores_extraidos)
        
        # Gerar Excel
        st.subheader("💾 Download")
        
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            edited_df.to_excel(writer, index=False, sheet_name='Dados Extraídos')
            
            workbook = writer.book
            worksheet = writer.sheets['Dados Extraídos']
            
            header_format = workbook.add_format({
                'bold': True,
                'bg_color': '#4CAF50',
                'font_color': 'white',
                'border': 1,
                'align': 'center'
            })
            
            for col_num, value in enumerate(edited_df.columns.values):
                worksheet.write(0, col_num, value, header_format)
            
            for i, col in enumerate(edited_df.columns):
                max_len = max(edited_df[col].astype(str).apply(len).max(), len(col)) + 2
                worksheet.set_column(i, i, min(max_len, 50))
        
        excel_data = output.getvalue()
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        st.download_button(
            label="📥 Baixar Planilha Excel",
            data=excel_data,
            file_name=f"dados_medicos_{timestamp}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )
    else:
        st.warning("⚠️ Nenhum dado foi extraído dos arquivos. Ative 'Mostrar texto extraído' para debug.")
else:
    st.info("👈 Faça upload de arquivos PDF ou imagens na barra lateral para começar.")
    
    with st.expander("ℹ️ Como usar"):
        st.markdown("""
        ### 📖 Instruções de Uso
        
        1. **Faça upload** de um ou mais arquivos (PDF ou imagens JPG/PNG)
        2. **Aguarde** o processamento automático com OCR
        3. **Revise e edite** os dados extraídos diretamente na tabela
        4. **Baixe** a planilha Excel formatada
        
        ### 💡 Dicas para Melhor Extração
        
        - ✅ Use imagens com boa resolução (mínimo 300 DPI)
        - ✅ Certifique-se de que o texto está legível
        - ✅ PDFs digitalizados funcionam melhor que PDFs escaneados
        - ✅ Ative "Mostrar texto extraído" para verificar o que foi lido
        - ✅ Você pode editar manualmente os dados na tabela
        
        ### 🔍 Dados Extraídos
        
        O aplicativo busca automaticamente:
        - **1 - Registro ANS**: número de registro da operadora
        - **2 - Número GUIA**: número único da guia
        - **4 - Data de Autorização**: formato DD/MM/AAAA
        - **10 - Nome**: nome completo do beneficiário
        - **Valor**: formatos monetários (R$ 100,00)
        """)

# Rodapé
st.sidebar.markdown("---")
st.sidebar.markdown("### ℹ️ Sobre")
st.sidebar.info("Aplicativo de OCR para extração automática de dados de guias médicas usando Tesseract e PyMuPDF.")
st.sidebar.markdown("**Versão:** 2.0 | **Motor OCR:** Tesseract")
            # Limpar nome
            nome = re.sub(r'\s{2,}', ' ', nome)
                # Remover caracteres indesejados do final
                nome = re.sub(r'[:\-–—]+$', '', nome).strip()
                if len(nome.split()) >= 2:  # Pelo menos nome e sobrenome
                    info['10 - Nome'] = nome
                    break

    
    # === EXTRAÇÃO DE VALOR ===
    valor_patterns = [
        r'(?:valor|total|consulta|procedimento)[:\s]*R?\$?\s*(\d{1,3}(?:\.\d{3})*,\d{2})',
        r'R\$\s*(\d{1,3}(?:\.\d{3})*,\d{2})',
        r'(?:pagar|cobrar)[:\s]*R?\$?\s*(\d{1,3}(?:\.\d{3})*,\d{2})',
        r'\bR\$?\s*(\d+,\d{2})\b'
    ]
    for pattern in valor_patterns:
        match = re.search(pattern, text_normalized, re.IGNORECASE)
        if match:
            info['Valor da Consulta'] = match.group(1)
            break
    
    return info

# Interface de upload
st.sidebar.header("📤 Upload de Arquivos")

# Opções de visualização
show_text = st.sidebar.checkbox("Mostrar texto extraído (Debug)", value=False)

uploaded_files = st.sidebar.file_uploader(
    "Selecione PDFs ou Imagens",
    type=['pdf', 'png', 'jpg', 'jpeg'],
    accept_multiple_files=True
)

# Processar arquivos
if uploaded_files:
    st.subheader(f"📊 Processando {len(uploaded_files)} arquivo(s)...")
    
    all_data = []
    all_texts = []
    
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
            all_texts.append({'Arquivo': file.name, 'Texto': text})
            
            # Extrair informações
            info = extract_information(text)
            info['Arquivo'] = file.name
            all_data.append(info)
        
        # Atualizar barra de progresso
        progress_bar.progress((idx + 1) / len(uploaded_files))
    
    status_text.text("✅ Processamento concluído!")
    
    # Mostrar texto extraído se solicitado
    if show_text and all_texts:
        st.subheader("🔍 Texto Extraído (Debug)")
        for item in all_texts:
            with st.expander(f"📄 {item['Arquivo']}"):
                st.text_area("Texto completo", item['Texto'], height=300)
    
    # Criar DataFrame
    if all_data:
        df = pd.DataFrame(all_data)
        
        # Reordenar colunas
        columns_order = ['Arquivo', 'Data de Atendimento', 'Número da Guia', 
                        'Número de Atendimento', 'Nome do Paciente', 'Valor da Consulta']
        df = df[columns_order]
        
        # Mostrar resultados
        st.subheader("📋 Dados Extraídos")
        
        # Editor de dados
        edited_df = st.data_editor(
            df,
            use_container_width=True,
            num_rows="dynamic"
        )
        
        # Estatísticas
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total de Arquivos", len(edited_df))
        with col2:
            campos_preenchidos = edited_df.apply(lambda x: x.str.strip().ne('').sum()).sum()
            total_campos = len(edited_df) * (len(edited_df.columns) - 1)
            taxa = (campos_preenchidos/total_campos*100) if total_campos > 0 else 0
            st.metric("Taxa de Extração", f"{taxa:.1f}%")
        with col3:
            valores_extraidos = edited_df['Valor da Consulta'].str.strip().ne('').sum()
            st.metric("Valores Extraídos", valores_extraidos)
        
        # Gerar Excel
        st.subheader("💾 Download")
        
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            edited_df.to_excel(writer, index=False, sheet_name='Dados Extraídos')
            
            workbook = writer.book
            worksheet = writer.sheets['Dados Extraídos']
            
            header_format = workbook.add_format({
                'bold': True,
                'bg_color': '#4CAF50',
                'font_color': 'white',
                'border': 1,
                'align': 'center'
            })
            
            for col_num, value in enumerate(edited_df.columns.values):
                worksheet.write(0, col_num, value, header_format)
            
            for i, col in enumerate(edited_df.columns):
                max_len = max(edited_df[col].astype(str).apply(len).max(), len(col)) + 2
                worksheet.set_column(i, i, min(max_len, 50))
        
        excel_data = output.getvalue()
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        st.download_button(
            label="📥 Baixar Planilha Excel",
            data=excel_data,
            file_name=f"dados_medicos_{timestamp}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )
    else:
        st.warning("⚠️ Nenhum dado foi extraído dos arquivos. Ative 'Mostrar texto extraído' para debug.")
else:
    st.info("👈 Faça upload de arquivos PDF ou imagens na barra lateral para começar.")
    
    with st.expander("ℹ️ Como usar"):
        st.markdown("""
        ### 📖 Instruções de Uso
        
        1. **Faça upload** de um ou mais arquivos (PDF ou imagens JPG/PNG)
        2. **Aguarde** o processamento automático com OCR
        3. **Revise e edite** os dados extraídos diretamente na tabela
        4. **Baixe** a planilha Excel formatada
        
        ### 💡 Dicas para Melhor Extração
        
        - ✅ Use imagens com boa resolução (mínimo 300 DPI)
        - ✅ Certifique-se de que o texto está legível
        - ✅ PDFs digitalizados funcionam melhor que PDFs escaneados
        - ✅ Ative "Mostrar texto extraído" para verificar o que foi lido
        - ✅ Você pode editar manualmente os dados na tabela
        
        ### 🔍 Dados Extraídos
        
        O aplicativo busca automaticamente:
        - **Data de atendimento**: formatos DD/MM/AAAA
        - **Número da guia**: sequências numéricas após "guia"
        - **Número de atendimento**: sequências após "atendimento" ou "protocolo"
        - **Nome do paciente**: nome completo após "paciente" ou "beneficiário"
        - **Valor**: formatos monetários (R$ 100,00)
        """)

# Rodapé
st.sidebar.markdown("---")
st.sidebar.markdown("### ℹ️ Sobre")
st.sidebar.info("Aplicativo de OCR para extração automática de dados de guias médicas usando Tesseract e PyMuPDF.")
st.sidebar.markdown("**Versão:** 2.0 | **Motor OCR:** Tesseract")






