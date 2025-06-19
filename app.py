import streamlit as st
from PyPDF2 import PdfReader, PdfWriter
from PIL import Image
import tempfile, fitz
from streamlit_js_eval import streamlit_js_eval
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from streamlit_drawable_canvas import st_canvas
from io import BytesIO

# ------------------- 설정 -------------------
st.set_page_config(page_title="KONG PDF", layout="wide")

if "step" not in st.session_state:
    st.session_state.step = 1
if "sorted_files" not in st.session_state:
    st.session_state.sorted_files = []
if "answer_indices" not in st.session_state:
    st.session_state.answer_indices = set()
if "merged_pdf_path" not in st.session_state:
    st.session_state.merged_pdf_path = None
if "NanumFontLoaded" not in st.session_state:
    pdfmetrics.registerFont(TTFont("Nanum", "NanumBarunGothic.ttf"))
    st.session_state.NanumFontLoaded = True
if "tab_selection" not in st.session_state:
    st.session_state.tab_selection = "PDF 문제/답지 도구"

# ------------------- 헤더 출력 -------------------
cols = st.columns([1, 6])
with cols[0]:
    st.image("logo.png", width=80)
with cols[1]:
    st.markdown("<h1 style='margin-bottom:0;'>KONG PDF</h1>", unsafe_allow_html=True)

# ------------------- 탭 선택 (사이드바 기반) -------------------
tab_selection = st.sidebar.radio("기능 선택", ["PDF 문제/답지 도구", "PDF 필기"])
st.session_state.tab_selection = tab_selection

# ------------------- PDF 문제/답지 도구 -------------------
if tab_selection == "PDF 문제/답지 도구":
    if st.session_state.step == 1:
        st.header("1단계: PDF 파일 업로드")

        uploaded = st.file_uploader("PDF 파일을 업로드하세요 (여러 개 가능)", type=["pdf"], accept_multiple_files=True)

        if uploaded:
            st.session_state.uploaded_files = uploaded
            st.session_state.sorted_files = uploaded

        if st.session_state.sorted_files:
            st.subheader("PDF 파일 순서")
            for i, file in enumerate(st.session_state.sorted_files, 1):
                st.markdown(f"**{i}. {file.name}**")

            if st.button("다음 단계로 ▶️"):
                st.session_state.step = 2
                st.rerun()

    elif st.session_state.step == 2:
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

        if thumbs:
            reader = PdfReader(merged_path)
            writer = PdfWriter()
            for i in sorted(st.session_state.answer_indices):
                writer.add_page(reader.pages[i])
            temp_ans = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
            with open(temp_ans.name, "wb") as f:
                writer.write(f)

            with open(temp_ans.name, "rb") as f:
                st.download_button("📥 답지 PDF 저장", data=f.read(), file_name="answers.pdf", key="download_answer")

            if st.button("다음 단계로 ▶️"):
                st.session_state.step = 3
                st.rerun()

    elif st.session_state.step == 3:
        st.header("3단계: 문제 페이지에 워터마크 삽입")

        wm_input = st.text_area("한 줄에 텍스트, 장수 입력 (예: 일요일, 1)")
        problem_indices = sorted(set(range(len(PdfReader(st.session_state.merged_pdf_path).pages))) - st.session_state.answer_indices)
        st.info(f"💡 총 {len(problem_indices)}개의 문제 페이지가 있습니다. 페이지의 합이 {len(problem_indices)}가 되도록 입력해주세요.")

        def create_watermark_page(text, font_size=20, x=250, y=400):
            buffer = BytesIO()
            c = canvas.Canvas(buffer, pagesize=letter)
            c.setFillGray(0.4, 0.4)
            c.setFont("Nanum", font_size)
            c.drawCentredString(x, y, text)
            c.save()
            buffer.seek(0)
            return PdfReader(buffer).pages[0]

        def apply_watermarks(input_pdf_path, output_pdf_path, wm_texts):
            reader = PdfReader(input_pdf_path)
            writer = PdfWriter()
            problem_indices = sorted(set(range(len(reader.pages))) - st.session_state.answer_indices)
            for i, idx in enumerate(problem_indices):
                page = reader.pages[idx]
                wm_page = create_watermark_page(f"{i+1} {wm_texts[i]}")
                page.merge_page(wm_page)
                writer.add_page(page)
            with open(output_pdf_path, "wb") as f:
                writer.write(f)

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
                        temp_out = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
                        apply_watermarks(st.session_state.merged_pdf_path, temp_out.name, wm_texts)
                        with open(temp_out.name, "rb") as f:
                            st.download_button("📄 문제 (워터마크 포함) 저장", f.read(), file_name="questions_watermarked.pdf")
            except Exception as e:
                st.error(f"입력 오류: {e}")

# ------------------- PDF 필기 -------------------
elif tab_selection == "PDF 필기":
    st.header("✏️ PDF 페이지에 직접 필기하기")

    with st.sidebar:
        pdf_file = st.file_uploader("📄 PDF 업로드", type=["pdf"], key="annotate_pdf")
        if pdf_file:
            st.session_state.pdf_file_bytes = pdf_file.read()
            st.session_state.pdf_page = 0

        st.markdown("---")
        st.markdown("🖌️ **펜 설정**")
        st.session_state["drawing_mode"] = st.selectbox("도구 선택", ("freedraw", "line", "rect", "circle", "transform", "point"))
        st.session_state["stroke_width"] = st.slider("펜 굵기", 1, 25, 3)
        if st.session_state["drawing_mode"] == 'point':
            st.session_state["point_display_radius"] = st.slider("포인트 반지름", 1, 25, 3)
        st.session_state["stroke_color"] = st.color_picker("펜 색상", "#ff0000")
        st.session_state["realtime_update"] = st.checkbox("실시간 반영", True)

    if "pdf_file_bytes" in st.session_state:
        doc = fitz.open(stream=st.session_state.pdf_file_bytes, filetype="pdf")

        if "pdf_page" not in st.session_state:
            st.session_state.pdf_page = 0

        col1, col2 = st.columns(2)
        with col1:
            if st.button("⬅ 이전"):
                st.session_state.pdf_page = max(0, st.session_state.pdf_page - 1)
        with col2:
            if st.button("다음 ➡"):
                st.session_state.pdf_page = min(len(doc) - 1, st.session_state.pdf_page + 1)

        page = doc[st.session_state.pdf_page]
        pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5))
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples).convert("RGBA")

        st_canvas(
            fill_color="rgba(255, 165, 0, 0.3)",
            stroke_width=st.session_state.get("stroke_width", 3),
            stroke_color=st.session_state.get("stroke_color", "#ff0000"),
            background_image=img,
            update_streamlit=st.session_state.get("realtime_update", True),
            height=img.height,
            width=img.width,
            drawing_mode=st.session_state.get("drawing_mode", "freedraw"),
            point_display_radius=st.session_state.get("point_display_radius", 3),
            key=f"canvas_{st.session_state.pdf_page}"
        )
    else:
        st.info("사이드바에서 PDF를 업로드해 주세요.")
