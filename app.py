import streamlit as st
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.colors import Color
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from PIL import Image
import fitz  # PyMuPDF
import io
import os

pdfmetrics.registerFont(TTFont("NanumBarun", "NanumBarunGothicBold.ttf"))

st.set_page_config(page_title="PDF Editor", layout="wide")

if "step" not in st.session_state:
    st.session_state.step = 1

st.title("📄 PDF 처리 도구 (3단계)")

# --- Step 1: Upload and reorder pages ---
if st.session_state.step == 1:
    uploaded_files = st.file_uploader("📁 PDF 파일 업로드 (여러 개)", accept_multiple_files=True, type=["pdf"])
    if uploaded_files:
        # Merge PDFs
        merger = PdfWriter()
        for f in uploaded_files:
            reader = PdfReader(f)
            for p in reader.pages:
                merger.add_page(p)

        merged_path = "merged_temp.pdf"
        with open(merged_path, "wb") as f:
            merger.write(f)

        st.success("✅ PDF 병합 완료")

        # Thumbnail with fitz
        doc = fitz.open(merged_path)
        thumbs = []
        for i, page in enumerate(doc):
            pix = page.get_pixmap(matrix=fitz.Matrix(0.3, 0.3))
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            thumbs.append(img)

        st.markdown("📑 페이지 순서를 확인하세요")
        col_count = 5
        cols = st.columns(col_count)
        for idx, thumb in enumerate(thumbs):
            with cols[idx % col_count]:
                st.image(thumb, caption=f"Page {idx+1}", use_container_width=True)

        if st.button("➡️ 다음 단계로"):
            st.session_state["merged_path"] = merged_path
            st.session_state["page_count"] = len(thumbs)
            st.session_state.step = 2

# --- Step 2: Select answer pages ---
elif st.session_state.step == 2:
    st.markdown("### ✅ 답지 페이지 선택 및 저장")
    merged_path = st.session_state["merged_path"]
    page_count = st.session_state["page_count"]

    answer_pages = st.multiselect("✔️ 답지로 저장할 페이지 선택 (1부터 시작)", list(range(1, page_count + 1)))

    if st.button("💾 답지 저장"):
        reader = PdfReader(merged_path)
        writer = PdfWriter()
        for i in answer_pages:
            writer.add_page(reader.pages[i - 1])

        with open("answers.pdf", "wb") as f:
            writer.write(f)

        with open("answers.pdf", "rb") as f:
            st.download_button("📥 답지 PDF 다운로드", f.read(), file_name="answers.pdf")

    if st.button("➡️ 문제 페이지 워터마크 단계로"):
        st.session_state["problem_pages"] = [i for i in range(page_count) if (i + 1) not in answer_pages]
        st.session_state.step = 3

# --- Step 3: Apply watermark ---
elif st.session_state.step == 3:
    st.markdown("### ✏️ 문제 페이지 워터마크 입력")

    problem_indices = st.session_state["problem_pages"]
    merged_path = st.session_state["merged_path"]

    st.info(f"총 문제 페이지 수: {len(problem_indices)}")

    wm_input = st.text_area("🔤 워터마크 입력 (형식: 텍스트,장수)", height=200,
                            placeholder="예시:\n월요일,1\n화요일,2")

    def create_watermark(text, filename, size=40):
        from reportlab.pdfgen import canvas
        from reportlab.lib.colors import gray
        c = canvas.Canvas(filename, pagesize=letter)
        c.setFillColor(gray, alpha=0.3)
        c.setFont("NanumBarun", size)
        c.drawCentredString(letter[0] / 2, letter[1] / 2, text)
        c.save()

    def apply_watermarks(pdf_path, wm_texts):
        reader = PdfReader(pdf_path)
        writer = PdfWriter()
        for i, idx in enumerate(problem_indices):
            wm_text = f"{i+1} {wm_texts[i]}"
            wm_path = f"wm_temp_{i}.pdf"
            create_watermark(wm_text, wm_path)
            wm_pdf = PdfReader(wm_path)
            page = reader.pages[idx]
            page.merge_page(wm_pdf.pages[0])
            writer.add_page(page)
            os.remove(wm_path)
        out_path = "watermarked_questions.pdf"
        with open(out_path, "wb") as f:
            writer.write(f)
        return out_path

    if wm_input:
        try:
            lines = wm_input.strip().splitlines()
            wm_texts = []
            for line in lines:
                txt, count = line.split(",")
                wm_texts.extend([txt.strip()] * int(count))

            if len(wm_texts) != len(problem_indices):
                st.error("⚠️ 워터마크 개수와 문제 페이지 수가 일치하지 않습니다.")
            else:
                if st.button("🖋️ 워터마크 적용 및 문제 저장"):
                    out_pdf = apply_watermarks(merged_path, wm_texts)
                    with open(out_pdf, "rb") as f:
                        st.download_button("📄 문제 PDF 다운로드", f.read(), file_name="questions_watermarked.pdf")
        except Exception as e:
            st.error(f"입력 오류: {e}")
