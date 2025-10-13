// LLM Service for streaming chat
// You can configure this to use OpenAI, Anthropic, or any compatible API

interface Message {
  role: 'system' | 'user' | 'assistant';
  content: string;
}

// Load configuration from environment variables
const API_KEY = import.meta.env.VITE_API_KEY || '';
const API_BASE = import.meta.env.VITE_API_BASE || 'https://dashscope.aliyuncs.com/compatible-mode/v1';
const MODEL = import.meta.env.VITE_MODEL || 'qwen-max';

export async function streamChat(
  userMessage: string,
  onChunk: (chunkType: string, chunkContent: string) => void,
  signal?: AbortSignal
): Promise<void> {
  const messages: Message[] = [
    {
      role: 'system',
      content: '你是一个可爱的桌面宠物小狗助手，用温暖友好的语气回答问题。回答要简洁但有帮助。',
    },
    {
      role: 'user',
      content: userMessage,
    },
  ];

  try {
    const response = await fetch(`${API_BASE}/chat/completions`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${API_KEY}`,
      },
      body: JSON.stringify({
        model: MODEL,
        messages: messages,
        stream: true,
        temperature: 0.7,
      }),
      signal,
    });

    if (!response.ok) {
      throw new Error(`API error: ${response.status} ${response.statusText}`);
    }

    const reader = response.body?.getReader();
    if (!reader) {
      throw new Error('No response body');
    }

    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';

      for (const line of lines) {
        const trimmedLine = line.trim();
        if (!trimmedLine || trimmedLine === 'data: [DONE]') continue;

        if (trimmedLine.startsWith('data: ')) {
          try {
            const jsonStr = trimmedLine.substring(6);
            const data = JSON.parse(jsonStr);

            if (data.choices && data.choices.length > 0) {
              const delta = data.choices[0].delta;
              
              if (delta.content) {
                onChunk('answer', delta.content);
              }

              // Handle reasoning content if available (for models that support it)
              if (delta.reasoning_content) {
                onChunk('think', delta.reasoning_content);
              }
            }
          } catch (e) {
            console.error('Error parsing chunk:', e, trimmedLine);
          }
        }
      }
    }
  } catch (error: any) {
    if (error.name === 'AbortError') {
      throw error;
    }
    console.error('Stream error:', error);
    throw new Error(error.message || 'Failed to connect to AI service');
  }
}

