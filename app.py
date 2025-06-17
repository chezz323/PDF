import streamlit as st
import warnings
warnings.filterwarnings("ignore")  # 경고 숨김

from pypdf import PdfReader, PdfWriter
from pdf2image import convert_from_bytes
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.pagesizes import letter
from reportlab.lib.colors import black

import tempfile
import os

# 폰트 등록
pdfmetrics.registerFont(TTFont('NanumBarunGothicBold', 'NanumBarunGothicBold.ttf'))

# PDF 병합
def merge_pdfs(files):
    writer = PdfWriter()
    for f in files:
        reader = PdfReader(f)
        for page in reader.pages:
            writer.add_page(page)
    merged = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    with open(merged.name, "wb") as f:
        writer.write(f)
    return merged.name

# 썸네일 생성
def generate_thumbnails(pdf_path):
    with open(pdf_path, "rb") as f:
        return convert_from_bytes(f.read(), size=(300, None))

# 페이지 추출
def extract_pages(pdf_path, indices):
    reader = PdfReader(pdf_path)
    writer = PdfWriter()
    for i in indices:
        writer.add_page(reader.pages[i])
    out = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    with open(out.name, "wb") as f:
        writer.write(f)
    return out.name

# 페이지 제거
def remove_pages(pdf_path, remove_indices):
    reader = PdfReader(pdf_path)
    writer = PdfWriter()
    kept_indices = []
    for i, page in enumerate(reader.pages):
        if i not in remove_indices:
            writer.add_page(page)
            kept_indices.append(i)
    out = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    with open(out.name, "wb") as f:
        writer.write(f)
    return out.name, kept_indices

# 워터마크 생성
def create_watermark(text, path):
    from reportlab.lib.colors import Color
    gray_transparent = Color(0.4, 0.4, 0.4, alpha=0.3)

    c = canvas.Canvas(path, pagesize=letter)
    c.setFillColor(gray_transparent)
    c.setFont("NanumBarunGothicBold", 20)
    text_width = c.stringWidth(text, "NanumBarunGothicBold", 20)
    x = (letter[0] - text_width) / 2
    y = letter[1] / 2
    c.drawString(x, y, text)
    c.save()


# 워터마크 적용
def create_temp_pdf_path():
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    tmp.close()
    return tmp.name


def apply_watermarks(pdf_path, wm_texts):
    reader = PdfReader(pdf_path)
    writer = PdfWriter()
    for i, page in enumerate(reader.pages):
        wm_text = f"{i+1} {wm_texts[i]}"
        temp_path = create_temp_pdf_path()
        create_watermark(wm_text, temp_path)
        wm_reader = PdfReader(temp_path)
        page.merge_page(wm_reader.pages[0])
        writer.add_page(page)
        os.remove(temp_path)
    out_path = create_temp_pdf_path()
    with open(out_path, "wb") as f:
        writer.write(f)
    return out_path


# Streamlit UI 시작
st.set_page_config(layout="wide")
st.title("📄 문제/답지 분리 및 워터마크 삽입 도구")

uploaded_files = st.file_uploader("문제+답지가 포함된 PDF 파일들을 업로드하세요", type="pdf", accept_multiple_files=True)

if uploaded_files:
    merged_path = merge_pdfs(uploaded_files)
    thumbs = generate_thumbnails(merged_path)

    st.header("🖼️ 답지 페이지 선택")
    answer_indices = []
    cols = st.columns(3)

    for i, img in enumerate(thumbs):
        col = cols[i % 3]
        with col:
            st.image(img, caption=f"Page {i+1}", use_container_width=True)
            if st.checkbox(f"답지 (Page {i+1})", key=f"ans_{i}"):
                answer_indices.append(i)

    if answer_indices:
        answer_pdf = extract_pages(merged_path, answer_indices)
        with open(answer_pdf, "rb") as f:
            st.download_button("📤 선택된 답지만 저장", f.read(), file_name="answers.pdf")

    # 답지 제외한 문제 PDF 생성
    problem_pdf, problem_indices = remove_pages(merged_path, answer_indices)
    problem_thumbs = [thumbs[i] for i in problem_indices]

    st.header("✍️ 문제에 워터마크 삽입")
    st.markdown("예: `월요일,2` → 1 월요일 / 2 월요일 ...")
    wm_input = st.text_area("텍스트,장수 형태로 입력", height=200)

    if wm_input:
        try:
            wm_lines = wm_input.strip().splitlines()
            wm_texts = []
            for line in wm_lines:
                txt, cnt = line.split(",")
                wm_texts.extend([txt.strip()] * int(cnt))

            if len(wm_texts) != len(problem_indices):
                st.error(f"⚠️ 총 입력된 워터마크 수({len(wm_texts)})가 문제 페이지 수({len(problem_indices)})와 다릅니다.")
            else:
                if st.button("🖋️ 워터마크 적용 후 문제 저장"):
                    watermarked_pdf = apply_watermarks(problem_pdf, wm_texts)
                    with open(watermarked_pdf, "rb") as f:
                        st.download_button("📄 문제 (워터마크 포함) 저장", f.read(), file_name="questions_watermarked.pdf")
        except Exception as e:
            st.error(f"입력 오류: {e}")
