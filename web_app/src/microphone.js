// Keep the analysis graph running on browsers that suspend unconnected outputs.
// The destination receives zero gain: microphone audio never plays on speakers.
export function microphoneGraph(context,stream) {
  const source=context.createMediaStreamSource(stream),analyser=context.createAnalyser(),silent=context.createGain();
  analyser.fftSize=4096;silent.gain.value=0;
  source.connect(analyser);analyser.connect(silent);silent.connect(context.destination);
  return {source,analyser,silent};
}
export function inputLevel(buffer) {
  let energy=0;for(const x of buffer)energy+=x*x;
  const rms=Math.sqrt(energy/buffer.length)||0;
  return {rms,percent:Math.max(0,Math.min(100,(20*Math.log10(Math.max(rms,1e-6))+70)/70*100))};
}
export function microphoneMessage({state,muted,ended,rms}) {
  if(ended)return 'ไมค์หยุดแล้ว · กดเปิดไมค์อีกครั้ง';
  if(muted)return 'ไมค์ถูกพักโดยเบราว์เซอร์ · ลองเปิดไมค์ใหม่';
  if(state!=='running')return 'ระบบเสียงถูกพัก · กดเริ่มระบบเสียงต่อ';
  if(rms<.00001)return 'ยังไม่มีเสียงเข้าไมค์ · ตรวจไมค์หรือสิทธิ์ของเบราว์เซอร์';
  if(rms<.002)return 'เสียงเข้าเบา · ลองสีดังขึ้นหรือวางไมค์ใกล้ซอ';
  return 'ไมค์รับเสียงแล้ว';
}
