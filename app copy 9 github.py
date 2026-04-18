import os
import json
import urllib.request
import urllib.error
import streamlit as st
MEMORY_FILE = "memory.json"
CHAT_FOLDER = "chats"

def get_chat_files():
    if not os.path.exists(CHAT_FOLDER):
        os.makedirs(CHAT_FOLDER)
    return [f for f in os.listdir(CHAT_FOLDER) if f.endswith(".json")]

def load_chat(filename):
    path = os.path.join(CHAT_FOLDER, filename)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def save_chat(filename, history):
    path = os.path.join(CHAT_FOLDER, filename)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

def load_memory():
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def save_memory(history):
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)
# -----------------------------
# Configuration
# -----------------------------
AZURE_OPENAI_ENDPOINT = "https://eva-ai.openai.azure.com/"
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_OPENAI_DEPLOYMENT = "eva-4-1"
AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")
SYSTEM_PROMPT_FILE = os.getenv("SYSTEM_PROMPT_FILE", "sacred_system.txt")


def load_system_prompt(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()
    except FileNotFoundError:
        return "You are a helpful assistant."


def call_azure_openai(messages: list[dict]) -> str:
    if not AZURE_OPENAI_ENDPOINT or not AZURE_OPENAI_API_KEY or not AZURE_OPENAI_DEPLOYMENT:
        raise RuntimeError(
            "Missing configuration. Set AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_KEY, and AZURE_OPENAI_DEPLOYMENT."
        )

    endpoint = AZURE_OPENAI_ENDPOINT.rstrip("/")
    url = (
        f"{endpoint}/openai/deployments/{AZURE_OPENAI_DEPLOYMENT}"
        f"/chat/completions?api-version={AZURE_OPENAI_API_VERSION}"
    )

    payload = {
    "messages": messages,
    "max_tokens": 800,
    "temperature": 0.7
}

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "api-key": AZURE_OPENAI_API_KEY,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"Azure error {e.code}: {body}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"Connection error: {e}") from e

    # Chat Completions parsing
    try:
        return result["choices"][0]["message"]["content"]
    except Exception:
        return json.dumps(result, indent=2, ensure_ascii=False)


# -----------------------------
# UI
# -----------------------------
st.set_page_config(page_title="Eva Private Chat", page_icon="💬", layout="centered")
st.title("Eva Private Chat")
st.caption("Private Azure chat with your sacred system prompt loaded automatically.")

system_prompt = load_system_prompt(SYSTEM_PROMPT_FILE)
def load_knowledge(folder="knowledge"):
    knowledge_texts = []
    if os.path.exists(folder):
        for filename in os.listdir(folder):
            if filename.endswith(".txt"):
                with open(os.path.join(folder, filename), "r", encoding="utf-8") as f:
                    knowledge_texts.append(f.read())
    return "\n\n".join(knowledge_texts)

knowledge = load_knowledge()
if "history" not in st.session_state:
    st.session_state.history = load_memory()

with st.sidebar:
    st.subheader("Chats")

    chat_files = get_chat_files()

    if st.button("New Chat"):
        new_chat_name = f"chat_{len(chat_files)+1}.json"
        st.session_state.current_chat = new_chat_name
        st.session_state.history = []
        save_chat(new_chat_name, [])

    selected_chat = st.selectbox(
        "Select chat",
        ["new_chat.json"] + chat_files
    )

    st.subheader("Setup")
    st.write("This app reads your sacred system prompt automatically from `sacred_system.txt`.")
    st.text_input("Deployment", value=AZURE_OPENAI_DEPLOYMENT, disabled=True)
    st.text_area("System prompt preview", value=system_prompt[:1500], height=220, disabled=True)
    if st.button("Clear chat"):
        st.session_state.history = []
        st.rerun()

if "current_chat" not in st.session_state:
    st.session_state.current_chat = "new_chat.json"

if "history" not in st.session_state:
    if os.path.exists(os.path.join(CHAT_FOLDER, "new_chat.json")):
        st.session_state.history = load_chat("new_chat.json")
    else:
        st.session_state.history = load_memory()
        save_chat("new_chat.json", st.session_state.history)

if selected_chat != st.session_state.current_chat:
    st.session_state.current_chat = selected_chat
    st.session_state.history = load_chat(selected_chat)

for msg in st.session_state.history:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

user_text = st.chat_input("Write your message")
if user_text:
    st.session_state.history.append({"role": "user", "content": user_text})
    with st.chat_message("user"):
        st.markdown(user_text)

    messages = [{"role": "system", "content": system_prompt + "\n\nKnowledge:\n" + knowledge}]
    messages.extend(st.session_state.history)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                reply = call_azure_openai(messages)
            except Exception as e:
                reply = f"Error: {e}"
            st.markdown(reply)

    st.session_state.history.append({"role": "assistant", "content": reply})
    save_chat(st.session_state.current_chat, st.session_state.history)