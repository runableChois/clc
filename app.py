import streamlit as st
from google import genai

st.set_page_config(page_title="우리 팀 스몰 제미나이", page_icon="🤖")
st.title("🤖 우리 팀 스몰 제미나이")
st.write("---")

if "GEMINI_API_KEY" in st.secrets:
    api_key = st.secrets["GEMINI_API_KEY"].strip()
    client = genai.Client(api_key=api_key)
    
    # 1. 404 에러를 일으키는 만료/미지원 모델 자동 제외 필터링
    valid_models = []
    try:
        for m in client.models.list():
            name = m.name.replace("models/", "") if hasattr(m, "name") else str(m)
            
            # 텍스트 생성 지원 모델 중 만료된 preview/2.5-flash 등 제외
            methods = getattr(m, "supported_generation_methods", [])
            if "generateContent" in methods:
                if "2.5-flash" not in name and "preview" not in name:
                    valid_models.append(name)
    except Exception as e:
        st.error(f"모델 목록 불러오기 실패: {e}")

    if valid_models:
        # 가장 안정적인 gemini-1.5-flash 또는 첫 번째 정상 모델을 기본 선택
        default_idx = 0
        for idx, m_name in enumerate(valid_models):
            if "1.5-flash" in m_name:
                default_idx = idx
                break
                
        selected_model = st.selectbox(
            "사용할 Gemini 모델 (404 발생 모델 자동 제외됨):", 
            valid_models,
            index=default_idx
        )
        
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
                    st.error("⚠️ 호출 에러 발생. 드롭다운에서 다른 모델을 선택해 보세요:")
                    st.code(str(e))
    else:
        st.error("⚠️ 사용 가능한 정상 모델을 찾지 못했습니다.")
else:
    st.error("⚠️ Streamlit Cloud Secrets에 GEMINI_API_KEY가 설정되지 않았습니다.")
