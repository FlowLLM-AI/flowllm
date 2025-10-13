import React, { useState, useRef, useEffect } from 'react';
import ResponseBubble from './ResponseBubble';
import { streamChat } from '../services/llmService';
import './ChatBubble.css';

interface ChatBubbleProps {
  dogPosition: { x: number; y: number };
  onClose: () => void;
}

const ChatBubble: React.FC<ChatBubbleProps> = ({ dogPosition, onClose }) => {
  const [message, setMessage] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const [showResponse, setShowResponse] = useState(false);
  const [responses, setResponses] = useState<Array<{ type: string; content: string }>>([]);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  useEffect(() => {
    textareaRef.current?.focus();
  }, []);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleSend = async () => {
    const trimmedMessage = message.trim();
    if (!trimmedMessage || isStreaming) return;

    setMessage('');
    setIsStreaming(true);
    setShowResponse(true);
    setResponses([]);

    abortControllerRef.current = new AbortController();

    try {
      await streamChat(
        trimmedMessage,
        (chunkType: string, chunkContent: string) => {
          setResponses((prev) => [...prev, { type: chunkType, content: chunkContent }]);
        },
        abortControllerRef.current.signal
      );
    } catch (error: any) {
      if (error.name !== 'AbortError') {
        console.error('Chat error:', error);
        setResponses((prev) => [
          ...prev,
          { type: 'error', content: `抱歉，出错了: ${error.message}` },
        ]);
      }
    } finally {
      setIsStreaming(false);
    }
  };

  const handleCloseResponse = () => {
    setShowResponse(false);
    setResponses([]);
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
  };

  // Calculate bubble position (left side of dog)
  const bubbleX = Math.max(20, dogPosition.x - 420);
  const bubbleY = Math.max(20, dogPosition.y - 150);

  return (
    <>
      <div
        className="chat-bubble"
        style={{
          position: 'fixed',
          left: `${bubbleX}px`,
          top: `${bubbleY}px`,
        }}
      >
        <div className="chat-bubble-container">
          <div className="chat-bubble-header">
            <span className="chat-bubble-title">💬 和我聊天吧~</span>
            <button className="close-button" onClick={onClose}>
              ✕
            </button>
          </div>
          <textarea
            ref={textareaRef}
            className="chat-input"
            placeholder="输入你想说的话...（按回车发送）"
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={isStreaming}
          />
        </div>
      </div>

      {showResponse && (
        <ResponseBubble
          dogPosition={dogPosition}
          responses={responses}
          onClose={handleCloseResponse}
        />
      )}
    </>
  );
};

export default ChatBubble;

