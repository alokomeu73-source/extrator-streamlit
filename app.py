import streamlit as st
import pandas as pd
from PIL import Image
import pytesseract
import io
import re
from datetime import datetime
import os

# Configurar caminho do Tesseract
if os.path.exists('/usr/bin/tesseract'):
    pytesseract.pytesseract.tesseract_cmd = '/usr/bin/tesseract'
elif os.path.exists('/usr/local/bin/tesseract'):
    pytesseract.pytesseract.tesseract_cmd = '/usr/local/bin/tesseract'

# Importar PyMuPDF
try:
    import fitz
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False
    st.warning("PyMuPDF não disponível. Apenas imagens serão processadas.")

# ==================== CONFIGURAÇÃO DA PÁGINA ====================
st.set_page_config(
    page_title="Extração de Dados Médicos - OCR",
    page_icon="🏥",
    layout="wide"
)

st.title("🏥 Extração de Dados de Guias Médicas")
st.markdown("""
Extrai automaticamente as seguintes informações de guias médicas:
- **1 - Registro ANS**
- **2 - Número GUIA**
- **4 - Data de Autorização**
- **10 - Nome**
- **Valor da Consulta**
""")

# ==================== FUNÇÕES DE EXTRAÇÃO DE TEXTO ====================

def extract_text_from_pdf(pdf_file):
    """Extrai texto de arquivo PDF usando PyMuPDF e OCR quando necessário"""
    if not PYMUPDF_AVAILABLE:
        st.error("PyMuPDF não está instalado")
        return None
    
    try:
        pdf_bytes = pdf_file.read()
        pdf_document = fitz.open(stream=pdf_bytes, filetype="pdf")
        full_text = ""
        
        for page_num in range(pdf_document.page_count):
            page = pdf_document[page_num]
            page_text = page.get_text()
            
            # Se texto direto for muito curto, fazer OCR
            if len(page_text.strip()) < 50:
                try:
                    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                    img_data = pix.tobytes("png")
                    img = Image.open(io.BytesIO(img_data))
                    page_text = pytesseract.image_to_string(img, lang='por')
                except Exception as e:
                    st.warning(f"OCR falhou na página {page_num + 1}: {str(e)}")
            
            full_text += page_text + "\n"
        
        pdf_document.close()
        return full_text
        
    except Exception as e:
        st.error(f"Erro ao processar PDF: {str(e)}")
        return None


def extract_text_from_image(image_file):
    """Extrai texto de imagem usando Tesseract OCR"""
    try:
        # Verificar se Tesseract está disponível
        try:
            pytesseract.get_tesseract_version()
        except:
            st.error("Tesseract OCR não está instalado. Verifique o arquivo packages.txt")
            return None
        
        image = Image.open(image_file)
        config = r'--oem 3 --psm 6'
        text = pytesseract.image_to_string(image, lang='por', config=config)
        return text
        
    except Exception as e:
        st.error(f"Erro ao processar imagem: {str(e)}")
        return None


