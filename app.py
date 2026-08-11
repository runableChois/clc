import io
import json
import os
import re
import urllib.request

from PIL import Image, ImageDraw, ImageFont
from google import genai
from google.genai import types
import pandas as pd
from pypdf import PdfReader
import streamlit as st
import streamlit.components.v1 as components

# ==========================================
# 1. 페이지 기본 설정 및 모바일 UI 최적화 CSS
# ==========================================
st.set_page_config(
    page_title="세스코 경기서북부 플래너 AI (Pro)",
    page_icon="💼",
    layout="wide"
)

# Streamlit Cloud 배지, 헤더, 푸터 완전 은닉 스크립트
components.html("""
<script>
    function removeStreamlitBadgesOnly() {
        try {
            const parentDoc = window.parent.document;
            const selectors = [
                'footer',
                '#MainMenu',
                '[data-testid="stStatusWidget"]',
                '[data-testid="stDecoration"]',
                '[class*="viewerBadge"]',
                '[class*="stAppDeployButton"]',
                'div[class*="styles_viewerBadge"]',
                'div[class*="ViewerBadge"]',
                'button[title="View app in Streamlit Community Cloud"]'
            ];
            selectors.forEach(selector => {
                const elements = parentDoc.querySelectorAll(selector);
                elements.forEach(el => {
                    el.style.display = 'none';
                    el.style.visibility = 'hidden';
                });
            });
        } catch (e) { console.log(e); }
    }
    setInterval(removeStreamlitBadgesOnly, 300);
</script>
""", height=0, width=0)

