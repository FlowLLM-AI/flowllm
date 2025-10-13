import React, { useState, useRef, useEffect } from 'react';
import ChatBubble from './ChatBubble';
import ContextMenu from './ContextMenu';
import './DesktopDog.css';

const DesktopDog: React.FC = () => {
  const [position, setPosition] = useState({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState(false);
  const [showChat, setShowChat] = useState(false);
  const [showContextMenu, setShowContextMenu] = useState(false);
  const [contextMenuPos, setContextMenuPos] = useState({ x: 0, y: 0 });
  const [isRunning, setIsRunning] = useState(false);
  const [runDirection, setRunDirection] = useState(1); // 1 = right, -1 = left
  const [expression, setExpression] = useState('normal');
  
  const dragStart = useRef({ x: 0, y: 0 });
  const lastClickTime = useRef(0);
  const runAnimationFrame = useRef<number>();

  // Initialize position
  useEffect(() => {
    if (typeof window !== 'undefined' && (window as any).ipcRenderer) {
      (window as any).ipcRenderer.invoke('get-screen-size').then((size: { width: number; height: number }) => {
        setPosition({ x: size.width - 200, y: size.height - 200 });
      });
    } else {
      // Fallback for browser
      setPosition({ x: window.innerWidth - 200, y: window.innerHeight - 200 });
    }
  }, []);

  // Running animation
  useEffect(() => {
    if (isRunning) {
      const animate = () => {
        setPosition((prev) => {
          let newX = prev.x + (runDirection * 8);
          
          const screenWidth = window.innerWidth;
          if (newX <= 0) {
            newX = 0;
            setRunDirection(1);
          } else if (newX >= screenWidth - 150) {
            newX = screenWidth - 150;
            setRunDirection(-1);
          }
          
          return { x: newX, y: prev.y };
        });
        
        runAnimationFrame.current = requestAnimationFrame(animate);
      };
      
      runAnimationFrame.current = requestAnimationFrame(animate);
      
      return () => {
        if (runAnimationFrame.current) {
          cancelAnimationFrame(runAnimationFrame.current);
        }
      };
    }
  }, [isRunning, runDirection]);

  const handleMouseDown = (e: React.MouseEvent) => {
    if (e.button === 0) {
      // Left click
      dragStart.current = {
        x: e.clientX - position.x,
        y: e.clientY - position.y,
      };
      setIsDragging(true);
      setExpression('dragging');
    } else if (e.button === 2) {
      // Right click
      e.preventDefault();
      setShowContextMenu(true);
      setContextMenuPos({ x: e.clientX, y: e.clientY });
    }
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (isDragging) {
      const newX = Math.max(0, Math.min(e.clientX - dragStart.current.x, window.innerWidth - 150));
      const newY = Math.max(0, Math.min(e.clientY - dragStart.current.y, window.innerHeight - 180));
      setPosition({ x: newX, y: newY });
    }
  };

  const handleMouseUp = (e: React.MouseEvent) => {
    if (e.button === 0 && isDragging) {
      setIsDragging(false);
      setExpression('normal');
      
      // Check for click vs drag
      const distance = Math.sqrt(
        Math.pow(e.clientX - (position.x + dragStart.current.x), 2) +
        Math.pow(e.clientY - (position.y + dragStart.current.y), 2)
      );
      
      if (distance < 5) {
        const now = Date.now();
        if (now - lastClickTime.current < 300) {
          // Double click - toggle running
          handleDoubleClick();
        } else {
          // Single click - show chat
          handleClick();
        }
        lastClickTime.current = now;
      }
    }
  };

  const handleClick = () => {
    setShowChat(true);
    setExpression('happy');
  };

  const handleDoubleClick = () => {
    setIsRunning(!isRunning);
    setExpression(isRunning ? 'normal' : 'running');
  };

  const handleCloseChat = () => {
    setShowChat(false);
    setExpression('normal');
  };

  const handleQuit = () => {
    if (typeof window !== 'undefined' && (window as any).ipcRenderer) {
      (window as any).ipcRenderer.invoke('quit-app');
    } else {
      window.close();
    }
  };

  const moveToCorner = () => {
    const screenWidth = window.innerWidth;
    const screenHeight = window.innerHeight;
    setPosition({ x: screenWidth - 200, y: screenHeight - 200 });
    setShowContextMenu(false);
  };

  const randomMove = () => {
    const newX = Math.random() * (window.innerWidth - 200) + 50;
    const newY = Math.random() * (window.innerHeight - 230) + 50;
    setPosition({ x: newX, y: newY });
    setShowContextMenu(false);
  };

  return (
    <>
      <div
        className={`desktop-dog ${isDragging ? 'dragging' : ''} ${isRunning ? 'running' : ''}`}
        style={{
          position: 'fixed',
          left: `${position.x}px`,
          top: `${position.y}px`,
          cursor: isDragging ? 'grabbing' : 'grab',
        }}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onContextMenu={(e) => e.preventDefault()}
      >
        <DogSVG expression={expression} />
        {isDragging && <div className="drag-text">汪~ 🐕</div>}
      </div>

      {showChat && (
        <ChatBubble
          dogPosition={position}
          onClose={handleCloseChat}
        />
      )}

      {showContextMenu && (
        <ContextMenu
          position={contextMenuPos}
          onClose={() => setShowContextMenu(false)}
          onShowChat={() => {
            setShowChat(true);
            setShowContextMenu(false);
          }}
          onMoveToCorner={moveToCorner}
          onRandomMove={randomMove}
          onToggleRunning={() => {
            handleDoubleClick();
            setShowContextMenu(false);
          }}
          onQuit={handleQuit}
          isRunning={isRunning}
        />
      )}
    </>
  );
};

interface DogSVGProps {
  expression: string;
}

const DogSVG: React.FC<DogSVGProps> = ({ expression }) => {
  return (
    <svg width="150" height="180" viewBox="0 0 150 180" xmlns="http://www.w3.org/2000/svg">
      {/* Shadow */}
      <ellipse cx="75" cy="170" rx="50" ry="12" fill="rgba(0,0,0,0.2)" />
      
      {/* Tail */}
      <path
        d="M 115 140 Q 135 130, 130 110 Q 128 95, 120 100"
        fill="none"
        stroke="#8B6F47"
        strokeWidth="12"
        strokeLinecap="round"
      />
      
      {/* Body */}
      <ellipse cx="75" cy="130" rx="45" ry="35" fill="#A0826D" />
      
      {/* Legs */}
      <rect x="50" y="155" width="12" height="25" rx="6" fill="#8B6F47" />
      <rect x="88" y="155" width="12" height="25" rx="6" fill="#8B6F47" />
      
      {/* Paws */}
      <ellipse cx="56" cy="175" rx="8" ry="5" fill="#6B5D3F" />
      <ellipse cx="94" cy="175" rx="8" ry="5" fill="#6B5D3F" />
      
      {/* Head */}
      <ellipse cx="75" cy="75" rx="40" ry="45" fill="#A0826D" />
      
      {/* Ears */}
      <ellipse cx="50" cy="50" rx="18" ry="28" fill="#8B6F47" />
      <ellipse cx="100" cy="50" rx="18" ry="28" fill="#8B6F47" />
      
      {/* Inner ears */}
      <ellipse cx="50" cy="55" rx="10" ry="18" fill="#D4A574" />
      <ellipse cx="100" cy="55" rx="10" ry="18" fill="#D4A574" />
      
      {/* Snout */}
      <ellipse cx="75" cy="85" rx="25" ry="20" fill="#C4956D" />
      
      {/* Eyes */}
      {expression === 'dragging' ? (
        <>
          <ellipse cx="60" cy="70" rx="8" ry="10" fill="white" />
          <ellipse cx="90" cy="70" rx="8" ry="10" fill="white" />
          <ellipse cx="60" cy="72" rx="4" ry="5" fill="#2C1810" />
          <ellipse cx="90" cy="72" rx="4" ry="5" fill="#2C1810" />
        </>
      ) : (
        <>
          <ellipse cx="60" cy="70" rx="8" ry="10" fill="white" />
          <ellipse cx="90" cy="70" rx="8" ry="10" fill="white" />
          <ellipse cx="60" cy="72" rx="5" ry="6" fill="#2C1810" />
          <ellipse cx="90" cy="72" rx="5" ry="6" fill="#2C1810" />
          <ellipse cx="58" cy="69" rx="2" ry="3" fill="white" opacity="0.8" />
          <ellipse cx="88" cy="69" rx="2" ry="3" fill="white" opacity="0.8" />
        </>
      )}
      
      {/* Nose */}
      <ellipse cx="75" cy="90" rx="6" ry="5" fill="#2C1810" />
      <ellipse cx="74" cy="89" rx="2" ry="2" fill="white" opacity="0.6" />
      
      {/* Mouth */}
      {expression === 'happy' || expression === 'running' ? (
        <path
          d="M 75 93 Q 70 98, 65 95 M 75 93 Q 80 98, 85 95"
          fill="none"
          stroke="#2C1810"
          strokeWidth="1.5"
          strokeLinecap="round"
        />
      ) : (
        <path
          d="M 75 93 L 75 97 M 75 97 Q 70 99, 67 97 M 75 97 Q 80 99, 83 97"
          fill="none"
          stroke="#2C1810"
          strokeWidth="1.5"
          strokeLinecap="round"
        />
      )}
      
      {/* Tongue (when happy/running) */}
      {(expression === 'happy' || expression === 'running') && (
        <ellipse cx="75" cy="102" rx="6" ry="4" fill="#FF6B9D" />
      )}
      
      {/* Spots */}
      <ellipse cx="95" cy="75" rx="8" ry="10" fill="#6B5D3F" opacity="0.5" />
      <ellipse cx="55" cy="135" rx="10" ry="8" fill="#6B5D3F" opacity="0.5" />
    </svg>
  );
};

export default DesktopDog;

