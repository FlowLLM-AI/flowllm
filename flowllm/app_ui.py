import json
import os
import time
import uuid
from datetime import datetime

import requests
import streamlit as st

from flowllm.utils.common_utils import load_env

if not os.getenv("FLOW_APP_NAME"):
    load_env(enable_log=False)

APP_NAME: str = os.environ["FLOW_APP_NAME"]

st.set_page_config(
    page_title=f"{APP_NAME} Chat",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    .main-header {
        text-align: center;
        color: #2E86AB;
        margin-bottom: 2rem;
    }

    .chat-container {
        height: 600px;
        overflow-y: auto;
        padding: 1rem;
        border: 1px solid #e0e0e0;
        border-radius: 10px;
        background-color: #fafafa;
    }

    .user-message {
        background-color: #007bff;
        color: white;
        padding: 10px 15px;
        border-radius: 18px;
        margin: 10px 0;
        max-width: 70%;
        margin-left: auto;
        word-wrap: break-word;
    }

    .bot-message {
        background-color: #f1f3f4;
        color: #333;
        padding: 10px 15px;
        border-radius: 18px;
        margin: 10px 0;
        max-width: 70%;
        margin-right: auto;
        word-wrap: break-word;
    }

    /* Chunk type specific styles */
    .chunk-answer {
        background-color: #f1f3f4;
        color: #333;
        padding: 10px 15px;
        border-radius: 18px;
        margin: 5px 0;
        max-width: 70%;
        margin-right: auto;
        word-wrap: break-word;
        border-left: 4px solid #28a745;
    }

    .chunk-think {
        background-color: #fff3cd;
        color: #856404;
        padding: 10px 15px;
        border-radius: 8px;
        margin: 5px 0;
        max-width: 70%;
        margin-right: auto;
        word-wrap: break-word;
        border-left: 4px solid #ffc107;
        font-style: italic;
    }

    .chunk-error {
        background-color: #f8d7da;
        color: #721c24;
        padding: 10px 15px;
        border-radius: 8px;
        margin: 5px 0;
        max-width: 70%;
        margin-right: auto;
        word-wrap: break-word;
        border-left: 4px solid #dc3545;
        font-weight: 500;
    }

    .chunk-tool {
        background-color: #d1ecf1;
        color: #0c5460;
        padding: 10px 15px;
        border-radius: 8px;
        margin: 5px 0;
        max-width: 70%;
        margin-right: auto;
        word-wrap: break-word;
        border-left: 4px solid #17a2b8;
        font-family: monospace;
        font-size: 0.9em;
    }

    .chunk-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 8px;
        font-weight: bold;
        font-size: 0.85em;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }

    .chunk-content {
        margin-top: 5px;
        max-height: 300px;
        overflow-y: auto;
    }

    /* Streamlit expander customization */
    .streamlit-expander {
        border: none;
        box-shadow: none;
    }
    
    .streamlit-expander > .streamlit-expanderHeader {
        font-weight: bold;
        font-size: 0.9em;
    }
    
    /* Force expander width to match message width */
    div[data-testid="column"] .streamlit-expander {
        width: 100% !important;
        max-width: 100% !important;
    }
    
    /* Ensure expander content doesn't overflow */
    .streamlit-expander .streamlit-expanderContent {
        padding: 10px 15px;
        word-wrap: break-word;
    }

    .conversation-item {
        padding: 10px;
        margin: 5px 0;
        border-radius: 8px;
        cursor: pointer;
        transition: background-color 0.2s;
    }

    .conversation-item:hover {
        background-color: #e8f4f8;
    }

    .conversation-active {
        background-color: #d4edda;
        border-left: 4px solid #28a745;
    }

    .new-chat-btn {
        width: 100%;
        padding: 12px;
        background-color: #28a745;
        color: white;
        border: none;
        border-radius: 8px;
        font-size: 16px;
        cursor: pointer;
        margin-bottom: 20px;
    }

    .new-chat-btn:hover {
        background-color: #218838;
    }

    .sidebar-title {
        font-size: 18px;
        font-weight: bold;
        margin-bottom: 15px;
        color: #2E86AB;
    }

    .message-time {
        font-size: 12px;
        color: #666;
        margin-top: 5px;
    }

    .typing-indicator {
        color: #28a745;
        font-style: italic;
        font-size: 12px;
        margin: 10px 15px;
        padding: 8px;
        background-color: #f8f9fa;
        border-radius: 8px;
        border-left: 3px solid #28a745;
    }