st.markdown("""
<style>
    footer {display: none !important; visibility: hidden !important;}
    #MainMenu {display: none !important;}
    .stAppDeployButton {display: none !important;}
    div[data-testid="stDecoration"] {display: none !important;}
    div[data-testid="stStatusWidget"] {display: none !important;}
    div[class*="viewerBadge"] {display: none !important;}
    
    div[data-testid="stHeader"] {
        background-color: transparent !important;
        z-index: 100 !important;
    }
    
    [data-testid="collapsedControl"], [data-testid="stSidebarCollapseButton"] {
        display: flex !important;
        visibility: visible !important;
        color: #ffffff !important;
        background-color: #003b7a !important;
        border-radius: 8px !important;
        padding: 4px !important;
        margin-top: 5px !important;
        margin-left: 5px !important;
        box-shadow: 0 2px 5px rgba(0,0,0,0.2) !important;
    }
    
    [data-testid="collapsedControl"] button, [data-testid="stSidebarCollapseButton"] button {
        color: #ffffff !important;
    }

    .main .block-container {
        padding-top: 2.5rem !important;
        padding-bottom: 2rem !important;
    }
    
    @media (max-width: 768px) {
        .main .block-container {
            padding-left: 0.8rem !important;
            padding-right: 0.8rem !important;
        }
        h1 { font-size: 1.4rem !important; }
        div[data-testid="stMarkdownContainer"] table { font-size: 12px !important; }
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 2. 이미지 생성 엔진 (카톡 고화질 견적 카드용)
# ==========================================
FONT_PATH = "NanumGothic-Bold.ttf"

def ensure_korean_font():
    """한글 폰트(나눔고딕) 자동 다운로드 처리"""
    if not os.path.exists(FONT_PATH):
        font_url = "https://github.com/google/fonts/raw/main/ofl/nanumgothic/NanumGothic-Bold.ttf"
        try:
            urllib.request.urlretrieve(font_url, FONT_PATH)
        except Exception as e:
            st.error(f"폰트 다운로드 실패: {e}")

def create_high_res_quote_card(card_data):
    """1200x1600 초고해상도 완제품 이미지 카드 생성"""
    ensure_korean_font()
    width, height = 1200, 1600
    img = Image.new('RGB', (width, height), color='#f1f5f9')
    draw = ImageDraw.Draw(img)
    
    try:
        font_brand = ImageFont.truetype(FONT_PATH, 48)
        font_subhead = ImageFont.truetype(FONT_PATH, 24)
        font_title = ImageFont.truetype(FONT_PATH, 34)
        font_item_name = ImageFont.truetype(FONT_PATH, 30)
        font_price = ImageFont.truetype(FONT_PATH, 36)
        font_regular = ImageFont.truetype(FONT_PATH, 24)
        font_small = ImageFont.truetype(FONT_PATH, 20)
    except Exception:
        font_brand = font_subhead = font_title = font_item_name = font_price = font_regular = font_small = ImageFont.load_default()

    # 상단 헤더 영역
    draw.rectangle([(0, 0), (width, 200)], fill='#003b7a')
    draw.rectangle([(0, 190), (width, 200)], fill='#00a3e0') 
    
    draw.text((60, 45), "💎 CESCO 맞춤 솔루션 견적서", fill='#ffffff', font=font_brand)
    draw.text((60, 125), "세스코 공식 문서 기반 | 현장 맞춤 케어 제안", fill='#dbeafe', font=font_subhead)

    # 견적 제목 영역
    draw.rectangle([(50, 240), (width - 50, 370)], fill='#ffffff', outline='#cbd5e1', width=2)
    title_text = card_data.get("title", "맞춤 위생 솔루션 견적")
    draw.text((80, 268), title_text[:30], fill='#0f172a', font=font_title)
    
    subtitle_text = card_data.get("subtitle", "공식 문서 데이터 기준")
    draw.text((80, 320), subtitle_text[:40], fill='#64748b', font=font_regular)

    # 서비스 항목 카드 출력
    items = card_data.get("items", [])
    y_offset = 400
    for item in items[:4]:
        draw.rectangle([(50, y_offset), (width - 50, y_offset + 140)], fill='#ffffff', outline='#e2e8f0', width=2)
        
        name = item.get("name", "서비스 항목")
        note = item.get("note", "")
        price = item.get("price", "상담가")

        draw.text((80, y_offset + 30), name[:20], fill='#0f172a', font=font_item_name)
        if note:
            draw.text((80, y_offset + 80), note[:28], fill='#64748b', font=font_small)

        draw.rectangle([(width - 380, y_offset + 30), (width - 80, y_offset + 110)], fill='#eff6ff', outline='#bfdbfe', width=1)
        draw.text((width - 360, y_offset + 48), price, fill='#003b7a', font=font_price)
        
        y_offset += 160

    # 프로모션 배너
    promo_text = card_data.get("promotion", "")
    if promo_text:
        draw.rectangle([(50, y_offset + 10), (width - 50, y_offset + 180)], fill='#e0f2fe', outline='#0284c7', width=2)
        draw.text((80, y_offset + 35), "🎁 특별 프로모션 & 결합 혜택", fill='#0369a1', font=font_title)
        draw.text((80, y_offset + 105), promo_text[:45], fill='#0f172a', font=font_regular)

    # 하단 푸터
    draw.rectangle([(0, height - 130), (width, height)], fill='#0f172a')
    draw.text((60, height - 95), "📞 서비스 문의 및 신청: 세스코 담당 플래너", fill='#ffffff', font=font_regular)
    
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return buf.getvalue()

# ==========================================
# 3. 데이터 I/O 및 누적 문서 학습 (RAG) 함수
# ==========================================
KNOWLEDGE_BASE_PATH = "cesco_knowledge_base.txt"
KNOWLEDGE_FILES_PATH = "cesco_knowledge_files_list.txt"
SALES_LOG_PATH = "sales_activity_log.csv"
EQUIPMENT_LOG_PATH = "team_equipment_inventory.csv"

def load_knowledge_data():
    """누적 학습 텍스트 및 학습 파일 목록 로드"""
    context = ""
    file_list_str = ""
    if os.path.exists(KNOWLEDGE_BASE_PATH):
        with open(KNOWLEDGE_BASE_PATH, "r", encoding="utf-8") as f:
            context = f.read()
    if os.path.exists(KNOWLEDGE_FILES_PATH):
        with open(KNOWLEDGE_FILES_PATH, "r", encoding="utf-8") as f:
            file_list_str = f.read()
    return context, file_list_str

def add_file_to_cumulative_knowledge(uploaded_file):
    """업로드된 파일(PDF, Excel, CSV)을 지식 베이스에 누적(Append) 학습"""
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
        for page in reader.pages:
            text = page.extract_text()
            if text:
                extracted_text += text + "\n"

    if extracted_text:
        current_context, current_files = load_knowledge_data()
        
        if filename in current_files.split(","):
            return False, f"⚠️ `{filename}` 문서는 이미 학습되어 있습니다."

        new_context = current_context + f"\n\n--- [학습 문서 시작: {filename}] ---\n" + extracted_text + f"\n--- [학습 문서 끝: {filename}] ---\n"
        
        with open(KNOWLEDGE_BASE_PATH, "w", encoding="utf-8") as f:
            f.write(new_context)
            
        new_files_list = (current_files + "," + filename).strip(",")
        with open(KNOWLEDGE_FILES_PATH, "w", encoding="utf-8") as f:
            f.write(new_files_list)
            
        return True, f"✅ `{filename}` 문서 학습 완료! 통합 지식 베이스에 추가되었습니다."
    return False, f"⚠️ `{filename}` 문서에서 텍스트를 추출할 수 없습니다."

def delete_all_knowledge_data():
    """전체 학습 데이터 초기화"""
    if os.path.exists(KNOWLEDGE_BASE_PATH):
        os.remove(KNOWLEDGE_BASE_PATH)
    if os.path.exists(KNOWLEDGE_FILES_PATH):
        os.remove(KNOWLEDGE_FILES_PATH)

knowledge_context, learned_files_str = load_knowledge_data()
learned_files_list = [f for f in learned_files_str.split(",") if f]

def save_sales_log(planner_name, client_name, proposed_deal, equipment_status, equipment_item, reaction, memo):
    """영업 일지 데이터 저장"""
    new_data = pd.DataFrame([{
        "작성일시": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"),
        "담당플래너": planner_name,
        "고객/매장명": client_name,
        "제안서비스/견적가": proposed_deal,
        "체험장비설치": equipment_status,
        "설치장비품목": equipment_item if equipment_status == "설치 완료" else "-",
        "고객반응/상태": reaction,
        "영업메모": memo
    }])
    if os.path.exists(SALES_LOG_PATH):
        old_df = pd.read_csv(SALES_LOG_PATH)
        if "담당팀원" in old_df.columns:
            old_df.rename(columns={"담당팀원": "담당플래너"}, inplace=True)
        df = pd.concat([old_df, new_data], ignore_index=True)
    else:
        df = new_data
    df.to_csv(SALES_LOG_PATH, index=False, encoding="utf-8-sig")

def load_equipment_inventory():
    """플래너별 체험장비 보유 대수 로드"""
    if os.path.exists(EQUIPMENT_LOG_PATH):
        df = pd.read_csv(EQUIPMENT_LOG_PATH)
        if "담당팀원" in df.columns:
            df.rename(columns={"담당팀원": "담당플래너"}, inplace=True)
        if "보유대수" in df.columns and "전체 보유대수" not in df.columns:
            df.rename(columns={"보유대수": "전체 보유대수"}, inplace=True)
        return df
    default_df = pd.DataFrame([
        {"담당플래너": "홍길동", "전체 보유대수": 5},
        {"담당플래너": "김철수", "전체 보유대수": 3},
        {"담당플래너": "이영희", "전체 보유대수": 4}
    ])
    default_df.to_csv(EQUIPMENT_LOG_PATH, index=False, encoding="utf-8-sig")
    return default_df

def save_equipment_inventory(df):
    """체험장비 보유 대수 저장"""
    df.to_csv(EQUIPMENT_LOG_PATH, index=False, encoding="utf-8-sig")

# ==========================================
# 4. 사이드바 UI 및 프롬프트 설정
# ==========================================
with st.sidebar:
    st.header("⚙️ 영업 모드 설정")
    
    role_option = st.selectbox(
        "AI 영업 파트너 모드:",
        [
            "경기서북부 상권 분석 & 영업지 추천 (BI Pro)",
            "견적 & 요금 비교 전문가 (학습 문서 기반 Pro)",
            "거절 대응 & 셀링포인트 안내",
            "자유 질문 모드"
        ]
    )
    
    if role_option == "경기서북부 상권 분석 & 영업지 추천 (BI Pro)":
        base_instruction = (
            "당신은 경기도 고양시, 파주시, 김포시, 인천 검단구 지역 전문 세스코 영업 상권 컨설턴트이자 최고 영업 멘토입니다.\n"
            "플래너가 특정 상권(예: 라페스타, 야당역, 구래동, 검단 등)이나 보유한 체험장비/제품(예: 에어퍼퓸, 에어제닉, 공기살균기 등)을 언급하며 영업 전략을 물어보면, 피상적인 안내를 지양하고 아래 4단계 실전 영업 지침서 형태로 매우 상세하고 구체적으로 답변하세요.\n\n"
            "[답변 작성 4단계 필수 프레임워크]\n"
            "1. 🎯 보유 장비/제품 맞춤 타겟 업종 매칭: 언급된 장비/제품의 기능적 특성(향기, 탈취, 살균 등)에 딱 맞는 상권 내 최적 타겟 업종과 그 이유를 명확히 제시하세요.\n"
            "2. 📍 상권 내 세부 동선 및 우선 방문 구역: 해당 상권의 동/층수/구역별 특성을 분석하여 시간대별 우선 방문 동선을 추천하세요.\n"
            "3. 💬 체험장비 무상 설치 유치 킬러 피칭 화법: 사장님의 니즈를 자극하고 거절을 무력화하는 100% 무상 시범 설치 대화 대본(Script)을 작성하세요.\n"
            "4. 💡 현장 시연 및 거절 예방 팁: 현장에서 즉시 체감시키는 시연 방법 및 최적의 장비 설치 위치 전략을 제시하세요.\n\n"
            "장황한 이론 대신 현장에서 바로 적용할 수 있는 디테일하고 실전적인 가이드를 제공하세요."
        )
        )
    elif role_option == "견적 & 요금 비교 전문가 (학습 문서 기반 Pro)":
        base_instruction = (
            "당신은 영업 플래너를 보조하는 세스코 초정밀 견적 및 제품 안내 전문 컨설턴트입니다.\n"
            "[작성 논리 및 점검 수칙 (필수)]\n"
            "1. 고객의 질문이나 첨부된 사진(해충 식별 포함)을 분석하세요.\n"
            "2. 하단에 제공된 [업로드된 학습 문서 데이터] 안에서만 답변을 찾으세요. 절대로 없는 내용을 지어내지 마세요.\n"
            "3. 답변 출력 전 3단계 스스로 점검(1단계: 문서 존재여부 / 2단계: 단독가/결합가 가격 정확성 / 3단계: 업종/평수 적합성)을 완료하세요.\n"
            "4. 인사말은 생략하고, 표와 불렛포인트로 간결하게 답변하세요.\n"
            "5. 답변 본문에는 이미지를 첨부하지 마세요."
        )
    elif role_option == "거절 대응 & 셀링포인트 안내":
        base_instruction = (
            "당신은 베테랑 영업 멘토입니다.\n"
            "플래너가 고객의 거절 반응을 입력하면, 이를 뒤집을 수 있는 강력한 반박 논리와 세스코만의 차별점을 3줄 이내로 핵심만 알려주세요."
        )
    else:
        base_instruction = "당신은 유능하고 친절한 AI 영업 보조입니다. 답변은 간결하게 작성하세요."

    st.divider()
    st.subheader("📚 현재 AI 학습 문서 상태")
    if learned_files_list:
        st.success(f"**누적 학습 완료 ({len(learned_files_list)}건):**")
        st.text_area("파일 목록 (RAG 최우선 참조)", value="\n".join(learned_files_list), height=100)
    else:
        st.info("현재 학습된 제품/단가표 문서가 없습니다.")

    st.divider()
    st.subheader("🔑 관리자 패널")
    admin_password_secret = st.secrets.get("ADMIN_PASSWORD", "1234")
    input_pwd = st.text_input("비밀번호 입력:", type="password")
    
    if input_pwd == admin_password_secret:
        st.success("🔓 관리자 권한 활성화됨")
        
        admin_tab1, admin_tab2, admin_tab3 = st.tabs(["📊 영업 대시보드", "📦 체험장비 운용/할당 설정", "📁 누적 문서 학습(PDF)"])
        
        with admin_tab1:
            st.write("📈 **실시간 영업 성과 대시보드**")
            if os.path.exists(SALES_LOG_PATH):
                logs_df = pd.read_csv(SALES_LOG_PATH)
                if "담당팀원" in logs_df.columns and "담당플래너" not in logs_df.columns:
                    logs_df.rename(columns={"담당팀원": "담당플래너"}, inplace=True)
                if "설치장비품목" not in logs_df.columns:
                    logs_df["설치장비품목"] = "-"
                
                inv_df = load_equipment_inventory()
                installed_counts = logs_df[logs_df["체험장비설치"] == "설치 완료"]["담당플래너"].value_counts().reset_index()
                installed_counts.columns = ["담당플래너", "설치대수"]
                
                merged_inv = pd.merge(inv_df, installed_counts, on="담당플래너", how="left").fillna(0)
                merged_inv["설치대수"] = merged_inv["설치대수"].astype(int)
                merged_inv["현재 수중 보유대수"] = merged_inv["전체 보유대수"] - merged_inv["설치대수"]
                merged_inv["설치활동률(%)"] = (merged_inv["설치대수"] / merged_inv["전체 보유대수"] * 100).round(1)
                
                st.subheader("1️⃣ 플래너별 체험장비 보유 및 설치 현황")
                st.dataframe(merged_inv[["담당플래너", "전체 보유대수", "설치대수", "현재 수중 보유대수", "설치활동률(%)"]], use_container_width=True)
                
                chart_data = merged_inv.set_index("담당플래너")[["전체 보유대수", "설치대수", "현재 수중 보유대수"]]
                st.bar_chart(chart_data)
                
                st.divider()
                st.subheader("2️⃣ 체험장비 설치 후 계약 성사율 분석")
                installed_group = logs_df[logs_df["체험장비설치"] == "설치 완료"]
                non_installed_group = logs_df[logs_df["체험장비설치"] != "설치 완료"]
                
                total_installed = len(installed_group)
                installed_success = len(installed_group[installed_group["고객반응/상태"].str.contains("계약 완료", na=False)])
                installed_rate = (installed_success / total_installed * 100) if total_installed > 0 else 0.0
                
                total_non = len(non_installed_group)
                non_success = len(non_installed_group[non_installed_group["고객반응/상태"].str.contains("계약 완료", na=False)])
                non_rate = (non_success / total_non * 100) if total_non > 0 else 0.0
                
                m_col1, m_col2 = st.columns(2)
                with m_col1:
                    st.metric(label="🎁 체험장비 설치 후 계약 성사율", value=f"{installed_rate:.1f}%", delta=f"{installed_success}건 성공 / 총 {total_installed}건")
                with m_col2:
                    st.metric(label="❌ 미설치건 계약 성사율", value=f"{non_rate:.1f}%", delta=f"{non_success}건 성공 / 총 {total_non}건")
                    
                st.divider()
                st.subheader("3️⃣ 인기 제안 상품 & 서비스 순위")
                product_counts = logs_df["제안서비스/견적가"].value_counts().head(5)
                st.bar_chart(product_counts)
                
                st.divider()
                st.write("📋 **전체 영업일지 데이터 대장:**")
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
                st.info("영업일지 데이터가 쌓이면 실시간 분석 대시보드가 표시됩니다.")

        with admin_tab2:
            st.write("📦 **체험장비 보유 대수 & 설치 장소/내역 종합 관리**")
            st.subheader("📍 1. 체험장비 실제 설치 매장/장소 상세 내역")
            if os.path.exists(SALES_LOG_PATH):
                logs_df = pd.read_csv(SALES_LOG_PATH)
                if "담당팀원" in logs_df.columns and "담당플래너" not in logs_df.columns:
                    logs_df.rename(columns={"담당팀원": "담당플래너"}, inplace=True)
                if "설치장비품목" not in logs_df.columns:
                    logs_df["설치장비품목"] = "-"
                
                installed_logs = logs_df[logs_df["체험장비설치"] == "설치 완료"]
                if len(installed_logs) > 0:
                    display_cols = ["작성일시", "담당플래너", "고객/매장명", "설치장비품목", "고객반응/상태", "영업메모"]
                    st.dataframe(installed_logs[display_cols], use_container_width=True)
                else:
                    st.info("현재 현장에 설치된 체험장비 내역이 없습니다.")
            else:
                st.info("기록된 영업일지가 없습니다.")
                
            st.divider()
            st.subheader("⚙️ 2. 플래너별 체험장비 전체 할당 대수(Total) 수정")
            current_inv = load_equipment_inventory()
            
            edited_df = st.data_editor(current_inv, num_rows="dynamic", use_container_width=True)
            if st.button("💾 전체 보유대수 수정사항 저장", use_container_width=True):
                save_equipment_inventory(edited_df)
                st.toast("✅ 플래너별 체험장비 전체 할당 대수가 업데이트되었습니다!", icon="🎉")
                st.rerun()

        with admin_tab3:
            st.subheader("📁 제품 정보 및 단가표 문서(PDF) 누적 학습")
            st.caption("여러 개의 PDF, 엑셀 파일을 업로드하면 AI가 통합하여 하나의 지식 기반으로 만듭니다.")
            
            uploaded_files = st.file_uploader("여러 제품 문서 업로드 (누적 학습)", type=["pdf", "xlsx", "csv"], accept_multiple_files=True)
            
            if uploaded_files and st.button("💾 업로드된 모든 문서를 누적 학습시키기", use_container_width=True):
                success_count = 0
                error_msgs = []
                with st.spinner("AI가 여러 문서를 정밀 분석 및 통합 학습 중입니다..."):
                    for up_file in uploaded_files:
                        success, message = add_file_to_cumulative_knowledge(up_file)
                        if success:
                            success_count += 1
                        else:
                            error_msgs.append(message)
                            
                if success_count > 0:
                    st.toast(f"✅ {success_count}건의 문서 누적 학습 완료!", icon="🎉")
                if error_msgs:
                    st.warning("\n".join(error_msgs))
                st.rerun()
                    
            if learned_files_list and st.button("🗑️ 전체 학습 데이터 초기화 (삭제)", use_container_width=True, type="secondary"):
                delete_all_knowledge_data()
                st.toast("전체 학습 데이터 초기화 완료!", icon="🧹")
                st.rerun()
    elif input_pwd:
        st.error("비밀번호 불일치")
    else:
        st.caption("관리자만 영업 대시보드 및 AI 누적 문서 학습 관리가 가능합니다.")

    st.divider()
    if st.button("🔄 대화 내용 초기화", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

# ==========================================
# 5. 메인 화면 & 챗봇 인터페이스
# ==========================================
st.title("💼 우리 팀 세스코 영업지원 AI (Pro)")

if learned_files_list:
    st.caption(f"📌 **참조 학습 문서:** `{len(learned_files_list)}건 통합` | 경기서북부 맞춤 AI")
else:
    st.caption("📌 **경기서북부(고양/파주/김포/검단) 영업 특화 모드**")

st.divider()

if "GEMINI_API_KEY" in st.secrets:
    api_key = st.secrets["GEMINI_API_KEY"].strip()
    client = genai.Client(api_key=api_key)

    if "messages" not in st.session_state:
        st.session_state.messages = []

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    selected_faq = None
    st.write("💡 **경기 서북부 주요 거점 퀵 분석 (버튼 터치):**")
    
    if role_option == "경기서북부 상권 분석 & 영업지 추천 (BI Pro)":
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            if st.button("📌 파주 야당역/운정 상권", use_container_width=True):
                selected_faq = "파주 야당역 음식점/유흥 상권 및 운정 신도시 상가의 특징, 포진 업종, 세스코 타겟 제안 전략을 알려줘."
        with col2:
            if st.button("📌 김포 구래동/운양동 상권", use_container_width=True):
                selected_faq = "김포 구래동 24시 외식 상권과 운양동 카페/병원 상권의 특성과 추천 서비스를 분석해줘."
        with col3:
            if st.button("📌 검단신도시 아라동 상권", use_container_width=True):
                selected_faq = "인천 검단신도시(아라동) 신규 입주 상가 건물들의 업종 특징과 초기 계약 타겟 포인트를 알려줘."
        with col4:
            if st.button("📌 고양 라페스타/삼송 상권", use_container_width=True):
                selected_faq = "고양 라페스타 구상권과 삼송/덕은 신규 오피스 상권의 주요 차이점과 맞춤 영업 방식을 분석해줘."
    else:
        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("🔍 15평 매장 단독/결합가 비교", use_container_width=True):
                selected_faq = "15평 매장 기준 단독가, 결합가, 프로모션가를 핵심만 간결하게 표로 비교해줘. (3-Step 스스로 점검할 것)"
        with col2:
            if st.button("🛡️ 타사 대비 핵심 강점 보기", use_container_width=True):
                selected_faq = "타사 대비 세스코 핵심 차별점 3가지를 짧고 강력하게 정리해줘."
        with col3:
            if st.button("🎁 이번 달 프로모션 혜택", use_container_width=True):
                selected_faq = "이번 달 프로모션 할인 혜택과 주요 단가를 간결하게 보여줘."

    st.write("---")
    
    with st.expander("📸 **현장 해충/매장 사진 AI 진단 및 제품 추천**"):
        uploaded_img = st.file_uploader("현장 스마트폰 사진을 첨부하세요. AI가 식별 및 견적을 3번 점검합니다.", type=["jpg", "jpeg", "png"])
        if uploaded_img:
            st.image(uploaded_img, caption="첨부된 사진 진단 중...", width=200)

    prompt_input = st.chat_input("질문을 입력하세요... (예: 야당역 상권 알려줘, 또는 독일바퀴 견적 얼마야?)")
    
    user_prompt = selected_faq if selected_faq else prompt_input

    if user_prompt:
        st.chat_message("user").markdown(user_prompt)
        st.session_state.messages.append({"role": "user", "content": user_prompt})

        history = []
        for msg in st.session_state.messages[:-1]:
            role = "user" if msg["role"] == "user" else "model"
            history.append({"role": role, "parts": [{"text": msg["content"]}]})

        final_system_instruction = base_instruction
        
        if role_option == "견적 & 요금 비교 전문가 (학습 문서 기반 Pro)" and knowledge_context:
            final_system_instruction += (
                f"\n\n[업로드된 전체 통합 학습 문서 데이터 ({len(learned_files_list)}건 통합본)]\n"
                "가장 중요한 정보입니다. 답변 시 반드시 이 내용 안에서만 찾고 3번 점검하세요:\n\n"
                f"{knowledge_context}"
            )
        elif role_option == "경기서북부 상권 분석 & 영업지 추천 (BI Pro)":
            final_system_instruction += (
                "\n\n[경기 서북부 상권 분석 가이드]\n"
                "고양, 파주, 김포, 검단 지역 특성에 집중하여 업종 분포, 신도시/구상권 차이, 최적 영업 전략을 '추정 데이터'임을 밝히고 핵심만 제안하세요."
            )

        with st.chat_message("assistant"):
            try:
                # 💡 [핵심 수정] Gemini 3 시리즈 모델 적용
                chat = client.chats.create(
                    model="gemini-3-flash-preview", 
                    config=types.GenerateContentConfig(
                        system_instruction=final_system_instruction
                    ),
                    history=history
                )
                
                if uploaded_img:
                    from PIL import Image as PILImage
                    img_obj = PILImage.open(uploaded_img)
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
    # 📱 카톡 요약문 (300자 제한) & 견적 카드 생성
    # ==========================================
    st.write("---")
    if len(st.session_state.messages) > 0 and role_option != "경기서북부 상권 분석 & 영업지 추천 (BI Pro)":
        if st.button("📱 **간결한 카톡 제안서 & 카드 이미지 생성**", use_container_width=True):
            with st.spinner("300자 이내 카톡 메시지 및 초고해상도 카드 제작 중..."):
                try:
                    recent_chat = st.session_state.messages[-1]["content"]
                    
                    summary_prompt = (
                        f"다음 견적 상담 내용을 바탕으로 고객에게 카카오톡으로 전달할 친절하고 정중한 요약 메시지를 작성해 줘.\n"
                        f"[작성 조건]\n"
                        f"1. 전체 글자 수는 공백 포함 **최대 300자 이내**로 매우 간결하게 작성할 것.\n"
                        f"2. 인사말은 1줄로 최소화하고 [매장명/추천서비스/월단가/주요혜택]만 불렛포인트로 명확히 적을 것.\n"
                        f"3. 한눈에 읽기 쉬운 카톡 전송용으로 만들 것.\n"
                        f"4. AI가 스스로 3번 점검한 정확한 제품명과 가격이어야 함.\n\n"
                        f"견적 내용:\n{recent_chat}"
                    )
                    chat = client.chats.create(model="gemini-3-flash-preview")
                    text_res = chat.send_message(summary_prompt)
                    
                    st.subheader("📱 **1. 카톡/문자 전송용 간결 메시지 (복사용)**")
                    st.code(text_res.text, language="text")
                    
                    json_prompt = (
                        f"다음 견적 내용에서 핵심 서비스와 요금 정보를 추출하여 오직 JSON 형식으로만 응답해 줘.\n"
                        f"JSON 구조 예시:\n"
                        f"{{\n"
                        f'  "title": "15평 매장 맞춤 위생 솔루션 견적",\n'
                        f'  "subtitle": "해충방제 + 위생케어 결합 할인 적용가",\n'
                        f'  "items": [\n'
                        f'    {{"name": "보일러/유충 방제", "price": "45,000원/월", "note": "월 1회 방문 점검"}},\n'
                        f'    {{"name": "바이러스케어", "price": "30,000원/월", "note": "방제 결합 할인가"}}\n'
                        f'  ],\n'
                        f'  "promotion": "초기 설치비 면제 혜택"\n'
                        f"}}\n\n"
                        f"견적 내용:\n{recent_chat}"
                    )
                    json_res = chat.send_message(json_prompt)
                    
                    json_match = re.search(r'\{.*\}', json_res.text, re.DOTALL)
                    if json_match:
                        card_data = json.loads(json_match.group())
                    else:
                        card_data = {
                            "title": "세스코 맞춤 솔루션 견적",
                            "subtitle": "공식 단가 기준 안내",
                            "items": [{"name": "맞춤 위생 서비스", "price": "상담가", "note": "상세 문의"}],
                            "promotion": "프로모션 및 결합 할인 조건 적용 가능"
                        }
                    
                    st.subheader("🖼️ **2. 카톡 전송용 완성형 그래픽 견적 카드**")
                    card_img_bytes = create_high_res_quote_card(card_data)
                    
                    st.image(card_img_bytes, caption="모바일 전용 초고해상도 견적 카드 (1200x1600)", use_container_width=True)
                    
                    st.download_button(
                        label="📥 **고해상도 견적 카드 다운로드 (.png)**",
                        data=card_img_bytes,
                        file_name="CES코_고해상도_견적카드.png",
                        mime="image/png",
                        use_container_width=True
                    )
                except Exception as img_err:
                    st.error(f"⚠️ 카드 이미지 생성 중 오류가 발생했습니다: {img_err}")

    # ==========================================
    # 📝 현장 영업일지 기록
    # ==========================================
    with st.expander("📝 **플래너 현장 영업 미팅 일지 기록하기**"):
        st.caption("오늘 방문한 매장/고객과의 상담 내역을 기록하면 전체 영업 대장에 저장되고 재고가 반영됩니다.")
        with st.form("sales_log_form", clear_on_submit=True):
            col_a, col_b = st.columns(2)
            with col_a:
                planner_input = st.text_input("담당 플래너 이름 * (예: 홍길동)")
                client_input = st.text_input("방문 매장/고객명 * (예: 대박식당)")
                p_deal = st.text_input("제안 서비스 및 견적가 (예: 방제+바이러스 결합 월 65,000원)")
            with col_b:
                eq_status = st.selectbox("🎁 체험장비 설치 여부", ["미설치", "설치 완료"])
                eq_item = st.text_input("설치한 체험장비 품목 (예: 공기살균기 B타입, 포충기 등)")
                reaction = st.selectbox("고객 반응/상태", ["계약 완료 🎉", "긍정적 (계약 임박)", "검토 중 (재방문 필요)", "보류 (가격 부담)"])
                memo = st.text_input("영업 메모 (예: 다음 주 화요일에 사장님 재방문 예정)")
                
            submit_log = st.form_submit_button("💾 영업일지 저장 및 대시보드 반영하기", use_container_width=True)
            if submit_log:
                if planner_input and client_input:
                    with st.spinner("영업일지 저장 중..."):
                        save_sales_log(planner_input, client_input, p_deal, eq_status, eq_item, reaction, memo)
                        st.toast("✅ 영업일지 저장 완료!", icon="🎉")
                        st.rerun()
                else:
                    st.warning("⚠️ 필수 항목(플래너 이름, 고객명)을 입력해 주세요.")
else:
    st.error("⚠️ Streamlit Cloud Secrets에 GEMINI_API_KEY가 설정되지 않았습니다.")
