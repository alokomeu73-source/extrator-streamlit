# app.py
import streamlit as st
import pandas as pd
from PIL import Image, ImageEnhance, ImageFilter
import io
import re
from datetime import datetime
import numpy as np # Necessário para a conversão de imagem para array

# --- Importar EasyOCR e PyTorch (necessários) ---
import easyocr

# --- Importar PyMuPDF (fitz) para PDFs ---
try:
    import fitz
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False
    
# ==================== CONFIGURAÇÃO DA PÁGINA ====================
st.set_page_config(
    page_title="Extração de Dados Médicos - OCR",
    page_icon="🏥",
    layout="wide"
)

st.title("🏥 Extração de Dados de Guias Médicas (EasyOCR)")
st.markdown("""
Esta ferramenta utiliza **EasyOCR** e pré-processamento de imagem para extrair as informações
das Guias: **Registro ANS**, **Número GUIA**, **Data de Autorização**, **Nome do Paciente** e **Valor da Consulta**.
""")

# ==================== INICIALIZAÇÃO E CACHE DO EASYOCR READER ====================

@st.cache_resource
def load_easyocr_reader():
    """Carrega o modelo do EasyOCR para o idioma Português (pt)."""
    try:
        # Usamos gpu=False para garantir compatibilidade e estabilidade no Streamlit Cloud
        reader = easyocr.Reader(['pt'], gpu=False)
        return reader
    except Exception as e:
        st.error(f"Erro Crítico ao carregar o EasyOCR: {e}. Verifique se o PyTorch (torch) está instalado corretamente.")
        return None

# Carrega o leitor (caching garante que isso só ocorra uma vez)
reader = load_easyocr_reader()

# ==================== FUNÇÕES DE EXTRAÇÃO DE TEXTO ====================

def apply_image_enhancements(img):
    """Aplica melhorias de contraste e nitidez na imagem para otimizar o OCR."""
    if img.mode != 'RGB':
        img = img.convert('RGB')
        
    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(2)
    img = img.filter(ImageFilter.SHARPEN)
    
    return img

def run_easyocr(image):
    """
    Executa o EasyOCR na imagem fornecida (após conversão para NumPy array) 
    e retorna o texto unido.
    """
    if reader is None:
        return ""

    try:
        # CORREÇÃO: Converter a imagem PIL (Pillow) para um NumPy array, que é o formato
        # esperado pelo EasyOCR, evitando o erro "Invalid input type".
        img_array = np.array(image)
        
        # readtext retorna apenas o texto, eliminando caixas delimitadoras e confiança
        results = reader.readtext(img_array, detail=0) 
        
        # Juntar todo o texto extraído em uma única string
        full_text = " ".join(results)
        return full_text
    except Exception as e:
        st.error(f"EasyOCR falhou durante a execução: {str(e)}")
        return ""

def extract_text_from_pdf(pdf_file):
    """Extrai texto de PDF nativo ou usa EasyOCR se for escaneado."""
    if not PYMUPDF_AVAILABLE:
        st.error("PyMuPDF não está instalado para processar PDFs.")
        return None
    
    try:
        pdf_bytes = pdf_file.read()
        pdf_document = fitz.open(stream=pdf_bytes, filetype="pdf")
        full_text = ""
        
        for page_num in range(pdf_document.page_count):
            page = pdf_document[page_num]
            page_text = page.get_text()
            
            # Condição para tentar OCR (se o texto nativo for muito curto)
            if len(page_text.strip()) < 50:
                try:
                    # Aumentar resolução (zoom 3x) para melhor OCR
                    zoom = 3
                    mat = fitz.Matrix(zoom, zoom)
                    pix = page.get_pixmap(matrix=mat)
                    img_data = pix.tobytes("png")
                    
                    img = Image.open(io.BytesIO(img_data))
                    img = apply_image_enhancements(img)
                    
                    # Usar EasyOCR
                    page_text = run_easyocr(img)
                except Exception as e:
                    st.warning(f"OCR (EasyOCR) falhou na página {page_num + 1} de {pdf_file.name}: {str(e)}")
            
            full_text += page_text + "\n"
            
        pdf_document.close()
        return full_text
            
    except Exception as e:
        st.error(f"Erro crítico ao processar PDF {pdf_file.name}: {str(e)}")
        return None


