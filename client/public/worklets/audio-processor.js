class AudioProcessor extends AudioWorkletProcessor {
  constructor(options) {
    super();
    this.sampleRate = options.processorOptions.sampleRate || 16000;
    this.bufferSize = options.processorOptions.bufferSize || 4096;
    this.buffer = new Float32Array(this.bufferSize);
    this.bufferIndex = 0;
    this.isProcessing = false;
    this.lastSendTime = currentTime;
    this.MAX_BUFFER_AGE = 0.5; // 500ms
  }

  process(inputs, outputs, parameters) {
    const input = inputs[0][0];
    if (!input || input.length === 0) {
      if (currentTime - this.lastSendTime > this.MAX_BUFFER_AGE && this.bufferIndex > 0) {
        this.sendBuffer();
      }
      return true;
    }
    for (let i = 0; i < input.length; i++) {
      if (this.bufferIndex < this.bufferSize) {
        const sample = Math.max(-0.95, Math.min(0.95, input[i]));
        this.buffer[this.bufferIndex++] = sample;
      }
    }
    if ((this.bufferIndex >= this.bufferSize || currentTime - this.lastSendTime > this.MAX_BUFFER_AGE) && !this.isProcessing) {
      this.sendBuffer();
    }
    return true;
  }

  sendBuffer() {
    if (this.bufferIndex === 0) return;
    this.isProcessing = true;
    this.lastSendTime = currentTime;
    let sumSquares = 0;
    for (let i = 0; i < this.bufferIndex; i++) {
      sumSquares += this.buffer[i] * this.buffer[i];
    }
    const rms = Math.sqrt(sumSquares / this.bufferIndex);
    const level = Math.min(rms * 100 * 5, 100);
    const pcmData = new Int16Array(this.bufferIndex);
    for (let i = 0; i < this.bufferIndex; i++) {
      pcmData[i] = Math.max(-32768, Math.min(32767, Math.round(this.buffer[i] * 32767)));
    }
    this.port.postMessage({
      pcmData: pcmData.buffer,
      level: level
    }, [pcmData.buffer]);
    this.buffer = new Float32Array(this.bufferSize);
    this.bufferIndex = 0;
    this.isProcessing = false;
  }
}
registerProcessor('audio-processor', AudioProcessor); 