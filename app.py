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
    page_title="세스코 맞춤 단가 & 견적 안내 AI",
    page_icon="💎",
    layout="wide"
)

# 세련된 웹앱 UI 스타일링
st.markdown("""
<style>
    .main { padding: 1.5rem 2rem; }
    
    /* 상담 신청 폼 박스 스타일 */
    .lead-box {
        background-color: #f0f7ff;
        border: 1px solid #bae0ff;
        border-radius: 12px;
        padding: 1.2rem;
        margin-top: 1rem;
        margin-bottom: 1.5rem;
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
# 2. 마스터 데이터 및 상담 리드 I/O 함수
# ==========================================
DATA_FILE_PATH = "saved_data_context.txt"
NAME_FILE_PATH = "saved_data_name.txt"
LEADS_FILE_PATH = "saved_leads.csv"

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

def save_lead_data(name, phone, space, memo):
    """고객 상담 신청 내역 저장"""
    new_data = pd.DataFrame([{
        "신청일시": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"),
        "고객명": name,
        "연락처": phone,
        "매장평수/규모": space,
        "문의요청사항": memo
    }])
    if os.path.exists(LEADS_FILE_PATH):
        old_df = pd.read_csv(LEADS_FILE_PATH)
        df = pd.concat([old_df, new_data], ignore_index=True)
    else:
        df = new_data
    df.to_csv(LEADS_FILE_PATH, index=False, encoding="utf-8-sig")

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
# 3. 사이드바 (설정, 다운로드, 관리자 리드 관리)
# ==========================================
with st.sidebar:
    st.header("⚙️ 서비스 설정")
    
    role_option = st.selectbox(
        "AI 프롬프트 모드:",
        ["견적 & 요금 비교 전문가", "비즈니스 마케팅 컨설턴트", "자유 질문 모드"]
    )
    
    if role_option == "견적 & 요금 비교 전문가":
        base_instruction = (
            "당신은 세스코 견적 및 요금 안내 전문 컨설턴트입니다.\n"
            "등록된 단가표 데이터를 바탕으로 정확한 제품명, 스펙, 요금을 안내하세요.\n"
            "이미지가 첨부된 경우 이미지(해충/매장/주방 사진)를 분석하여 해당 문제를 진단하고, 필요한 서비스와 가격을 추천하세요.\n"
            "가격 문의 시 **'단독가', '결합가', '프로모션가'**가 존재하는 경우, "
            "이를 한눈에 볼 수 있도록 마크다운 표(Table)로 명확히 비교하고 적용 조건을 안내하세요."
        )
    elif role_option == "비즈니스 마케팅 컨설턴트":
        base_instruction = (
            "당신은 세스코 서비스 비즈니스 마케팅 컨설턴트입니다.\n"
            "등록된 단가 및 서비스 특징, 첨부 이미지를 바탕으로 설득력 있는 고객 제안서를 작성하세요."
        )
    else:
        base_instruction = "당신은 유능하고 친절한 AI 비즈니스 보조입니다."

    st.divider()
    
    st.subheader("📊 학습 데이터 상태")
    if uploaded_filename:
        st.success(f"**적용 중:** `{uploaded_filename}`")
    else:
        st.info("현재 등록된 마스터 파일이 없습니다.")

    st.divider()
    
    # 상담 내역 다운로드
    st.subheader("📥 견적 상담 내역 저장")
    if "messages" in st.session_state and len(st.session_state.messages) > 0:
        chat_export_text = "=== 세스코 AI 견적 상담 내역 ===\n\n"
        for msg in st.session_state.messages:
            role_label = "고객" if msg["role"] == "user" else "세스코 AI"
            chat_export_text += f"[{role_label}]\n{msg['content']}\n\n" + "-"*40 + "\n\n"
            
        st.download_button(
            label="📄 상담 대화 내역 다운로드 (.txt)",
            data=chat_export_text,
            file_name="세스코_상담내역.txt",
            mime="text/plain",
            use_container_width=True
        )

    st.divider()
    
    # 관리자 패널
    st.subheader("🔑 관리자 패널")
    admin_password_secret = st.secrets.get("ADMIN_PASSWORD", "1234")
    input_pwd = st.text_input("비밀번호 입력:", type="password")
    
    if input_pwd == admin_password_secret:
        st.success("🔓 관리자 권한 활성화됨")
        
        # 📋 [추가] 수집된 고객 상담 리드 확인 및 다운로드
        st.write("📋 **접수된 상담 신청 목록:**")
        if os.path.exists(LEADS_FILE_PATH):
            leads_df = pd.read_csv(LEADS_FILE_PATH)
            st.dataframe(leads_df, use_container_width=True)
            
            leads_csv = leads_df.to_csv(index=False, encoding="utf-8-sig")
            st.download_button(
                label="📥 상담 신청 데이터 다운로드 (.csv)",
                data=leads_csv,
                file_name="세스코_고객상담신청목록.csv",
                mime="text/csv",
                use_container_width=True
            )
        else:
            st.caption("아직 접수된 상담 신청이 없습니다.")
            
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
        st.caption("관리자만 상담 신청 데이터 및 단가표 관리가 가능합니다.")

    st.divider()
    if st.button("🔄 대화 내용 초기화", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

# ==========================================
# 4. 메인 화면 & 챗봇 인터페이스
# ==========================================
st.title("💎 세스코 맞춤 서비스 & 단가 안내 AI")

if uploaded_filename:
    st.caption(f"📌 **참조 문서:** {uploaded_filename} | 실시간 파싱 & 사진 진단 모드")
else:
    st.caption("📌 **참조 문서 없음** | 기본 지식 기반 작동 중")

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

    # FAQ 질문 추천 버튼
    selected_faq = None
    st.write("💡 **자주 묻는 질문 추천:**")
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("🔍 15평 매장 단가 비교해줘", use_container_width=True):
            selected_faq = "15평 매장 기준 추천 서비스와 단독가, 결합가, 프로모션가를 비교해서 표로 보여줘."
    with col2:
        if st.button("💡 결합 할인 조건이 뭐야?", use_container_width=True):
            selected_faq = "단독가와 결합가의 차이가 무엇이며, 결합 할인을 받기 위한 조건이 어떻게 되나요?"
    with col3:
        if st.button("🎁 이번 달 프로모션 안내해줘", use_container_width=True):
            selected_faq = "현재 진행 중인 프로모션 할인 혜택과 대상 서비스를 정리해 주세요."

    st.write("---")
    
    # 📸 [추가] 해충/매장 현장 사진 업로드 옵션
    with st.expander("📸 **해충 또는 매장 사진 첨부하여 진단받기 (선택사항)**"):
        uploaded_img = st.file_uploader("해충/현장 사진을 첨부하면 AI가 분석해 드립니다.", type=["jpg", "jpeg", "png"])
        if uploaded_img:
            st.image(uploaded_img, caption="첨부된 사진 미리보기", width=250)

    # 입력 질문 결정
    prompt_input = st.chat_input("질문을 입력하세요... (예: 사진 속 해충 어떤 서비스 받아야 해?)")
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
                "아래는 관리자가 직접 등록한 최신 서비스 단가표 데이터입니다. "
                "사용자의 요금 및 스펙 질문에는 반드시 아래 표 데이터에서 단독가, 결합가, 프로모션가를 찾아 정확하게 답변하세요:\n\n"
                f"{file_context}"
            )

        # AI 답변 생성 (이미지 포함 처리)
        with st.chat_message("assistant"):
            try:
                chat = client.chats.create(
                    model="gemini-3-flash-preview",
                    config=types.GenerateContentConfig(
                        system_instruction=final_system_instruction
                    ),
                    history=history
                )
                
                # 이미지가 첨부된 경우 텍스트와 함께 전달
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

    # 📞 [추가] 하단 간편 상담 신청 폼 (Lead Capture)
    st.write("---")
    with st.expander("📞 **맞춤 견적 방문 상담 신청하기 (전문가 무료 진단)**"):
        st.caption("상담 정보를 남겨주시면 세스코 담당 전문가가 빠른 시일 내에 연락드립니다.")
        with st.form("lead_form", clear_on_submit=True):
            col_a, col_b = st.columns(2)
            with col_a:
                c_name = st.text_input("성함/업체명 *")
                c_phone = st.text_input("연락처 * (예: 010-1234-5678)")
            with col_b:
                c_space = st.text_input("매장 평수/규모 (예: 25평 식당)")
                c_memo = st.text_input("문의 사항 (예: 주방 유충 소독 견적 원함)")
                
            submit_lead = st.form_submit_button("📩 상담 신청 제출하기", use_container_width=True)
            if submit_lead:
                if c_name and c_phone:
                    save_lead_data(c_name, c_phone, c_space, c_memo)
                    st.success("🎉 상담 신청이 정상 접수되었습니다! 담당자가 확인 후 안내해 드리겠습니다.")
                else:
                    st.warning("⚠️ 성함과 연락처는 필수 입력 항목입니다.")
else:
    st.error("⚠️ Streamlit Cloud Secrets에 GEMINI_API_KEY가 설정되지 않았습니다.")
