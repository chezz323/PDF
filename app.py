import streamlit as st
from PyPDF2 import PdfReader, PdfWriter
from PIL import Image
import tempfile, fitz  # fitz = PyMuPDF
from streamlit_js_eval import streamlit_js_eval
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from PyPDF2 import PdfReader, PdfWriter
from io import BytesIO

# ------------------- 설정 -------------------
st.set_page_config(page_title="PDF 문제/답지 도구", layout="wide")

if "step" not in st.session_state:
    st.session_state.step = 1
if "sorted_files" not in st.session_state:
    st.session_state.sorted_files = []
if "answer_indices" not in st.session_state:
    st.session_state.answer_indices = set()
if "merged_pdf_path" not in st.session_state:
    st.session_state.merged_pdf_path = None

# ------------------- Step 1 -------------------
if st.session_state.step == 1:
    st.header("1단계: PDF 파일 업로드")

    uploaded = st.file_uploader("PDF 파일을 업로드하세요 (여러 개 가능)", type=["pdf"], accept_multiple_files=True)

    if uploaded:
        st.session_state.uploaded_files = uploaded
        st.session_state.sorted_files = uploaded

    if st.session_state.sorted_files:
        st.subheader("업로드된 파일 순서")
        for i, file in enumerate(st.session_state.sorted_files, 1):
            st.markdown(f"**{i}. {file.name}**")

        if st.button("다음 단계로 ▶️"):
            st.session_state.step = 2
            st.rerun()

# ------------------- Step 2 -------------------
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

    client_width = streamlit_js_eval(js_expressions="window.innerWidth", key="WIDTH") or 1200
    cols_per_row = max(1, client_width // 180)

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
        st.rerun()

# ------------------- Step 3 -------------------
if st.session_state.step == 3:
    st.header("3단계: 문제 페이지에 워터마크 삽입")

    wm_input = st.text_area("한 줄에 텍스트, 장수 입력 (예: 일요일, 1)")

    def create_watermark(text):
        buffer = BytesIO()
        c = canvas.Canvas(buffer, pagesize=letter)
        c.setFont("Helvetica", 40)
        c.setFillGray(0.5, 0.5)
        c.drawString(100, 500, text)
        c.save()
        buffer.seek(0)
        return PdfReader(buffer).pages[0]

    if wm_input:
        try:
            wm_lines = wm_input.strip().splitlines()
            wm_texts = []
            for line in wm_lines:
                txt, cnt = line.split(",")
                wm_texts.extend([txt.strip()] * int(cnt))

            reader = PdfReader(st.session_state.merged_pdf_path)
            problem_indices = sorted(set(range(len(reader.pages))) - st.session_state.answer_indices)

            if len(wm_texts) != len(problem_indices):
                st.error(f"⚠️ 총 입력된 워터마크 수({len(wm_texts)})가 문제 페이지 수({len(problem_indices)})와 다릅니다.")
            else:
                if st.button("🖋️ 워터마크 적용 후 문제 저장"):
                    writer = PdfWriter()
                    for i, idx in enumerate(problem_indices):
                        base_page = reader.pages[idx]
                        wm_page = create_watermark(f"{i+1} {wm_texts[i]}")
                        base_page.merge_page(wm_page)
                        writer.add_page(base_page)
                    temp_q = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
                    with open(temp_q.name, "wb") as f:
                        writer.write(f)
                    with open(temp_q.name, "rb") as f:
                        st.download_button("📄 문제 (워터마크 포함) 저장", f.read(), file_name="questions_watermarked.pdf")
        except Exception as e:
            st.error(f"입력 오류: {e}")
