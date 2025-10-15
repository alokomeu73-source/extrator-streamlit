import streamlit as st
import pandas as pd
import re
import io
from PIL import Image
import numpy as np
import fitz  # PyMuPDF
from datetime import datetime
import gc

# Configuração da página
st.set_page_config(
    page_title="Extrator de Guias Médicas",
    page_icon="🏥",
    layout="wide"
)

# Inicialização do session state
if 'ocr_reader' not in st.session_state:
    st.session_state.ocr_reader = None
    st.session_state.ocr_loaded = False


@st.cache_resource(show_spinner=False)
def load_easyocr():
    """Carrega o modelo EasyOCR apenas uma vez e mantém em cache"""
    try:
        import easyocr
        # Configuração otimizada para Streamlit Cloud
        reader = easyocr.Reader(
            ['pt'], 
            gpu=False,
            verbose=False,
            download_enabled=True,
            model_storage_directory=None,
            detect_network='craft',
            recog_network='standard'
        )
        return reader
    except Exception as e:
        st.error(f"Erro ao carregar EasyOCR: {str(e)}")
        return None


def extract_text_from_image(image):
    """Extrai texto de uma imagem usando EasyOCR"""
    try:
        # Carrega o OCR se necessário
        if st.session_state.ocr_reader is None:
            with st.spinner("🔄 Inicializando modelo OCR... (pode levar 1-2 minutos na primeira vez)"):
                st.session_state.ocr_reader = load_easyocr()
                if st.session_state.ocr_reader is None:
                    return ""
                st.session_state.ocr_loaded = True
        
        # Redimensiona imagem se for muito grande
        max_size = 2000
        if max(image.size) > max_size:
            ratio = max_size / max(image.size)
            new_size = tuple([int(dim * ratio) for dim in image.size])
            image = image.resize(new_size, Image.Resampling.LANCZOS)
        
        # Converte para RGB se necessário
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        # Converte PIL Image para numpy array
        img_array = np.array(image)
        
        # Executa OCR com configurações otimizadas
        results = st.session_state.ocr_reader.readtext(
            img_array,
            detail=0,  # Retorna apenas texto, sem coordenadas
            paragraph=False,
            batch_size=1
        )
        
        # Concatena todos os textos extraídos
        text = ' '.join(results) if results else ""
        
        # Libera memória
        del img_array
        gc.collect()
        
        return text
        
    except Exception as e:
        st.error(f"Erro ao extrair texto da imagem: {str(e)}")
        return ""


def extract_text_from_pdf(pdf_file):
    """Extrai texto de um arquivo PDF usando PyMuPDF e OCR"""
    try:
        pdf_bytes = pdf_file.read()
        pdf_document = fitz.open(stream=pdf_bytes, filetype="pdf")
        
        full_text = ""
        total_pages = len(pdf_document)
        
        # Limita a 10 páginas para evitar timeout
        max_pages = min(total_pages, 10)
        if total_pages > max_pages:
            st.warning(f"⚠️ PDF tem {total_pages} páginas. Processando apenas as primeiras {max_pages} páginas.")
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for page_num in range(max_pages):
            status_text.text(f"📄 Processando página {page_num + 1} de {max_pages}...")
            
            try:
                page = pdf_document[page_num]
                
                # Tenta extrair texto direto primeiro
                page_text = page.get_text()
                
                # Se não houver texto suficiente, usa OCR
                if len(page_text.strip()) < 50:
                    # Converte página para imagem com zoom 2x
                    mat = fitz.Matrix(2, 2)
                    pix = page.get_pixmap(matrix=mat)
                    img_data = pix.tobytes("png")
                    img = Image.open(io.BytesIO(img_data))
                    
                    # Extrai texto via OCR
                    page_text = extract_text_from_image(img)
                    
                    # Libera memória
                    del pix, img_data, img
                    gc.collect()
                
                full_text += page_text + "\n"
                
            except Exception as e:
                st.warning(f"⚠️ Erro na página {page_num + 1}: {str(e)}")
                continue
            
            progress_bar.progress((page_num + 1) / max_pages)
        
        pdf_document.close()
        progress_bar.empty()
        status_text.empty()
        
        return full_text
        
    except Exception as e:
        st.error(f"Erro ao processar PDF: {str(e)}")
        return ""


