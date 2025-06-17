import streamlit as st
from PyPDF2 import PdfReader, PdfWriter
import tempfile
import os
from PIL import Image
import fitz  # PyMuPDF

st.set_page_config(page_title="PDF 정리 도우미", layout="wide")

# ------------------------- 상태 초기화 ----------------------------
if "file_order" not in st.session_state:
    st.session_state.file_order = []
if "confirmed" not in st.session_state:
    st.session_state.confirmed = False
if "sorted_files" not in st.session_state:
    st.session_state.sorted_files = []
if "step" not in st.session_state:
    st.session_state.step = 1
if "answer_indices" not in st.session_state:
    st.session_state.answer_indices = set()
if "merged_pdf_path" not in st.session_state:
    st.session_state.merged_pdf_path = ""

# ------------------------- 1단계: 파일 업로드 및 순서 조정 ----------------------------
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
        with st.container():
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

# ------------------------- 2단계: 답지 선택 ----------------------------
if st.session_state.step == 2:
    st.header("2단계: 답지 페이지 선택 및 저장")

    def merge_pdfs(files):
        writer = PdfWriter()
        for file in files:
            reader = PdfReader(file)
            for page in reader.pages:
                writer.add_page(page)
        temp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        with open(temp.name, "wb") as f:
            writer.write(f)
        return temp.name

    def generate_thumbnails(pdf_path):
        thumbs = []
        doc = fitz.open(pdf_path)
        for page in doc:
            pix = page.get_pixmap(matrix=fitz.Matrix(0.3, 0.3))
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            thumbs.append(img)
        return thumbs

    merged_path = merge_pdfs(st.session_state.sorted_files)
    st.session_state.merged_pdf_path = merged_path
    thumbs = generate_thumbnails(merged_path)

    cols_per_row = max(1, st.columns(1)[0].width // 180)
    rows = [thumbs[i:i+cols_per_row] for i in range(0, len(thumbs), cols_per_row)]

    for row_idx, row in enumerate(rows):
        cols = st.columns(len(row))
        for col_idx, img in enumerate(row):
            idx = row_idx * cols_per_row + col_idx
            with cols[col_idx]:
                st.image(img, caption=f"Page {idx+1}", use_container_width=True)
                selected = st.checkbox("답지로 선택", key=f"answer_{idx}")
                if selected:
                    st.session_state.answer_indices.add(idx)
                else:
                    st.session_state.answer_indices.discard(idx)

    if st.button("💾 답지만 저장하고 다음 단계로"):
        reader = PdfReader(merged_path)
        writer = PdfWriter()
        for i in sorted(st.session_state.answer_indices):
            writer.add_page(reader.pages[i])
        temp_ans = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        with open(temp_ans.name, "wb") as f:
            writer.write(f)
        with open(temp_ans.name, "rb") as f:
            st.download_button("📥 답지 PDF 저장", data=f.read(), file_name="answers.pdf")
        st.session_state.step = 3

# ------------------------- 3단계: 문제 페이지 워터마크 ----------------------------
if st.session_state.step == 3:
    st.header("3단계: 문제 페이지 워터마크 삽입")

    wm_input = st.text_area("✍️ 워터마크 입력 (한 줄에 '텍스트, 개수' 형식으로)",
                            help="예: 월요일, 2 → 1페이지: '1 월요일', 2페이지: '2 월요일'")

    def apply_watermarks(input_pdf, wm_texts):
        reader = PdfReader(input_pdf)
        writer = PdfWriter()
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.lib.colors import Color
        pdfmetrics.registerFont(TTFont('NanumBarunGothicBold', 'NanumBarunGothicBold.ttf'))

        for i, page in enumerate(reader.pages):
            if i in st.session_state.answer_indices:
                continue
            wm_text = f"{i+1} {wm_texts[i]}"
            packet = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
            c = canvas.Canvas(packet.name, pagesize=letter)
            c.setFont("NanumBarunGothicBold", 30)
            c.setFillColor(Color(0.5, 0.5, 0.5, alpha=0.3))  # 회색 + 반투명
            c.drawCentredString(300, 400, wm_text)
            c.save()

            wm_reader = PdfReader(packet.name)
            page.merge_page(wm_reader.pages[0])
            writer.add_page(page)
            os.remove(packet.name)

        temp_out = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        with open(temp_out.name, "wb") as f:
            writer.write(f)
        return temp_out.name

    if wm_input:
        try:
            wm_lines = wm_input.strip().splitlines()
            wm_texts = []
            for line in wm_lines:
                txt, cnt = line.split(",")
                wm_texts.extend([txt.strip()] * int(cnt))

            problem_indices = [i for i in range(len(PdfReader(st.session_state.merged_pdf_path).pages)) if i not in st.session_state.answer_indices]

            if len(wm_texts) != len(problem_indices):
                st.error(f"⚠️ 입력된 워터마크 수({len(wm_texts)})와 문제 페이지 수({len(problem_indices)})가 일치하지 않습니다.")
            else:
                if st.button("🖋️ 워터마크 적용 및 문제 저장"):
                    watermarked_pdf = apply_watermarks(st.session_state.merged_pdf_path, wm_texts)
                    with open(watermarked_pdf, "rb") as f:
                        st.download_button("📄 문제 PDF 저장", f.read(), file_name="questions_watermarked.pdf")
        except Exception as e:
            st.error(f"입력 오류: {e}")
