import streamlit as st
from google import genai

st.set_page_config(page_title="우리 팀 스몰 제미나이", page_icon="🤖")
st.title("🤖 우리 팀 스몰 제미나이")
st.write("---")

if "GEMINI_API_KEY" in st.secrets:
    api_key = st.secrets["GEMINI_API_KEY"].strip()
    client = genai.Client(api_key=api_key)
    
    # 1. 내 API 키로 현재 실제 사용 가능한 모델 목록을 구글에서 직접 불러오기
    try:
        model_list = []
        for m in client.models.list():
            # 모델 이름에서 앞쪽 'models/' 접두사 제거
            name = m.name.replace("models/", "") if hasattr(m, "name") else str(m)
            model_list.append(name)
    except Exception as e:
        model_list = []
        st.error(f"모델 목록을 불러오지 못했습니다: {e}")

    if model_list:
        # 2. 내 계정에서 사용 가능한 모델을 드롭다운으로 선택
        selected_model = st.selectbox("현재 계정에서 사용 가능한 모델 목록:", model_list)
        
        user_input = st.text_input("Gemini에게 질문을 입력하세요:", placeholder="예: 안녕? 오늘 기분 어때?")
        
        if user_input:
            with st.spinner("답변을 생성 중입니다..."):
                try:
                    response = client.models.generate_content(
                        model=selected_model,
                        contents=user_input
                    )
                    st.success(f"답변 도착! (선택된 모델: {selected_model})")
                    st.write(response.text)
                except Exception as e:
                    st.error("⚠️ API 호출 중 에러가 발생했습니다:")
                    st.code(str(e))
    else:
        st.warning("불러올 수 있는 활성화된 모델이 없습니다. API 키 상태를 확인해 주세요.")
else:
    st.error("⚠️ Streamlit Cloud Secrets에 GEMINI_API_KEY가 설정되지 않았습니다.")