def extract_fields_from_text(text, filename):
    """Extrai os campos específicos usando RegEx"""
    
    if not text or len(text.strip()) < 10:
        st.warning(f"⚠️ Pouco texto extraído de {filename}")
    
    # Remove quebras de linha e espaços extras
    text_clean = ' '.join(text.split())
    
    # Dicionário para armazenar os campos
    data = {
        'Arquivo': filename,
        '1 - Registro ANS': '',
        '2 - Número GUIA': '',
        '4 - Data de Autorização': '',
        '10 - Nome': ''
    }
    
    # RegEx para Registro ANS
    ans_patterns = [
        r'(?:Registro\s+ANS|ANS)[:\s]*([0-9]{5,7})',
        r'(?:1\s*[-.\s]*Registro\s+ANS)[:\s]*([0-9]{5,7})',
        r'(?:^|\s)([0-9]{6})(?:\s|$)',
    ]
    for pattern in ans_patterns:
        match = re.search(pattern, text_clean, re.IGNORECASE)
        if match:
            data['1 - Registro ANS'] = match.group(1).strip()
            break
    
    # RegEx para Número da GUIA
    guia_patterns = [
        r'(?:N[úu]mero\s+(?:da\s+)?GUIA|GUIA\s+N)[:\s]*([0-9]{10,20})',
        r'(?:2\s*[-.\s]*N[úu]mero\s+GUIA)[:\s]*([0-9]{10,20})',
        r'(?:N[°º]\s*Guia)[:\s]*([0-9]{10,20})',
        r'(?:GUIA)[:\s]+([0-9]{10,20})',
    ]
    for pattern in guia_patterns:
        match = re.search(pattern, text_clean, re.IGNORECASE)
        if match:
            data['2 - Número GUIA'] = match.group(1).strip()
            break
    
    # RegEx para Data de Autorização
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
    
    # RegEx para Nome
    nome_patterns = [
        r'(?:10\s*[-.\s]*Nome)[:\s]*([A-ZÀÁÂÃÄÅÇÈÉÊËÌÍÎÏÑÒÓÔÕÖÙÚÛÜ][A-ZÀÁÂÃÄÅÇÈÉÊËÌÍÎÏÑÒÓÔÕÖÙÚÛÜ\s]{2,50})',
        r'(?:Nome\s+(?:do\s+)?(?:Benefici[áa]rio|Paciente))[:\s]*([A-ZÀÁÂÃÄÅÇÈÉÊËÌÍÎÏÑÒÓÔÕÖÙÚÛÜ][A-ZÀÁÂÃÄÅÇÈÉÊËÌÍÎÏÑÒÓÔÕÖÙÚÛÜ\s]{2,50})',
        r'(?:Benefici[áa]rio)[:\s]*([A-ZÀÁÂÃÄÅÇÈÉÊËÌÍÎÏÑÒÓÔÕÖÙÚÛÜ][A-ZÀÁÂÃÄÅÇÈÉÊËÌÍÎÏÑÒÓÔÕÖÙÚÛÜ\s]{2,50})',
    ]
    for pattern in nome_patterns:
        match = re.search(pattern, text_clean, re.IGNORECASE)
        if match:
            nome_raw = match.group(1).strip()
            # Remove números e caracteres especiais
            nome_clean = re.sub(r'[0-9\-/:.]+', '', nome_raw).strip()
            # Remove espaços extras
            nome_clean = ' '.join(nome_clean.split())
            if len(nome_clean) >= 3:
                data['10 - Nome'] = nome_clean
                break
    
    return data


def process_image_file(image_file):
    """Processa um arquivo de imagem"""
    try:
        img = Image.open(image_file)
        
        with st.spinner(f"🔍 Extraindo texto de {image_file.name}..."):
            text = extract_text_from_image(img)
        
        if not text:
            st.warning(f"⚠️ Nenhum texto foi extraído de {image_file.name}")
        
        return extract_fields_from_text(text, image_file.name)
        
    except Exception as e:
        st.error(f"❌ Erro ao processar {image_file.name}: {str(e)}")
        return {
            'Arquivo': image_file.name,
            '1 - Registro ANS': 'ERRO',
            '2 - Número GUIA': 'ERRO',
            '4 - Data de Autorização': 'ERRO',
            '10 - Nome': 'ERRO'
        }


