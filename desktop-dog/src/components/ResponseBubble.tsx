import React, { useEffect, useRef, useState } from 'react';
import './ResponseBubble.css';

interface ResponseBubbleProps {
  dogPosition: { x: number; y: number };
  responses: Array<{ type: string; content: string }>;
  onClose: () => void;
}

const ResponseBubble: React.FC<ResponseBubbleProps> = ({ dogPosition, responses, onClose }) => {
  const [bubbleHeight, setBubbleHeight] = useState(150);
  const contentRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (contentRef.current) {
      const contentHeight = contentRef.current.scrollHeight;
      const newHeight = Math.min(Math.max(150, contentHeight + 80), 500);
      setBubbleHeight(newHeight);
    }
  }, [responses]);

  // Scroll to bottom when new content arrives
  useEffect(() => {
    if (contentRef.current) {
      contentRef.current.scrollTop = contentRef.current.scrollHeight;
    }
  }, [responses]);

  const getChunkStyle = (type: string): { color: string; prefix: string } => {
    const styles: Record<string, { color: string; prefix: string }> = {
      answer: { color: '#333333', prefix: '' },
      think: { color: '#FF8C00', prefix: '🤔 ' },
      error: { color: '#DC143C', prefix: '❌ ' },
      tool: { color: '#1E90FF', prefix: '🔧 ' },
    };
    return styles[type] || styles.answer;
  };

  // Calculate bubble position (right side of dog)
  const bubbleX = Math.min(dogPosition.x + 130, window.innerWidth - 390);
  const bubbleY = Math.max(20, dogPosition.y - 50);

  return (
    <div
      className="response-bubble"
      style={{
        position: 'fixed',
        left: `${bubbleX}px`,
        top: `${bubbleY}px`,
      }}
    >
      <div
        className="response-bubble-container"
        style={{
          height: `${bubbleHeight}px`,
        }}
      >
        <div className="response-bubble-header">
          <span className="response-bubble-title">🐾 AI回答</span>
          <button className="close-button" onClick={onClose}>
            ✕
          </button>
        </div>
        <div className="response-content" ref={contentRef}>
          {responses.map((response, index) => {
            // Only render answer, think, error, and tool types
            if (!['answer', 'think', 'error', 'tool'].includes(response.type)) {
              return null;
            }

            const style = getChunkStyle(response.type);
            return (
              <span key={index} style={{ color: style.color }}>
                {style.prefix}
                {response.content}
              </span>
            );
          })}
          {responses.length === 0 && (
            <span style={{ color: '#999' }}>思考中...</span>
          )}
        </div>
      </div>
    </div>
  );
};

export default ResponseBubble;