</style>

""", unsafe_allow_html=True)

if 'conversations' not in st.session_state:
    st.session_state.conversations = {}

if 'current_conversation_id' not in st.session_state:
    st.session_state.current_conversation_id = None

if 'is_streaming' not in st.session_state:
    st.session_state.is_streaming = False

if 'selected_model' not in st.session_state:
    st.session_state.selected_model = 'llm_flow_stream'


def create_new_conversation():
    conversation_id = str(uuid.uuid4())
    st.session_state.conversations[conversation_id] = {
        'title': 'New Conversation',
        'messages': [],
        'created_at': datetime.now()
    }
    st.session_state.current_conversation_id = conversation_id
    return conversation_id


def get_conversation_title(messages):
    for msg in messages:
        if msg['role'] == 'user':
            content = msg['content']
            return content[:20] + "..." if len(content) > 20 else content
    return "New Conversation"


def render_chunk_content(chunk_type, content, is_collapsible=True):
    """Render different chunk types with appropriate styling using Streamlit components"""
    
    chunk_icons = {
        'answer': '💬',
        'think': '🤔', 
        'error': '❌',
        'tool': '🔧'
    }
    
    chunk_labels = {
        'answer': 'Answer',
        'think': 'Thinking',
        'error': 'Error', 
        'tool': 'Tool Call'
    }
    
    icon = chunk_icons.get(chunk_type, '💬')
    label = chunk_labels.get(chunk_type, 'Response')
    
    # Convert newlines to HTML line breaks for proper display
    formatted_content = content.replace('\n', '<br>')
    
    # Use Streamlit expander for collapsible types (think, error, tool)
    if chunk_type in ['think', 'error', 'tool'] and is_collapsible:
        # Set different default expanded states
        expanded_default = chunk_type == 'error'  # Error expanded by default, others collapsed
        
        with st.expander(f"{icon} {label}", expanded=expanded_default):
            st.markdown(f'<div class="chunk-content">{formatted_content}</div>', unsafe_allow_html=True)
    else:
        # For non-collapsible types (answer) or during streaming - render as HTML
        st.markdown(f"""
        <div class="chunk-{chunk_type}">
            <div class="chunk-header">
                <span>{icon} {label}</span>
            </div>
            <div class="chunk-content">
                {formatted_content}
            </div>
        </div>
        """, unsafe_allow_html=True)


def stream_llm_response(messages, model_name='llm_flow_stream'):
    try:
        url = f"http://localhost:8001/{model_name}"
        headers = {"Content-Type": "application/json"}
        data = {"messages": messages}

        response = requests.post(url, headers=headers, json=data, stream=True)

        if response.status_code == 200:
            for line in response.iter_lines():
                if line:
                    line_str = line.decode('utf-8')
                    if line_str.startswith('data:'):
                        data_content = line_str[5:]

                        if data_content.strip() == '[DONE]':
                            break

                        try:
                            json_data = json.loads(data_content)
                            chunk_type = json_data.get('chunk_type', 'answer')
                            chunk_content = json_data.get('chunk', '')
                            
                            if chunk_content:
                                yield {
                                    'type': chunk_type,
                                    'content': chunk_content
                                }
                        except json.JSONDecodeError:
                            continue
        else:
            yield {
                'type': 'error',
                'content': f"API request failed, status code: {response.status_code}"
            }

    except Exception as e:
        yield {
            'type': 'error', 
            'content': f"Error: {str(e)}"
        }


with st.sidebar:
    st.markdown('<div class="sidebar-title">💬 Chat History</div>', unsafe_allow_html=True)

    # Model selection dropdown
    st.markdown("**🤖 Model Selection**")
    available_models = [
        'llm_flow_stream',
        'dashscope_deep_research',
        # Add more models here in the future
    ]
    
    selected_model = st.selectbox(
        "Choose model:",
        available_models,
        index=available_models.index(st.session_state.selected_model) if st.session_state.selected_model in available_models else 0,
        key="model_selector"
    )
    
    # Update session state when selection changes
    if selected_model != st.session_state.selected_model:
        st.session_state.selected_model = selected_model

    st.markdown("---")

    # New conversation button
    if st.button("➕ New Chat", key="new_chat", use_container_width=True):
        create_new_conversation()
        st.rerun()

    st.markdown("---")

    # Display conversation history
    if st.session_state.conversations:
        for conv_id, conv_data in reversed(list(st.session_state.conversations.items())):
            # Update conversation title
            if conv_data['messages'] and conv_data['title'] == 'New Conversation':
                conv_data['title'] = get_conversation_title(conv_data['messages'])

            # Conversation item style
            is_active = conv_id == st.session_state.current_conversation_id
            button_style = "conversation-active" if is_active else "conversation-item"

            col1, col2 = st.columns([4, 1])
            with col1:
                if st.button(
                        conv_data['title'],
                        key=f"conv_{conv_id}",
                        use_container_width=True
                ):
                    st.session_state.current_conversation_id = conv_id
                    st.rerun()

            with col2:
                if st.button("🗑️", key=f"del_{conv_id}", help="Delete conversation"):
                    del st.session_state.conversations[conv_id]
                    if st.session_state.current_conversation_id == conv_id:
                        st.session_state.current_conversation_id = None
                    st.rerun()

            # Display creation time
            st.caption(f"Created: {conv_data['created_at'].strftime('%m-%d %H:%M')}")
            st.markdown("---")

st.markdown(f'<h1 class="main-header">{APP_NAME} Chat</h1>', unsafe_allow_html=True)

if not st.session_state.current_conversation_id:
    create_new_conversation()

current_conv = st.session_state.conversations.get(st.session_state.current_conversation_id, {})

chat_container = st.container()

with chat_container:
    if current_conv.get('messages'):
        for message in current_conv['messages']:
            if message['role'] == 'user':
                st.markdown(f"""
                <div style="display: flex; justify-content: flex-end; margin: 10px 0;">
                    <div class="user-message">
                        {message['content']}
                        <div class="message-time">{message.get('timestamp', '')}</div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
            else:
                # Handle structured message with chunks
                if isinstance(message.get('content'), list):
                    # Sort chunks to show THINK, ERROR, TOOL first, then ANSWER
                    chunks = message['content']
                    sorted_chunks = []
                    
                    # First add THINK, ERROR, TOOL chunks (before answer)
                    for chunk_type in ['think', 'error', 'tool']:
                        type_chunks = [c for c in chunks if c.get('type') == chunk_type]
                        sorted_chunks.extend(type_chunks)
                    
                    # Then add ANSWER chunks last
                    answer_chunks = [c for c in chunks if c.get('type') == 'answer']
                    sorted_chunks.extend(answer_chunks)
                    
                    # Create a container with limited width for all chunks
                    col1, col2 = st.columns([7, 3])  # 70% width for content, 30% empty
                    with col1:
                        # Render chunks with proper spacing
                        for idx, chunk in enumerate(sorted_chunks):
                            chunk_id = f"{message.get('id', 'msg')}_{idx}"
                            render_chunk_content(
                                chunk.get('type', 'answer'), 
                                chunk.get('content', ''),
                                is_collapsible=True
                            )
                    
                    st.markdown(f'<div class="message-time" style="margin-left: 15px; color: #666; font-size: 12px;">{message.get("timestamp", "")}</div>', unsafe_allow_html=True)
                else:
                    # Handle legacy single content messages
                    st.markdown(f"""
                    <div style="display: flex; justify-content: flex-start; margin: 10px 0;">
                        <div class="bot-message">
                            {message['content']}
                            <div class="message-time">{message.get('timestamp', '')}</div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

# Use chat_input instead of text_input + button combination
user_input = st.chat_input(
    "Please enter your question...",
    disabled=st.session_state.is_streaming
)

if user_input and user_input.strip():
    st.session_state.is_streaming = True

    user_message = {
        'role': 'user',
        'content': user_input.strip(),
        'timestamp': datetime.now().strftime('%H:%M')
    }

    current_conv['messages'].append(user_message)

    # Extract content from messages for API call
    api_messages = []
    for msg in current_conv['messages']:
        if isinstance(msg.get('content'), list):
            # Combine all chunks into a single content for API
            combined_content = '\n'.join([chunk.get('content', '') for chunk in msg['content'] if chunk.get('type') == 'answer'])
            if combined_content:
                api_messages.append({'role': msg['role'], 'content': combined_content})
        else:
            api_messages.append({'role': msg['role'], 'content': msg['content']})

    st.markdown(f"""
    <div style="display: flex; justify-content: flex-end; margin: 10px 0;">
        <div class="user-message">
            {user_input.strip()}
            <div class="message-time">{datetime.now().strftime('%H:%M')}</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    assistant_placeholder = st.empty()

    # Store chunks by type
    response_chunks = []
    current_chunks = {'answer': '', 'think': '', 'error': '', 'tool': ''}

    with assistant_placeholder.container():
        response_container = st.empty()

        for chunk_data in stream_llm_response(api_messages, st.session_state.selected_model):
            chunk_type = chunk_data.get('type', 'answer')
            chunk_content = chunk_data.get('content', '')
            
            # Accumulate content by type
            current_chunks[chunk_type] += chunk_content
            
            # Clear and rebuild the streaming display
            response_container.empty()
            
            with response_container.container():
                # Create a container with limited width for streaming content
                col1, col2 = st.columns([7, 3])  # 70% width for content, 30% empty
                with col1:
                    # Display chunks in order: THINK, ERROR, TOOL first, then ANSWER
                    chunk_order = ['think', 'error', 'tool', 'answer']
                    
                    for c_type in chunk_order:
                        if current_chunks[c_type].strip():
                            chunk_id = f"streaming_{len(current_conv['messages'])}_{c_type}"
                            render_chunk_content(
                                c_type,
                                current_chunks[c_type],
                                is_collapsible=False  # Don't make collapsible during streaming
                            )
                
                    st.markdown('<div class="typing-indicator">Typing...</div>', unsafe_allow_html=True)
            
            time.sleep(0.05)  # Add small delay to simulate typing effect

    # Convert accumulated chunks to structured format, ordered properly
    final_chunks = []
    # Order: THINK, ERROR, TOOL first, then ANSWER last
    chunk_order = ['think', 'error', 'tool', 'answer']
    for c_type in chunk_order:
        if current_chunks[c_type].strip():
            final_chunks.append({
                'type': c_type,
                'content': current_chunks[c_type].strip()
            })

    assistant_message = {
        'role': 'assistant',
        'content': final_chunks if final_chunks else [{'type': 'answer', 'content': 'No response received'}],
        'timestamp': datetime.now().strftime('%H:%M'),
        'id': str(uuid.uuid4())
    }

    current_conv['messages'].append(assistant_message)

    if current_conv['title'] == 'New Conversation':
        current_conv['title'] = get_conversation_title(current_conv['messages'])

    st.session_state.is_streaming = False

    st.rerun()