def process_pdf_file(pdf_file):
    """Processa um arquivo PDF"""
    try:
        text = extract_text_from_pdf(pdf_file)
        
        if not text:
            st.warning(f"⚠️ Nenhum texto foi extraído de {pdf_file.name}")
        
        return extract_fields_from_text(text, pdf_file.name)
        
    except Exception as e:
        st.error(f"❌ Erro ao processar {pdf_file.name}: {str(e)}")
        return {
            'Arquivo': pdf_file.name,
            '1 - Registro ANS': 'ERRO',
            '2 - Número GUIA': 'ERRO',
            '4 - Data de Autorização': 'ERRO',
            '10 - Nome': 'ERRO'
        }


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

**💡 Dica:** A primeira execução pode levar 1-2 minutos para baixar os modelos de OCR.
""")

# Informações importantes
with st.expander("ℹ️ Informações Importantes"):
    st.write("""
    - **PDFs:** Máximo de 10 páginas por arquivo
    - **Imagens:** Formatos aceitos: PNG, JPG, JPEG
    - **Tamanho:** Recomendado até 5MB por arquivo
    - **Qualidade:** Quanto melhor a qualidade da imagem, melhor a extração
    - **Tempo:** Primeiro processamento pode demorar mais (download de modelos)
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
    
    # Limita o número de arquivos
    if len(uploaded_files) > 20:
        st.error("❌ Limite de 20 arquivos por vez. Por favor, reduza a quantidade.")
    else:
        if st.button("🚀 Processar Arquivos", type="primary", use_container_width=True):
            results = []
            
            # Barra de progresso geral
            overall_progress = st.progress(0)
            
            # Processa cada arquivo
            for idx, file in enumerate(uploaded_files):
                st.write(f"**Processando {idx + 1}/{len(uploaded_files)}: {file.name}**")
                
                try:
                    if file.type == "application/pdf":
                        data = process_pdf_file(file)
                    else:
                        data = process_image_file(file)
                    
                    results.append(data)
                    
                    # Verifica se extraiu pelo menos um campo
                    campos_extraidos = sum(1 for k, v in data.items() if k != 'Arquivo' and v and v != 'ERRO')
                    if campos_extraidos > 0:
                        st.success(f"✓ {file.name} - {campos_extraidos} campo(s) extraído(s)")
                    else:
                        st.warning(f"⚠️ {file.name} - Nenhum campo extraído")
                    
                except Exception as e:
                    st.error(f"❌ Erro crítico em {file.name}: {str(e)}")
                    results.append({
                        'Arquivo': file.name,
                        '1 - Registro ANS': 'ERRO',
                        '2 - Número GUIA': 'ERRO',
                        '4 - Data de Autorização': 'ERRO',
                        '10 - Nome': 'ERRO'
                    })
                
                overall_progress.progress((idx + 1) / len(uploaded_files))
            
            overall_progress.empty()
            
            # Cria DataFrame
            if results:
                df = pd.DataFrame(results)
                st.session_state.df_results = df
                st.balloons()
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
        ans_preenchidos = edited_df['1 - Registro ANS'].astype(str).str.strip().ne('').ne('ERRO').sum()
        st.metric("ANS Extraídos", f"{ans_preenchidos}/{len(edited_df)}")
    with col3:
        guia_preenchidos = edited_df['2 - Número GUIA'].astype(str).str.strip().ne('').ne('ERRO').sum()
        st.metric("GUIA Extraídos", f"{guia_preenchidos}/{len(edited_df)}")
    with col4:
        nome_preenchidos = edited_df['10 - Nome'].astype(str).str.strip().ne('').ne('ERRO').sum()
        st.metric("Nomes Extraídos", f"{nome_preenchidos}/{len(edited_df)}")

# Rodapé
st.divider()
st.caption("🔒 Os arquivos são processados na nuvem e não são armazenados após o processamento")