# ==================== FUNÇÃO DE EXTRAÇÃO DE DADOS ====================

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
    
    # Normalizar texto
    text = text.replace('\n', ' ')
    text = re.sub(r'\s+', ' ', text)
    
    # ===== REGISTRO ANS =====
    patterns_ans = [
        r'1\s*-\s*Registro\s+ANS[:\s]*(\d+)',
        r'Registro\s+ANS[:\s]*(\d+)',
        r'ANS[:\s]*(\d{6,})',
    ]
    
    for pattern in patterns_ans:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            data['1 - Registro ANS'] = match.group(1)
            break
    
    # ===== NÚMERO GUIA =====
    patterns_guia = [
        r'2\s*-\s*N[uú]mero\s+GUIA[:\s]*(\d+)',
        r'N[uú]mero\s+GUIA[:\s]*(\d+)',
        r'GUIA[:\s]*[Nn°º]?\s*(\d{5,})',
        r'[Gg]uia[:\s]+(\d{5,})',
    ]
    
    for pattern in patterns_guia:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            numero = re.sub(r'\D', '', match.group(1))
            if len(numero) >= 5:
                data['2 - Número GUIA'] = numero
                break
    
    # ===== DATA DE AUTORIZAÇÃO =====
    patterns_data = [
        r'4\s*-\s*Data\s+de\s+Autoriza[cç][aã]o[:\s]*(\d{2}/\d{2}/\d{4})',
        r'Data\s+de\s+Autoriza[cç][aã]o[:\s]*(\d{2}/\d{2}/\d{4})',
        r'Autoriza[cç][aã]o[:\s]*(\d{2}/\d{2}/\d{4})',
        r'(\d{2}/\d{2}/\d{4})',
    ]
    
    for pattern in patterns_data:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            data['4 - Data de Autorização'] = match.group(1)
            break
    
    # ===== NOME =====
    patterns_nome = [
        r'10\s*-\s*Nome[:\s]+([A-Z][A-Za-z\s]+?)(?:\s+\d{2}/|\s+CPF|\s+RG|\s+\d{3}\.)',
        r'10\s*-\s*Nome[:\s]+([A-Z][^\d\n]{10,80}?)(?=\s*\d|\s*CPF)',
        r'Nome[:\s]+([A-Z][A-Za-z\s]{15,80}?)(?:\s+CPF|\s+RG|\s+\d{2}/)',
        r'Benefici[aá]rio[:\s]+([A-Z][A-Za-z\s]{15,80}?)(?:\s+CPF|\s+RG)',
    ]
    
    for pattern in patterns_nome:
        match = re.search(pattern, text)
        if match:
            nome = match.group(1).strip()
            nome = re.sub(r'\s+', ' ', nome)
            nome = re.sub(r'[:\-]+$', '', nome).strip()
            
            palavras = nome.split()
            if len(palavras) >= 2 and all(len(p) > 1 for p in palavras):
                data['10 - Nome'] = nome
                break
    
    # ===== VALOR DA CONSULTA =====
    patterns_valor = [
        r'R\$\s*(\d{1,3}(?:\.\d{3})*,\d{2})',
        r'[Vv]alor[:\s]*R?\$?\s*(\d{1,3}(?:\.\d{3})*,\d{2})',
        r'[Tt]otal[:\s]*R?\$?\s*(\d{1,3}(?:\.\d{3})*,\d{2})',
        r'(\d{1,3}(?:\.\d{3})*,\d{2})',
    ]
    
    for pattern in patterns_valor:
        match = re.search(pattern, text)
        if match:
            data['Valor da Consulta'] = match.group(1)
            break
    
    return data


# ==================== INTERFACE DO USUÁRIO ====================

# Sidebar
st.sidebar.header("📤 Upload de Arquivos")
show_debug = st.sidebar.checkbox("🔍 Mostrar texto extraído (Debug)", value=False)

uploaded_files = st.sidebar.file_uploader(
    "Selecione arquivos PDF ou imagens",
    type=['pdf', 'png', 'jpg', 'jpeg'],
    accept_multiple_files=True,
    help="Arraste e solte seus arquivos aqui"
)

