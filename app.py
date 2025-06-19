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

def show_header():
    cols = st.columns([1, 6])
    with cols[0]:
        st.image("logo.png", width=80)
    with cols[1]:
        st.markdown("<h1 style='margin-bottom:0;'>KONG PDF</h1>", unsafe_allow_html=True)

# ------------------- 헤더 출력 -------------------
show_header()

# ------------------- 탭 분기 -------------------
tab1, tab2 = st.tabs(["📘 문제/답지 분리 도구", "✏️ PDF 필기"])

# ------------------- PDF 문제/답지 도구 -------------------
with tab1:
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

# ------------------- PDF 필기 탭 -------------------
with tab2:
    st.header("✏️ PDF 페이지에 직접 필기하기")

    uploaded_pdf = st.file_uploader("PDF 파일 업로드 (1개만)", type=["pdf"], key="note_pdf")

    if uploaded_pdf:
        doc = fitz.open(stream=uploaded_pdf.read(), filetype="pdf")
        total_pages = len(doc)

        if "note_page_idx" not in st.session_state:
            st.session_state.note_page_idx = 0

        # 페이지 전환 버튼
        cols = st.columns([1, 5, 1])
        with cols[0]:
            if st.button("⬅ 이전"):
                if st.session_state.note_page_idx > 0:
                    st.session_state.note_page_idx -= 1
        with cols[2]:
            if st.button("다음 ➡"):
                if st.session_state.note_page_idx < total_pages - 1:
                    st.session_state.note_page_idx += 1

        page_idx = st.session_state.note_page_idx
        st.markdown(f"**페이지 {page_idx + 1} / {total_pages}**")

        page = doc.load_page(page_idx)
        #pix = page.get_pixmap(dpi=150)
        #img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5))
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        img.thumbnail((1000, 1000))  # 최대 사이즈 제한
        st.image(img, caption="디버그: 이미지 확인")

        # 펜 색상 버튼 UI
        if "pen_color" not in st.session_state:
            st.session_state.pen_color = "#000000"

        st.markdown("#### 펜 색상 선택")
        color_options = {
            "검정": "#000000",
            "파랑": "#0000FF",
            "빨강": "#FF0000"
        }
        color_cols = st.columns(len(color_options))
        for i, (label, hex_code) in enumerate(color_options.items()):
            is_selected = st.session_state.pen_color == hex_code
            button_type = "primary" if is_selected else "secondary"
            with color_cols[i]:
                if st.button(label, key=f"pen_btn_{label}", type=button_type):
                    st.session_state.pen_color = hex_code

        # 필기 캔버스
        img = img.convert("RGBA")

        canvas_result = st_canvas(
            #fill_color="rgba(255, 255, 255, 0)",
            background_image=img.copy(),
            height=img.height,
            width=img.width,
            stroke_color=st.session_state.pen_color,
            stroke_width=3,
            drawing_mode="freedraw",
            key=f"canvas_{page_idx}",
        )

        # 필기 결과 저장
        if "drawn_images" not in st.session_state:
            st.session_state.drawn_images = {}
        if canvas_result.image_data is not None:
            st.session_state.drawn_images[page_idx] = Image.fromarray(canvas_result.image_data.astype("uint8"))

        # 전체 PDF로 저장
        if st.button("📄 모든 필기 저장 (PDF)"):
            writer = PdfWriter()
            for i in range(total_pages):
                page = doc.load_page(i)
                pix = page.get_pixmap(dpi=150)
                base_img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

                if i in st.session_state.drawn_images:
                    overlay = st.session_state.drawn_images[i].convert("RGBA").resize(base_img.size)
                    combined = Image.alpha_composite(base_img.convert("RGBA"), overlay)
                else:
                    combined = base_img

                buffer = BytesIO()
                combined.convert("RGB").save(buffer, format="PDF")
                buffer.seek(0)
                temp_pdf = PdfReader(buffer)
                writer.add_page(temp_pdf.pages[0])

            final_output = BytesIO()
            writer.write(final_output)
            final_output.seek(0)
            st.download_button("💾 전체 필기 PDF 저장", data=final_output, file_name="annotated_all_pages.pdf")
