import { useEffect, useRef, useImperativeHandle, forwardRef } from 'react';

interface VideoStreamProps {
  enabled: boolean;
}

export interface VideoStreamHandle {
  getLatestFrame: () => Promise<string | null>;
}

const VideoStream = forwardRef<VideoStreamHandle, VideoStreamProps>(({ enabled }, ref) => {
  const videoRef = useRef<HTMLVideoElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const latestFrameRef = useRef<string | null>(null);

  // Helper: capture a frame and store as data URL
  const captureFrame = async (): Promise<string | null> => {
    if (!videoRef.current) return null;
    const video = videoRef.current;
    if (video.videoWidth === 0 || video.videoHeight === 0) return null;
    const canvas = document.createElement('canvas');
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const ctx = canvas.getContext('2d');
    if (!ctx) return null;
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
    return await new Promise((resolve) => {
      canvas.toBlob((blob) => {
        if (!blob) return resolve(null);
        const reader = new FileReader();
        reader.onloadend = () => {
          const dataUrl = reader.result as string;
          latestFrameRef.current = dataUrl;
          resolve(dataUrl);
        };
        reader.readAsDataURL(blob);
      }, 'image/jpeg', 0.8);
    });
  };

  // Expose getLatestFrame to parent via ref
  useImperativeHandle(ref, () => ({
    getLatestFrame: async () => {
      return await captureFrame();
    }
  }));

  useEffect(() => {
    if (!enabled) return;
    let stopped = false;
    async function startVideo() {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ video: true });
        streamRef.current = stream;
        if (videoRef.current) videoRef.current.srcObject = stream;
        console.log('[LiveChat] Video capture started');
      } catch (err) {
        console.error('[LiveChat] Video capture error:', err);
      }
    }
    startVideo();
    return () => {
      stopped = true;
      streamRef.current?.getTracks().forEach(track => track.stop());
      if (videoRef.current) videoRef.current.srcObject = null;
      console.log('[LiveChat] Video capture stopped');
    };
  }, [enabled]);

  return <video ref={videoRef} autoPlay playsInline style={{ width: '100%', maxHeight: 320, borderRadius: 8, background: '#000' }} />;
});

export default VideoStream; 