def extract_text_from_image(image_file):
    """Extrai texto de imagem usando EasyOCR com pré-processamento."""
    if reader is None:
        return None
    
    try:
        image = Image.open(image_file)
        
        # Aplicar pré-processamento (melhora a qualidade antes do OCR)
        image = apply_image_enhancements(image)
        
        # Executar EasyOCR
        text = run_easyocr(image)
        
        return text
            
    except Exception as e:
        st.error(f"Erro ao processar imagem {image_file.name}: {str(e)}")
        return None


# ==================== FUNÇÃO DE EXTRAÇÃO DE DADOS (REGEX) ====================

def extract_medical_data(text):
    """Extrai dados específicos do texto da guia médica usando múltiplos padrões (Regex)."""
    
    data = {
        '1 - Registro ANS': '',
        '2 - Número GUIA': '',
        '4 - Data de Autorização': '',
        '10 - Nome': '',
        'Valor da Consulta': ''
    }
    
    if not text:
        return data
    
    # Normalizar texto (remover quebras de linha e espaços múltiplos)
    text = text.replace('\n', ' ')
    text = re.sub(r'\s+', ' ', text)
    
    # --- PADRÕES DE BUSCA (ANS, do mais específico ao mais genérico) ---
    patterns_ans = [
        r'1\s*-\s*Registro\s+ANS[:\s]*(\d+)',
        r'Registro\s+ANS[:\s]*(\d+)',
        r'ANS[:\s]*[Nn]?[°º]?\s*(\d{6,})',
        r'operadora.*?ANS.*?(\d{6,})',
    ]
    for pattern in patterns_ans:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            data['1 - Registro ANS'] = match.group(1).strip()
            break
            
    # --- PADRÕES DE BUSCA (NÚMERO GUIA) ---
    patterns_guia = [
        r'2\s*-\s*N[uú]mero\s+GUIA[:\s]*(\d+)',
        r'N[uú]mero\s+GUIA[:\s]*(\d+)',
        r'GUIA[:\s]*[Nn°º]?\s*(\d{5,})',
        r'n[°º]?\s*da\s+guia[:\s]*(\d{5,})',
    ]
    for pattern in patterns_guia:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            numero = re.sub(r'\D', '', match.group(1))
            if len(numero) >= 5:
                data['2 - Número GUIA'] = numero
                break
            
    # --- PADRÕES DE BUSCA (DATA DE AUTORIZAÇÃO) ---
    patterns_data = [
        r'4\s*-\s*Data\s+de\s+Autoriza[cç][aã]o[:\s]*(\d{2}/\d{2}/\d{4})',
        r'Data\s+de\s+Autoriza[cç][aã]o[:\s]*(\d{2}/\d{2}/\d{4})',
        r'Autoriza[cç][aã]o[:\s]*(\d{2}/\d{2}/\d{4})',
        r'(\d{2}/\d{2}/\d{4})', # Padrão mais genérico
    ]
    for pattern in patterns_data:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            data['4 - Data de Autorização'] = match.group(1)
            break
            
    # --- PADRÕES DE BUSCA (NOME) ---
    patterns_nome = [
        r'10\s*-\s*Nome[:\s]+([A-ZÀÁÂÃÇÉÊÍÓÔÕÚ][A-Za-zàáâãçéêíóôõúÀÁÂÃÇÉÊÍÓÔÕÚ\s]+?)(?:\s+\d{2}/|\s+CPF|\s+RG|\s+Cart|\s+\d{3}\.)',
        r'(?:Benefici[aá]rio|Paciente|Nome)[:\s]+([A-ZÀÁÂÃÇÉÊÍÓÔÕÚ][A-Za-zàáâãçéêíóôõúÀÁÂÃÇÉÊÍÓÔÕÚ\s]{15,80}?)(?:\s+CPF|\s+RG|\s+\d{2}/)',
    ]
    
    for pattern in patterns_nome:
        match = re.search(pattern, text)
        if match:
            nome = match.group(1).strip()
            nome = re.sub(r'\s+', ' ', nome)
            
            palavras = nome.split()
            if len(palavras) >= 2 and all(len(p) > 1 for p in palavras):
                data['10 - Nome'] = nome
                break
            
    # --- PADRÕES DE BUSCA (VALOR DA CONSULTA) ---
    patterns_valor = [
        r'R\$\s*(\d{1,3}(?:\.\d{3})*,\d{2})', # Padrão R$ 1.234,56
        r'[Vv]alor[:\s]*R?\$?\s*(\d{1,3}(?:\.\d{3})*,\d{2})',
        r'[Tt]otal[:\s]*R?\$?\s*(\d{1,3}(?:\.\d{3})*,\d{2})',
        r'[Cc]onsulta[:\s]*R?\$?\s*(\d{1,3}(?:\.\d{3})*,\d{2})',
    ]
    for pattern in patterns_valor:
        match = re.search(pattern, text)
        if match:
            data['Valor da Consulta'] = match.group(1)
            break
            
    return data


