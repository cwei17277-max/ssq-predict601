import streamlit as st
import requests
from paddleocr import PaddleOCR
from gtts import gTTS
import speech_recognition as sr
from io import BytesIO
import PIL.Image as Image

# 页面配置
st.set_page_config(
    page_title="AI 随身英语全能助手",
    page_icon="🤖",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# 初始化 OCR 模型 (第一次加载会比较慢，后续会缓存)
@st.cache_resource
def load_ocr_model():
    # 使用中英文模型
    return PaddleOCR(use_angle_cls=True, lang="ch")

ocr_model = load_ocr_model()

# 初始化语音识别器
r = sr.Recognizer()

# 初始化本地 Session 生词本
if "vocab_list" not in st.session_state:
    st.session_state.vocab_list = []

# 自定义 CSS
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
    .stTextArea textarea { font-size: 1.1rem; }
    </style>
""", unsafe_allow_html=True)

st.title("🤖 AI 随身英语全能助手")

# 1. 功能选择
app_mode = st.selectbox("选择功能", ["手动查词/翻译", "📷 拍照识字/翻译", "🎙️ 语音输入(中->英)"])

# 通用查词/翻译逻辑函数
def get_translation_and_phonetic(query, langpair="en|zh-CN"):
    is_single_word = len(query.split()) == 1 and "|" not in langpair # 粗略判断单词
    phonetic = ""
    translation = "翻译服务暂时不可用"

    # 1. 查音标 (仅限英文单字)
    if is_single_word and langpair.startswith("en"):
        try:
            dict_res = requests.get(f"https://api.dictionaryapi.dev/api/v2/entries/en/{query}", timeout=5)
            if dict_res.status_code == 200:
                dict_data = dict_res.json()
                phonetic = dict_data[0].get("phonetic", "")
                if not phonetic:
                    for p in dict_data[0].get("phonetics", []):
                        if "text" in p and p["text"]:
                            phonetic = p["text"]
                            break
        except Exception:
            pass

    # 2. 通用翻译
    try:
        trans_res = requests.get(
            f"https://api.mymemory.translated.net/get?q={query}&langpair={langpair}", 
            timeout=5
        )
        if trans_res.status_code == 200:
            translation = trans_res.json()["responseData"]["translatedText"]
    except Exception:
        pass

    return phonetic, translation, is_single_word

# 通用结果展示和保存生词本逻辑
def display_result_and_save(query, phonetic, translation, is_single_word, is_english_input=True):
    display_phonetic = phonetic if phonetic else ("/暂无音标/" if is_single_word else "")
    
    st.markdown("---")
    st.markdown("### 查词/翻译结果")
    st.markdown(f"""
    <div class="word-card">
        <h3>{query} <span class="phonetic">{display_phonetic}</span></h3>
        <p><b>释义：</b> {translation}</p>
    </div>
    """, unsafe_allow_html=True)

    # 发音组件 (根据输入语言发音)
    lang = "en" if is_english_input else "zh-CN"
    tts_query = query if is_english_input else translation
    # 这里我们统一播放英文的发音，如果是中文输入翻译成英文，播放英文
    if not is_english_input:
        tts_query = translation
        lang = "en"
        
    audio_url = f"https://translate.google.com/translate_tts?ie=UTF-8&q={tts_query}&tl={lang}&client=tw-ob"
    st.audio(audio_url, format="audio/mp3")

    # 加入生词本
    if is_english_input and st.button("➕ 保存到我的生词本", key=f"save_{query}"):
        item = {"word": query, "phonetic": display_phonetic, "translation": translation}
        if not any(v['word'].lower() == query.lower() for v in st.session_state.vocab_list):
            st.session_state.vocab_list.insert(0, item)
            st.success("已成功保存到生词本！")
        else:
            st.warning("该单词已存在于生词本中。")

# ==================== 1. 手动查词/翻译 ====================
if app_mode == "手动查词/翻译":
    user_input = st.text_area("输入英文单词或句子（自动识别中英）：", placeholder="例如: Apple 或 Learning English is fun!", height=100)
    col1, col2 = st.columns([2, 1])
    with col1:
        search_btn = st.button("🔍 查询 / 翻译", type="primary")
    with col2:
        if st.button("🗑️ 清空"): st.rerun()

    if search_btn and user_input.strip():
        # 这里简单判断，包含中文即为中译英，否则英译中
        if any('\u4e00' <= char <= '\u9fff' for char in user_input):
            # 中译英
            phonetic, translation, is_single_word = get_translation_and_phonetic(user_input, langpair="zh-CN|en")
            display_result_and_save(user_input, phonetic, translation, is_single_word, is_english_input=False)
        else:
            # 英译中
            phonetic, translation, is_single_word = get_translation_and_phonetic(user_input, langpair="en|zh-CN")
            display_result_and_save(user_input, phonetic, translation, is_single_word, is_english_input=True)

# ==================== 2. 📷 拍照识字/翻译 ====================
elif app_mode == "📷 拍照识字/翻译":
    st.write("拍摄包含英文单词或句子的图片。")
    uploaded_file = st.camera_input("拍照") # 使用 Streamlit 的相机输入组件

    if uploaded_file is not None:
        # 1. 显示拍摄的图片
        image = Image.open(uploaded_file)
        # 2. 执行 OCR 识别
        with st.spinner("正在识别图片中的文字..."):
            img_bytes = uploaded_file.getvalue()
            result = ocr_model.ocr(img_bytes, cls=True)
            
            # 3. 提取识别到的文字
            recognized_text = ""
            if result:
                for idx in range(len(result)):
                    res = result[idx]
                    if res:
                        for line in res:
                            recognized_text += line[1][0] + " " # 拼接所有行

        recognized_text = recognized_text.strip()
        
        if recognized_text:
            st.success(f"识别到文字: {recognized_text}")
            
            # 4. 如果识别到的是中文，则中译英；否则英译中
            if any('\u4e00' <= char <= '\u9fff' for char in recognized_text):
                 # 中译英
                phonetic, translation, is_single_word = get_translation_and_phonetic(recognized_text, langpair="zh-CN|en")
                display_result_and_save(recognized_text, phonetic, translation, is_single_word, is_english_input=False)
            else:
                # 英译中
                phonetic, translation, is_single_word = get_translation_and_phonetic(recognized_text, langpair="en|zh-CN")
                display_result_and_save(recognized_text, phonetic, translation, is_single_word, is_english_input=True)
        else:
            st.warning("未能在图片中识别到文字。")

# ==================== 3. 🎙️ 语音输入(中->英) ====================
elif app_mode == "🎙️ 语音输入(中->英)":
    st.write("点击下方按钮，开始说中文。")
    
    # 使用 Streamlit 的音频输入组件 (较新的版本支持)
    # 如果你的 streamlit 版本较老，可以通过 HTML/JS 实现，但这个最简单
    audio_data = st.experimental_audio_input("按住说话")

    if audio_data is not None:
        with st.spinner("正在识别您的语音(中文)..."):
            # 1. 将音频数据转换为 SpeechRecognition 可用的格式
            # experimental_audio_input 返回的是 BytesIO，通常是 wav 或 webm 格式
            try:
                # 尝试用 SpeechRecognition 读取
                with sr.AudioFile(BytesIO(audio_data.getvalue())) as source:
                    audio_content = r.record(source) # 读取整个音频文件
                    
                # 2. 执行语音识别 (Google Speech Recognition, 需要联网)
                recognized_chinese = r.recognize_google(audio_content, language="zh-CN")
                st.success(f"识别到您说: {recognized_chinese}")
                
                # 3. 中译英
                with st.spinner("正在翻译成英文..."):
                    phonetic, translation, is_single_word = get_translation_and_phonetic(recognized_chinese, langpair="zh-CN|en")
                    
                    # 4. 显示结果：翻译出的英文
                    # 注意：此时 recognized_chinese 是中文，translation 是英文
                    st.markdown("---")
                    st.markdown("### 英文翻译结果")
                    st.markdown(f"""
                    <div class="word-card">
                        <h3>{translation}</h3>
                        <p>（原文：{recognized_chinese}）</p>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # 5. 播放翻译出的英文发音
                    st.audio(f"https://translate.google.com/translate_tts?ie=UTF-8&q={translation}&tl=en&client=tw-ob", format="audio/mp3")

            except sr.UnknownValueError:
                st.error("未能听懂您的语音，请重试。")
            except sr.RequestError as e:
                st.error(f"语音识别服务请求失败: {e}")
            except Exception as e:
                st.error(f"发生错误: {e}")

# ==================== 4. 本地生词本展示 ====================
st.markdown("---")
st.subheader("📖 我的生词本")

if not st.session_state.vocab_list:
    st.info("暂无生词，快在上方查询并添加吧！")
else:
    for idx, item in enumerate(st.session_state.vocab_list):
        # 英文单词在外面，中文释义在 expander 里面
        with st.expander(f"📌 {item['word']}  {item['phonetic']}"):
            st.write(f"**释义：** {item['translation']}")
            
            # 单词朗读
            st.audio(f"https://translate.google.com/translate_tts?ie=UTF-8&q={item['word']}&tl=en&client=tw-ob", format="audio/mp3")
            
            # 删除生词按钮
            if st.button("删除", key=f"del_{idx}"):
                st.session_state.vocab_list.pop(idx)
                st.rerun()
