import os
import pandas as pd
from pypdf import PdfReader
from PIL import Image
import streamlit as st
from google import genai
from google.genai import types

# ==========================================
# 1. 페이지 기본 설정 및 커스텀 CSS
# ==========================================
st.set_page_config(
    page_title="영업팀 전용 AI 단가 & 견적 지원 시스템",
    page_icon="💼",
    layout="wide"
)

# 세련된 웹앱 UI 스타일링
st.markdown("""
<style>
    .main { padding: 1.5rem 2rem; }
    
    /* 제안서 생성 박스 스타일 */
    .proposal-box {
        background-color: #f0fdf4;
        border: 1px solid #bbf7d0;
        border-radius: 12px;
        padding: 1.2rem;
        margin-top: 1rem;
        margin-bottom: 1rem;
    }
    
    /* 마크다운 표 디자인 커스텀 */
    div[data-testid="stMarkdownContainer"] table {
        width: 100% !important;
        border-collapse: collapse !important;
        margin: 1rem 0 !important;
        font-size: 14.5px !important;
        border-radius: 8px !important;
        overflow: hidden !important;
        box-shadow: 0 2px 5px rgba(0,0,0,0.05) !important;
    }
    div[data-testid="stMarkdownContainer"] th {
        background-color: #0f172a !important;
        color: #ffffff !important;
        font-weight: 600 !important;
        padding: 12px 16px !important;
        border: 1px solid #1e293b !important;
        text-align: center !important;
    }
    div[data-testid="stMarkdownContainer"] td {
        padding: 11px 16px !important;
        border: 1px solid #e2e8f0 !important;
        vertical-align: middle !important;
    }
    div[data-testid="stMarkdownContainer"] tr:nth-child(even) {
        background-color: #f8fafc !important;
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 2. 마스터 데이터 및 영업일지 I/O 함수
# ==========================================
DATA_FILE_PATH = "saved_data_context.txt"
NAME_FILE_PATH = "saved_data_name.txt"
SALES_LOG_PATH = "sales_activity_log.csv"

def load_master_data():
    if os.path.exists(DATA_FILE_PATH) and os.path.exists(NAME_FILE_PATH):
        with open(DATA_FILE_PATH, "r", encoding="utf-8") as f:
            context = f.read()
        with open(NAME_FILE_PATH, "r", encoding="utf-8") as f:
            filename = f.read()
        return context, filename
    return "", None

def save_master_data(context, filename):
    with open(DATA_FILE_PATH, "w", encoding="utf-8") as f:
        f.write(context)
    with open(NAME_FILE_PATH, "w", encoding="utf-8") as f:
        f.write(filename)

def delete_master_data():
    if os.path.exists(DATA_FILE_PATH):
        os.remove(DATA_FILE_PATH)
    if os.path.exists(NAME_FILE_PATH):
        os.remove(NAME_FILE_PATH)

def save_sales_log(member_name, client_name, proposed_deal, reaction, memo):
    """팀원의 영업 미팅 일지 저장"""
    new_data = pd.DataFrame([{
        "작성일시": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"),
        "담당팀원": member_name,
        "고객/매장명": client_name,
        "제안서비스/견적가": proposed_deal,
        "고객반응/상태": reaction,
        "영업메모": memo
    }])
    if os.path.exists(SALES_LOG_PATH):
        old_df = pd.read_csv(SALES_LOG_PATH)
        df = pd.concat([old_df, new_data], ignore_index=True)
    else:
        df = new_data
    df.to_csv(SALES_LOG_PATH, index=False, encoding="utf-8-sig")

def process_file_content(uploaded_file):
    extracted_text = ""
    filename = uploaded_file.name

    if filename.endswith(('.xlsx', '.xls')):
        df = pd.read_excel(uploaded_file, sheet_name=0)
        df = df.dropna(how="all")
        extracted_text = df.to_markdown(index=False)
        
    elif filename.endswith('.csv'):
        df = pd.read_csv(uploaded_file)
        df = df.dropna(how="all")
        extracted_text = df.to_markdown(index=False)
        
    elif filename.endswith('.pdf'):
        reader = PdfReader(uploaded_file)
        for idx, page in enumerate(reader.pages, start=1):
            extracted_text += f"\n[PDF Page {idx}]\n" + page.extract_text() + "\n"

    return extracted_text, filename

file_context, uploaded_filename = load_master_data()

# ==========================================
# 3. 사이드바 (설정, 관리자 영업일지 관리)
# ==========================================
with st.sidebar:
    st.header("⚙️ 영업 모드 설정")
    
    role_option = st.selectbox(
        "AI 영업 파트너 모드:",
        ["견적 & 요금 비교 전문가", "거절 대응 & 셀링포인트 안내", "자유 질문 모드"]
    )
    
    if role_option == "견적 & 요금 비교 전문가":
        base_instruction = (
            "당신은 영업 팀원을 보조하는 세스코 견적 및 요금 안내 전문 컨설턴트입니다.\n"
            "등록된 단가표 데이터를 바탕으로 정확한 제품명, 스펙, 요금을 팀원에게 신속히 안내하세요.\n"
            "팀원이 영업 현장에서 고객에게 바로 보여줄 수 있도록 단독가, 결합가, 프로모션가를 마크다운 표(Table)로 깔끔하게 정리하세요."
        )
    elif role_option == "거절 대응 & 셀링포인트 안내":
        base_instruction = (
            "당신은 베테랑 영업 멘토입니다.\n"
            "팀원이 현장에서 고객의 거절 반응(예: '너무 비싸요', '타사 쓸게요')을 입력하면, "
            "설득력 있는 반박 논리, 타사 대비 강점, 세스코의 핵심 셀링 포인트를 3가지로 정리해서 알려주세요."
        )
    else:
        base_instruction = "당신은 유능하고 친절한 AI 영업 보조입니다."

    st.divider()
    
    st.subheader("📊 학습 단가표 상태")
    if uploaded_filename:
        st.success(f"**적용 중:** `{uploaded_filename}`")
    else:
        st.info("현재 등록된 마스터 단가표가 없습니다.")

    st.divider()
    
    # 관리자 패널
    st.subheader("🔑 관리자 패널")
    admin_password_secret = st.secrets.get("ADMIN_PASSWORD", "1234")
    input_pwd = st.text_input("비밀번호 입력:", type="password")
    
    if input_pwd == admin_password_secret:
        st.success("🔓 관리자 권한 활성화됨")
        
        # 📋 팀 전체 영업일지 모아보기
        st.write("📋 **팀원 현장 영업 기록 대장:**")
        if os.path.exists(SALES_LOG_PATH):
            logs_df = pd.read_csv(SALES_LOG_PATH)
            st.dataframe(logs_df, use_container_width=True)
            
            logs_csv = logs_df.to_csv(index=False, encoding="utf-8-sig")
            st.download_button(
                label="📥 영업일지 전체 다운로드 (.csv)",
                data=logs_csv,
                file_name="팀_영업활동기록대장.csv",
                mime="text/csv",
                use_container_width=True
            )
        else:
            st.caption("아직 기록된 영업일지가 없습니다.")
            
        st.divider()
        
        # 단가표 관리
        new_file = st.file_uploader("새 단가표 (시트 1 작성 엑셀/PDF)", type=["xlsx", "csv", "pdf"])
        if new_file and st.button("💾 마스터 데이터로 반영", use_container_width=True):
            try:
                with st.spinner("단가표 분석 및 저장 중..."):
                    parsed_text, fname = process_file_content(new_file)
                    save_master_data(parsed_text, fname)
                    st.toast("✅ 새 마스터 단가표 적용 완료!", icon="🎉")
                    st.rerun()
            except Exception as e:
                st.error(f"⚠️ 파일 처리 오류: {e}")
                
        if uploaded_filename and st.button("🗑️ 등록 데이터 삭제", use_container_width=True, type="secondary"):
            delete_master_data()
            st.toast("등록 데이터 삭제 완료!", icon="🧹")
            st.rerun()
    elif input_pwd:
        st.error("비밀번호 불일치")
    else:
        st.caption("관리자만 영업일지 총괄 및 단가표 관리가 가능합니다.")

    st.divider()
    if st.button("🔄 대화 내용 초기화", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

# ==========================================
# 4. 메인 화면 & 챗봇 인터페이스
# ==========================================
st.title("💼 우리 팀 세스코 영업지원 AI 시스템")

if uploaded_filename:
    st.caption(f"📌 **참조 단가표:** {uploaded_filename} | 영업 현장 실시간 지원 작동 중")
else:
    st.caption("📌 **참조 단가표 없음** | 기본 지식 기반 작동 중")

st.divider()

# API 키 확인 및 메시지 처리
if "GEMINI_API_KEY" in st.secrets:
    api_key = st.secrets["GEMINI_API_KEY"].strip()
    client = genai.Client(api_key=api_key)

    if "messages" not in st.session_state:
        st.session_state.messages = []

    # 이전 대화 메시지 출력
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # 팀원 자주 쓰는 영업 질문 퀵 버튼
    selected_faq = None
    st.write("💡 **영업 현장 빠른 단가 조회:**")
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("🔍 15평 매장 단독/결합가 비교", use_container_width=True):
            selected_faq = "15평 매장 기준 추천 서비스와 단독가, 결합가, 프로모션가를 비교해서 고객 브리핑용 표로 보여줘."
    with col2:
        if st.button("🛡️ 타사 대비 핵심 강점 보기", use_container_width=True):
            selected_faq = "고객이 타사(사설 업체 등) 가격과 비교할 때 설득할 수 있는 세스코만의 핵심 차별점 3가지를 정리해줘."
    with col3:
        if st.button("🎁 이번 달 프로모션 혜택", use_container_width=True):
            selected_faq = "현재 고객에게 적용할 수 있는 프로모션 할인 혜택과 조건 단가를 보여줘."

    st.write("---")
    
    # 📸 현장 사진 분석 (해충/매장)
    with st.expander("📸 **현장 해충/매장 사진으로 바로 서비스 추천받기**"):
        uploaded_img = st.file_uploader("현장 사진을 첨부하면 AI가 적합한 서비스를 진단해 줍니다.", type=["jpg", "jpeg", "png"])
        if uploaded_img:
            st.image(uploaded_img, caption="첨부된 현장 사진", width=250)

    # 입력 질문 결정
    prompt_input = st.chat_input("팀원 질문 입력... (예: 25평 식당에 바이러스케어 결합하면 얼마야?)")
    user_prompt = selected_faq if selected_faq else prompt_input

    if user_prompt:
        st.chat_message("user").markdown(user_prompt)
        st.session_state.messages.append({"role": "user", "content": user_prompt})

        history = []
        for msg in st.session_state.messages[:-1]:
            role = "user" if msg["role"] == "user" else "model"
            history.append({"role": role, "parts": [{"text": msg["content"]}]})

        final_system_instruction = base_instruction
        if file_context:
            final_system_instruction += (
                f"\n\n[참조 마스터 데이터 (파일명: {uploaded_filename})]\n"
                "아래는 최신 마스터 단가표 데이터입니다. 팀원의 질문에 단독가, 결합가, 프로모션가를 정확하게 찾아 답변하세요:\n\n"
                f"{file_context}"
            )

        # AI 답변 생성
        with st.chat_message("assistant"):
            try:
                chat = client.chats.create(
                    model="gemini-3-flash-preview",
                    config=types.GenerateContentConfig(
                        system_instruction=final_system_instruction
                    ),
                    history=history
                )
                
                if uploaded_img:
                    img_obj = Image.open(uploaded_img)
                    send_contents = [user_prompt, img_obj]
                else:
                    send_contents = user_prompt

                response_stream = chat.send_message_stream(send_contents)
                
                def stream_generator():
                    for chunk in response_stream:
                        yield chunk.text

                full_response = st.write_stream(stream_generator())
                st.session_state.messages.append({"role": "assistant", "content": full_response})
                st.rerun()
            except Exception as e:
                st.error(f"⚠️ 답변 생성 실패: {e}")

    # ==========================================
    # 📱 [영업팀 전용 기능 1] 카톡/문자 제안서 자동 생성
    # ==========================================
    st.write("---")
    if len(st.session_state.messages) > 0:
        if st.button("📱 **현재 상담 내용 1초만에 카톡/문자 제안서로 만들기**", use_container_width=True):
            with st.spinner("고객 전송용 카톡/문자 요약문 작성 중..."):
                recent_chat = st.session_state.messages[-1]["content"]
                summary_prompt = (
                    f"다음 상담 내용을 바탕으로 고객에게 카카오톡이나 문자로 바로 전송할 수 있는 "
                    f"친절하고 정중한 견적 요약 메시지를 작성해 줘.\n\n"
                    f"상담 내용:\n{recent_chat}"
                )
                
                chat = client.chats.create(model="gemini-3-flash-preview")
                res = chat.send_message(summary_prompt)
                
                st.subheader("📱 **고객 전송용 카톡/문자 메시지 (복사해서 전송하세요)**")
                st.code(res.text, language="text")

    # ==========================================
    # 📝 [영업팀 전용 기능 2] 현장 영업일지 기록
    # ==========================================
    with st.expander("📝 **팀원 현장 영업 미팅 일지 기록하기**"):
        st.caption("오늘 방문한 매장/고객과의 상담 내역을 기록하면 팀 전체 영업 대장에 저장됩니다.")
        with st.form("sales_log_form", clear_on_submit=True):
            col_a, col_b = st.columns(2)
            with col_a:
                m_name = st.text_input("담당 팀원 이름 *")
                c_name = st.text_input("방문 매장/고객명 *")
                p_deal = st.text_input("제안 서비스 및 견적가 (예: 방제+바이러스 결합 월 65,000원)")
            with col_b:
                reaction = st.selectbox("고객 반응/상태", ["긍정적 (계약 임박)", "검토 중 (재방문 필요)", "보류 (가격 부담)", "계약 완료 🎉"])
                memo = st.text_input("영업 메모 (예: 다음 주 화요일에 사장님 재방문 예정)")
                
            submit_log = st.form_submit_button("💾 영업일지 저장하기", use_container_width=True)
            if submit_log:
                if m_name and c_name:
                    save_sales_log(m_name, c_name, p_deal, reaction, memo)
                    st.success("🎉 영업일지가 성공적으로 저장되었습니다! 팀 대장에 자동 합산됩니다.")
                else:
                    st.warning("⚠️ 담당 팀원 이름과 매장/고객명은 필수 입력 항목입니다.")
else:
    st.error("⚠️ Streamlit Cloud Secrets에 GEMINI_API_KEY가 설정되지 않았습니다.")
