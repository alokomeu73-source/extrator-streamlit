# 🩺 Leitor de PDFs Médicos (Streamlit)

Aplicativo para extrair automaticamente informações de laudos e documentos médicos, mesmo que estejam escaneados.

## 🚀 Como funciona
- Detecta automaticamente se o PDF contém texto digital ou é uma imagem;
- Usa **PyMuPDF** para extrair texto digital;
- Usa **EasyOCR** para ler PDFs escaneados (OCR);
- Extrai informações como **Nome**, **Data**, **Procedimento**, **Médico** e **CRM**;
- Gera uma tabela e exporta os dados em **CSV**.

## 🧩 Requisitos
Veja `requirements.txt` para as versões testadas no Streamlit Cloud.

## ☁️ Deploy no Streamlit Cloud
1. Crie um repositório no GitHub com esses 3 arquivos:
   - `app.py`
   - `requirements.txt`
   - `README.md`
2. Vá até [https://share.streamlit.io](https://share.streamlit.io)
3. Clique em **"New app"** e conecte seu repositório.
4. O app será executado automaticamente.
