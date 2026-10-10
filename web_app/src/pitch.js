// YIN difference function with cumulative normalization and sub-sample interpolation.
// Decimation keeps microphone analysis small; no sound is sent to the server.
export const PITCH_TOLERANCE_HZ=5, PITCH_METER_RANGE_HZ=20;
export const NOTE_TABLE = [
  ['do','โด',228.31,'สายทุ้ม','สายเปล่า'],['re','เร',256.26,'สายทุ้ม','นิ้วชี้'],
  ['mi','มี',287.67,'สายทุ้ม','นิ้วกลาง'],['fa','ฟา',304.77,'สายทุ้ม','นิ้วนาง'],
  ['sol','ซอล',342.20,'สายเอก','สายเปล่า'],['la','ลา',384.27,'สายเอก','นิ้วชี้'],
  ['ti','ที',431.42,'สายเอก','นิ้วกลาง'],['do-high','โดสูง',457.15,'สายเอก','นิ้วนาง'],
  ['re-high','เรสูง',512.52,'สายเอก','นิ้วก้อย'],
].map(([id,name,hz,string,finger])=>({id,name,hz,string,finger}));

export function detectPitch(input,sampleRate) {
  const step=sampleRate>=32000 ? 2 : 1, rate=sampleRate/step;
  const size=Math.floor(input.length/step), values=new Float32Array(size);
  let mean=0,energy=0;
  for(let i=0;i<size;i++){values[i]=input[i*step];mean+=values[i];}
  mean/=size;
  for(let i=0;i<size;i++){values[i]-=mean;energy+=values[i]*values[i];}
  const rms=Math.sqrt(energy/size);
  if(!Number.isFinite(rms)||rms<.002)return null;
  const low=Math.floor(rate/1200),high=Math.min(Math.ceil(rate/80),Math.floor(size/2)-1);
  if(high<=low)return null;
  const difference=new Float32Array(high+2), window=size-high-2;
  let sum=0;
  for(let lag=1;lag<=high+1;lag++) {
    let d=0;for(let i=0;i<window;i++){const delta=values[i]-values[i+lag];d+=delta*delta;}
    sum+=d;difference[lag]=sum ? d*lag/sum : 1;
  }
  let lag=low;
  for(;lag<high;lag++)if(difference[lag]<.12){while(lag<high&&difference[lag+1]<difference[lag])lag++;break;}
  if(lag>=high||difference[lag]>.12)return null;
  // A dominant overtone can produce an early, shallow valley. Prefer its
  // double/triple period only when it fits the waveform substantially better.
  // This uses the signal alone, never the selected target note.
  if(difference[lag]>.025){
    const first=lag;
    for(const multiple of [2,3]){
      let candidate=Math.round(first*multiple);
      if(candidate+2>high)continue;
      for(let j=candidate-2;j<=first*multiple+2&&j<=high;j++)if(difference[j]<difference[candidate])candidate=j;
      if(difference[candidate]<difference[lag]*.3)lag=candidate;
    }
  }
  const a=difference[lag-1],b=difference[lag],c=difference[lag+1],den=a-2*b+c;
  const refined=lag+(Math.abs(den)>1e-8 ? Math.max(-1,Math.min(1,(a-c)/(2*den))) : 0);
  const hz=rate/refined;
  return hz>=80&&hz<=1200 ? {hz,clarity:1-b,rms} : null;
}

export function pitchFeedback(hz,note,toleranceHz=PITCH_TOLERANCE_HZ) {
  if(!Number.isFinite(hz)||hz<=0)return null;
  const deltaHz=hz-note.hz,cents=1200*Math.log2(hz/note.hz);
  // Include both exact boundaries despite floating-point subtraction.
  const state=Math.abs(deltaHz)<=toleranceHz+1e-9 ? 'tuned' : deltaHz<0 ? 'low' : 'high';
  const advice=state==='tuned' ? 'คงตำแหน่งนี้ แล้วสีต่อเนื่อง' : note.finger==='สายเปล่า' ? 'สายเปล่า: ปรับลูกบิดตั้งสาย' :
    state==='low' ? 'เลื่อนนิ้วเข้าหาหย่องเล็กน้อย' : 'เลื่อนนิ้วออกจากหย่องเล็กน้อย';
  return {deltaHz,cents,state,label:{tuned:'ตรงคีย์แล้ว',low:'ต่ำไป',high:'สูงไป'}[state],advice};
}
