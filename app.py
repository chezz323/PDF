import streamlit as st
from PyPDF2 import PdfReader, PdfWriter
import tempfile
import os
from PIL import Image
import io

st.set_page_config(page_title="PDF 정리 도우미", layout="centered")

# ------------------------- 상태 초기화 ----------------------------
if "file_order" not in st.session_state:
    st.session_state.file_order = []
if "confirmed" not in st.session_state:
    st.session_state.confirmed = False
if "sorted_files" not in st.session_state:
    st.session_state.sorted_files = []
if "step" not in st.session_state:
    st.session_state.step = 1
if "answer_pages" not in st.session_state:
    st.session_state.answer_pages = []

# ------------------------- 기능 함수 ----------------------------
def merge_pdfs(files):
    writer = PdfWriter()
    for f in files:
        reader = PdfReader(f)
        for page in reader.pages:
            writer.add_page(page)
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    with open(temp_file.name, "wb") as f:
        writer.write(f)
    return temp_file.name

def get_page_images(pdf_path):
    from fitz import open as fitz_open  # PyMuPDF
    doc = fitz_open(pdf_path)
    images = []
    for page in doc:
        pix = page.get_pixmap(dpi=100)
        img = Image.open(io.BytesIO(pix.tobytes("png")))
        images.append(img)
    return images

def apply_watermarks(input_pdf_path, wm_texts):
    reader = PdfReader(input_pdf_path)
    writer = PdfWriter()
    for i, page in enumerate(reader.pages):
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.lib.colors import Color
        from reportlab.lib.units import inch

        packet = io.BytesIO()
        can = canvas.Canvas(packet, pagesize=letter)
        pdfmetrics.registerFont(TTFont('Nanum', 'NanumBarunGothicBold.ttf'))
        gray = Color(0.3, 0.3, 0.3, alpha=0.4)
        can.setFont("Nanum", 30)
        can.setFillColor(gray)
        text = f"{i+1} {wm_texts[i]}"
        can.drawCentredString(letter[0]/2, letter[1]/2, text)
        can.save()
        packet.seek(0)
        wm_pdf = PdfReader(packet)
        page.merge_page(wm_pdf.pages[0])
        writer.add_page(page)

    out_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    with open(out_file.name, "wb") as f:
        writer.write(f)
    return out_file.name

# ------------------------- 1단계: 파일 업로드 및 순서 조정 ----------------------------
if st.session_state.step == 1:
    st.header("1단계: PDF 파일 업로드 및 순서 조정")
    uploaded_files = st.file_uploader("📁 PDF 파일 업로드", type=["pdf"], accept_multiple_files=True)

    if uploaded_files and not st.session_state.file_order:
        st.session_state.file_order = list(range(len(uploaded_files)))

    def move_file(index, direction):
        order = st.session_state.file_order
        new_index = index + direction
        if 0 <= new_index < len(order):
            order[index], order[new_index] = order[new_index], order[index]

    if uploaded_files and st.session_state.file_order:
        st.markdown("### 📑 업로드된 파일 순서 조정")
        for i, file_index in enumerate(st.session_state.file_order):
            file = uploaded_files[file_index]
            col1, col2, col3 = st.columns([0.6, 0.2, 0.2])
            with col1:
                st.write(f"{i+1}. {file.name}")
            with col2:
                if st.button("⬆️", key=f"up_{i}"):
                    move_file(i, -1)
            with col3:
                if st.button("⬇️", key=f"down_{i}"):
                    move_file(i, 1)

        if st.button("✅ 확인하고 다음 단계로"):
            st.session_state.confirmed = True
            st.session_state.sorted_files = [uploaded_files[i] for i in st.session_state.file_order]
            st.session_state.step = 2

# ------------------------- 2단계: 답지 페이지 선택 ----------------------------
if st.session_state.step == 2:
    st.header("2단계: 답지 페이지 선택")
    merged_path = merge_pdfs(st.session_state.sorted_files)
    thumbs = get_page_images(merged_path)
    selected = []
    for i, img in enumerate(thumbs):
        col1, col2 = st.columns([0.1, 0.9])
        with col1:
            if st.checkbox(f"{i+1}쪽", key=f"chk_{i}"):
                selected.append(i)
        with col2:
            st.image(img, width=200)

    if st.button("📥 답지만 저장하고 다음 단계로"):
        reader = PdfReader(merged_path)
        writer = PdfWriter()
        for i in selected:
            writer.add_page(reader.pages[i])
        out = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        with open(out.name, "wb") as f:
            writer.write(f)
        st.download_button("📄 답지 다운로드", data=open(out.name, "rb").read(), file_name="answers.pdf")
        st.session_state.answer_pages = selected
        st.session_state.step = 3

# ------------------------- 3단계: 문제 워터마크 삽입 ----------------------------
if st.session_state.step == 3:
    st.header("3단계: 문제 워터마크 삽입")
    merged_path = merge_pdfs(st.session_state.sorted_files)
    reader = PdfReader(merged_path)
    total_pages = len(reader.pages)
    problem_indices = [i for i in range(total_pages) if i not in st.session_state.answer_pages]

    st.markdown("한 줄에 텍스트와 장수(예: 월요일,2)를 입력해 주세요")
    wm_input = st.text_area("워터마크 입력")

    if wm_input:
        try:
            wm_lines = wm_input.strip().splitlines()
            wm_texts = []
            for line in wm_lines:
                txt, cnt = line.split(",")
                wm_texts.extend([txt.strip()] * int(cnt))

            if len(wm_texts) != len(problem_indices):
                st.error(f"⚠️ 워터마크 수({len(wm_texts)}) ≠ 문제 페이지 수({len(problem_indices)})")
            else:
                if st.button("🖋️ 워터마크 적용 후 문제 저장"):
                    reordered_pdf = PdfWriter()
                    for i in problem_indices:
                        reordered_pdf.add_page(reader.pages[i])
                    temp_path = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
                    with open(temp_path.name, "wb") as f:
                        reordered_pdf.write(f)
                    wm_applied = apply_watermarks(temp_path.name, wm_texts)
                    with open(wm_applied, "rb") as f:
                        st.download_button("📄 문제 저장 (워터마크 포함)", f.read(), file_name="questions_watermarked.pdf")
        except Exception as e:
            st.error(f"입력 오류: {e}")