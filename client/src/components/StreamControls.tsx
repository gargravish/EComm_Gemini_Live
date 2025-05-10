import React, { useState, useCallback } from 'react';

interface StreamControlsProps {
  onVideoChange: (enabled: boolean) => void;
}

const StreamControls = ({ onVideoChange }: StreamControlsProps) => {
  const [video, setVideo] = useState(false);

  const handleVideo = useCallback(() => {
    setVideo(prev => {
      const newVideoState = !prev;
      console.log(`[LiveChat] User clicked ${newVideoState ? 'Start' : 'Stop'} Video, new state:`, newVideoState);
      return newVideoState;
    });
    setTimeout(() => {
      onVideoChange(!video);
    }, 0);
  }, [onVideoChange, video]);

  return (
    <div style={{ display: 'flex', gap: 12, marginBottom: 16 }}>
      <button onClick={handleVideo} style={{ padding: '8px 16px' }}>
        {video ? 'Stop Video' : 'Start Video'}
      </button>
    </div>
  );
};

export default StreamControls;