# Processamento principal
if uploaded_files:
    st.subheader(f"📊 Processando {len(uploaded_files)} arquivo(s)...")
    
    results = []
    debug_texts = []
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for idx, file in enumerate(uploaded_files):
        status_text.text(f"Processando: {file.name}")
        
        # Extrair texto
        if file.name.lower().endswith('.pdf'):
            text = extract_text_from_pdf(file)
        else:
            text = extract_text_from_image(file)
        
        if text:
            # Salvar para debug
            debug_texts.append({
                'Arquivo': file.name,
                'Texto': text
            })
            
            # Extrair dados
            extracted_data = extract_medical_data(text)
            extracted_data['Arquivo'] = file.name
            results.append(extracted_data)
        else:
            st.warning(f"Não foi possível extrair texto de {file.name}")
        
        progress_bar.progress((idx + 1) / len(uploaded_files))
    
    status_text.text("✅ Processamento concluído!")
    
    # Mostrar texto extraído se debug ativado
    if show_debug and debug_texts:
        st.subheader("🔍 Texto Extraído (Debug)")
        for item in debug_texts:
            with st.expander(f"📄 {item['Arquivo']}"):
                st.text_area(
                    "Texto completo extraído",
                    item['Texto'],
                    height=300,
                    key=f"debug_{item['Arquivo']}"
                )
    
    # Criar DataFrame
    if results:
        df = pd.DataFrame(results)
        
        # Ordenar colunas
        column_order = [
            'Arquivo',
            '1 - Registro ANS',
            '2 - Número GUIA',
            '4 - Data de Autorização',
            '10 - Nome',
            'Valor da Consulta'
        ]
        df = df[column_order]
        
        # Exibir dados extraídos
        st.subheader("📋 Dados Extraídos")
        
        edited_df = st.data_editor(
            df,
            use_container_width=True,
            num_rows="dynamic",
            key="data_editor"
        )
        
        # Estatísticas
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("📁 Arquivos Processados", len(edited_df))
        
        with col2:
            total_campos = len(edited_df) * 5  # 5 campos principais
            campos_preenchidos = 0
            for col in ['1 - Registro ANS', '2 - Número GUIA', '4 - Data de Autorização', '10 - Nome', 'Valor da Consulta']:
                campos_preenchidos += edited_df[col].astype(str).str.strip().ne('').sum()
            
            taxa = (campos_preenchidos / total_campos * 100) if total_campos > 0 else 0
            st.metric("📊 Taxa de Extração", f"{taxa:.1f}%")
        
        with col3:
            valores_count = edited_df['Valor da Consulta'].astype(str).str.strip().ne('').sum()
            st.metric("💰 Valores Extraídos", valores_count)
        
        # Gerar Excel para download
        st.subheader("💾 Download")
        
        output = io.BytesIO()
        
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            edited_df.to_excel(writer, index=False, sheet_name='Dados Médicos')
            
            workbook = writer.book
            worksheet = writer.sheets['Dados Médicos']
            
            # Formato do cabeçalho
            header_format = workbook.add_format({
                'bold': True,
                'text_wrap': True,
                'valign': 'center',
                'fg_color': '#4CAF50',
                'font_color': '#FFFFFF',
                'border': 1
            })
            
            # Aplicar formato
            for col_num, value in enumerate(edited_df.columns.values):
                worksheet.write(0, col_num, value, header_format)
                
                # Ajustar largura das colunas
                max_length = max(
                    edited_df[value].astype(str).apply(len).max(),
                    len(str(value))
                ) + 2
                worksheet.set_column(col_num, col_num, min(max_length, 50))
        
        excel_data = output.getvalue()
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        st.download_button(
            label="📥 Baixar Planilha Excel",
            data=excel_data,
            file_name=f"guias_medicas_{timestamp}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )
        
        # CSV alternativo
        csv = edited_df.to_csv(index=False).encode('utf-8-sig')
        st.download_button(
            label="📄 Baixar CSV",
            data=csv,
            file_name=f"guias_medicas_{timestamp}.csv",
            mime="text/csv",
            use_container_width=True
        )
    
    else:
        st.warning("⚠️ Nenhum dado foi extraído. Verifique os arquivos e tente novamente.")

else:
    # Tela inicial
    st.info("👈 **Faça upload de arquivos na barra lateral para começar**")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 📖 Como Usar")
        st.markdown("""
        1. **Faça upload** de PDFs ou imagens (JPG/PNG)
        2. **Aguarde** o processamento automático
        3. **Revise** e edite os dados na tabela
        4. **Baixe** a planilha Excel
        
        💡 **Dica:** Ative o modo debug para ver o texto extraído
        """)
    
    with col2:
        st.markdown("### ⚙️ Requisitos")
        st.markdown("""
        **Para melhor resultado:**
        - ✅ Imagens com resolução mínima de 300 DPI
        - ✅ Texto legível e bem contrastado
        - ✅ PDFs nativos (não escaneados) funcionam melhor
        - ✅ Arquivos individuais (uma guia por arquivo)
        """)

# Rodapé
st.sidebar.markdown("---")
st.sidebar.markdown("### ℹ️ Informações")
st.sidebar.info("""
**Versão:** 3.0  
**OCR Engine:** Tesseract  
**PDF Engine:** PyMuPDF  

Extrai automaticamente dados de guias médicas usando reconhecimento óptico de caracteres (OCR).
""")

# Instruções de instalação
with st.sidebar.expander("📦 Instalação Local"):
    st.code("""
# Ubuntu/Debian
sudo apt-get install tesseract-ocr tesseract-ocr-por
pip install -r requirements.txt

# macOS
brew install tesseract tesseract-lang
pip install -r requirements.txt

# Executar
streamlit run app.py
    """, language="bash")
