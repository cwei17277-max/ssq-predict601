import streamlit as st
import requests
import json

# 页面配置：设置标题与移动端适配布局
st.set_page_config(
    page_title="随身英语助手",
    page_icon="🔤",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# 初始化本地 Session 生词本（刷新页面时保留数据）
if "vocab_list" not in st.session_state:
    st.session_state.vocab_list = []

# 自定义 CSS 提升手机端 UI 体验
st.markdown("""
    <style>
    .main { padding: 1rem; }
    .stButton>button { width: 100%; border-radius: 8px; }
    .word-card {
        background-color: #f8f9fa;
        padding: 15px;
        border-radius: 10px;
        border: 1px solid #e9ecef;
        margin-bottom: 10px;
    }
    .phonetic { color: #e67e22; font-weight: bold; }
    </style>
""", unsafe_allow_html=True)

st.title("🔤 随身英语助手")

# 1. 查询/翻译输入区
user_input = st.text_area("输入英文单词或句子：", placeholder="例如: Apple 或 Learning English is fun!", height=100)

col1, col2 = st.columns([2, 1])

with col1:
    search_btn = st.button("🔍 查询 / 翻译", type="primary")
with col2:
    clear_btn = st.button("🗑️ 清空")

if clear_btn:
    st.rerun()

# 逻辑判断：点击查询
if search_btn and user_input.strip():
    query = user_input.strip()
    is_single_word = len(query.split()) == 1

    phonetic = ""
    # 如果是单个单词，去 Dictionary API 查音标
    if is_single_word:
        try:
            dict_res = requests.get(f"https://api.dictionaryapi.dev/api/v2/entries/en/{query}", timeout=5)
            if dict_res.status_code == 200:
                dict_data = dict_res.json()
                phonetic = dict_data[0].get("phonetic", "")
                if not phonetic:
                    # 尝试从 phonetics 数组提取
                    for p in dict_data[0].get("phonetics", []):
                        if "text" in p and p["text"]:
                            phonetic = p["text"]
                            break
        except Exception:
            phonetic = ""

    # 使用免费翻译 API 查中文释义/句子翻译
    translation = ""
    try:
        trans_res = requests.get(
            f"https://api.mymemory.translated.net/get?q={query}&langpair=en|zh-CN", 
            timeout=5
        )
        if trans_res.status_code == 200:
            translation = trans_res.json()["responseData"]["translatedText"]
    except Exception:
        translation = "翻译服务暂时不可用"

    # 展示查询结果卡片
    st.markdown("---")
    st.markdown("### 查词结果")
    
    # 标注发音（注：Streamlit 容器内可通过 HTML5 audio 直接播放微软/谷歌TTS语音）
    display_phonetic = phonetic if phonetic else ("/暂无音标/" if is_single_word else "[句子翻译]")
    
    st.markdown(f"""
    <div class="word-card">
        <h3>{query} <span class="phonetic">{display_phonetic}</span></h3>
        <p><b>释义：</b> {translation}</p>
    </div>
    """, unsafe_allow_html=True)

    # 发音组件（利用免费TTS音频流）
    audio_url = f"https://translate.google.com/translate_tts?ie=UTF-8&q={query}&tl=en&client=tw-ob"
    st.audio(audio_url, format="audio/mp3")

    # 加入生词本按钮
    if st.button("➕ 保存到我的生词本"):
        item = {"word": query, "phonetic": display_phonetic, "translation": translation}
        if not any(v['word'].lower() == query.lower() for v in st.session_state.vocab_list):
            st.session_state.vocab_list.insert(0, item)
            st.success("已成功保存到生词本！")
        else:
            st.warning("该单词已存在于生词本中。")

# 2. 本地生词本展示
st.markdown("---")
st.subheader("📖 我的生词本")

if not st.session_state.vocab_list:
    st.info("暂无生词，快在上方查询并添加吧！")
else:
    for idx, item in enumerate(st.session_state.vocab_list):
        with st.expander(f"📌 {item['word']}  {item['phonetic']}"):
            st.write(f"**释义：** {item['translation']}")
            
            # 单词朗读
            st.audio(f"https://translate.google.com/translate_tts?ie=UTF-8&q={item['word']}&tl=en&client=tw-ob", format="audio/mp3")
            
            # 删除生词按钮
            if st.button("删除", key=f"del_{idx}"):
                st.session_state.vocab_list.pop(idx)
                st.rerun()