# ==================== INTERFACE DO USUÁRIO ====================

if reader is None:
    st.error("A aplicação não pode iniciar. EasyOCR Reader falhou ao carregar.")
    st.stop()

# Sidebar
st.sidebar.header("📤 Upload de Arquivos")
show_debug = st.sidebar.checkbox("🔍 Mostrar texto extraído (Debug)", value=False)

uploaded_files = st.sidebar.file_uploader(
    "Selecione arquivos PDF ou imagens (JPG/PNG)",
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
        
        # O EasyOCR processa o arquivo na memória, mas resetamos o ponteiro
        file.seek(0)

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
    
    # Criar DataFrame e permitir edição
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
        
        st.subheader("📋 Dados Extraídos (Edite para Corrigir OCR)")
        
        edited_df = st.data_editor(
            df,
            use_container_width=True,
            num_rows="dynamic",
            key="data_editor"
        )
        
        # Estatísticas (Métricas)
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("📁 Arquivos Processados", len(edited_df))
        
        with col2:
            total_campos = len(edited_df) * 5
            campos_preenchidos = 0
            for col in ['1 - Registro ANS', '2 - Número GUIA', '4 - Data de Autorização', '10 - Nome', 'Valor da Consulta']:
                campos_preenchidos += edited_df[col].astype(str).str.strip().ne('').sum()
            
            taxa = (campos_preenchidos / total_campos * 100) if total_campos > 0 else 0
            st.metric("📊 Taxa de Preenchimento", f"{taxa:.1f}%")
        
        with col3:
            valores_count = edited_df['Valor da Consulta'].astype(str).str.strip().ne('').sum()
            st.metric("💰 Valores Extraídos", valores_count)
        
        # Gerar Excel para download
        st.subheader("💾 Download")
        
        output = io.BytesIO()
        
        # Usa xlsxwriter para formatação avançada
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            edited_df.to_excel(writer, index=False, sheet_name='Dados Médicos')
            
            workbook = writer.book
            worksheet = writer.sheets['Dados Médicos']
            
            # Formatação do cabeçalho
            header_format = workbook.add_format({
                'bold': True,
                'text_wrap': True,
                'valign': 'center',
                'fg_color': '#1E88E5', # Azul
                'font_color': '#FFFFFF',
                'border': 1
            })
            
            # Aplicar formato e ajustar largura das colunas
            for col_num, value in enumerate(edited_df.columns.values):
                worksheet.write(0, col_num, value, header_format)
                
                max_length = max(
                    edited_df[value].astype(str).apply(len).max(),
                    len(str(value))
                ) + 2
                worksheet.set_column(col_num, col_num, min(max_length, 50))
        
        excel_data = output.getvalue()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        st.download_button(
            label="📥 Baixar Planilha Excel (.xlsx)",
            data=excel_data,
            file_name=f"guias_medicas_easyocr_{timestamp}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )
        
    else:
        st.warning("⚠️ Nenhum dado foi extraído. Verifique os arquivos.")

else:
    # --- Tela inicial (instruções) ---
    st.info("👈 **Faça upload de arquivos na barra lateral para começar**")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 📖 Como Usar")
        st.markdown("""
        1. **Faça upload** de PDFs ou imagens na barra lateral.
        2. **Aguarde** o processamento (A primeira execução pode demorar mais, devido ao carregamento do modelo EasyOCR).
        3. **Revise** e edite a tabela para corrigir erros do OCR.
        4. **Baixe** a planilha Excel editada.
        """)
    
    with col2:
        st.markdown("### ⚙️ Dicas de Qualidade")
        st.markdown("""
        - O **EasyOCR** é uma excelente alternativa ao Tesseract, geralmente entregando maior precisão em textos manuscritos ou complexos.
        - Ele utiliza um modelo de Machine Learning, sendo mais pesado para carregar, mas seu modelo é **cacheado** para execuções subsequentes.
        - Mantenha a qualidade da imagem (acima de 300 DPI) para melhores resultados.
        """)

# Rodapé
st.sidebar.markdown("---")
st.sidebar.info("""
**Engine:** **EasyOCR** (com PyTorch)
**Vantagem:** Maior precisão em imagens complexas e menos dependência de bibliotecas de sistema operacional.
""")
