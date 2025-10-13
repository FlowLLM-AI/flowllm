import React, { useEffect, useRef } from 'react';
import './ContextMenu.css';

interface ContextMenuProps {
  position: { x: number; y: number };
  onClose: () => void;
  onShowChat: () => void;
  onMoveToCorner: () => void;
  onRandomMove: () => void;
  onToggleRunning: () => void;
  onQuit: () => void;
  isRunning: boolean;
}

const ContextMenu: React.FC<ContextMenuProps> = ({
  position,
  onClose,
  onShowChat,
  onMoveToCorner,
  onRandomMove,
  onToggleRunning,
  onQuit,
  isRunning,
}) => {
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        onClose();
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [onClose]);

  return (
    <div
      ref={menuRef}
      className="context-menu"
      style={{
        position: 'fixed',
        left: `${position.x}px`,
        top: `${position.y}px`,
      }}
    >
      <div className="context-menu-item" onClick={onShowChat}>
        💬 和我聊天
      </div>
      <div className="context-menu-separator" />
      <div className="context-menu-item" onClick={onMoveToCorner}>
        🏠 回到角落
      </div>
      <div className="context-menu-item" onClick={onRandomMove}>
        🚶 随机漫步
      </div>
      <div className="context-menu-item" onClick={onToggleRunning}>
        {isRunning ? '🛑 停止跑步' : '🏃 开始跑步'}
      </div>
      <div className="context-menu-separator" />
      <div className="context-menu-item" onClick={onQuit}>
        👋 再见~
      </div>
    </div>
  );
};

export default ContextMenu;

