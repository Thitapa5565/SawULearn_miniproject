export const BODY_POINT_IDS=[11,12,23,24,16];
export const BODY_OVERLAY_MAX_AGE=1800;

export function bodyOverlayGeometry(landmarks,measurement) {
  const points=Object.fromEntries(BODY_POINT_IDS.flatMap(id=>{
    const p=landmarks?.[id];
    return p && Number.isFinite(p.x) && Number.isFinite(p.y) && p.x>=0 && p.x<=1 && p.y>=0 && p.y<=1 &&
      Math.min(p.visibility ?? 0,p.presence ?? 0)>=.5 ? [[id,p]] : [];
  }));
  const edges=[[11,12],[12,24],[24,23],[23,11]].filter(([a,b])=>points[a] && points[b]);
  let axis=null,distance=null;
  if([11,12,23,24].every(id=>points[id])) {
    const shoulder={x:(points[11].x+points[12].x)/2,y:(points[11].y+points[12].y)/2};
    const hip={x:(points[23].x+points[24].x)/2,y:(points[23].y+points[24].y)/2};
    if(hip.y-shoulder.y>.02) {
      axis=[shoulder,hip];
      if(measurement?.status==='ready' && points[16]) {
        const wrist=points[16],x=hip.x+(wrist.y-hip.y)*(shoulder.x-hip.x)/(shoulder.y-hip.y);
        if(Number.isFinite(x))distance=[{x,y:wrist.y},wrist];
      }
    }
  }
  return {points,edges,axis,distance};
}

export function freshBodyObservation(observation,dimensions,now) {
  if(!observation || !Number.isFinite(observation.time) || now<observation.time || now-observation.time>BODY_OVERLAY_MAX_AGE)return null;
  const inputRatio=observation.width/observation.height,displayRatio=dimensions.width/dimensions.height;
  // Resizing the same image is safe; rotating the camera invalidates coordinates.
  if(!Number.isFinite(inputRatio) || !Number.isFinite(displayRatio) || Math.abs(inputRatio/displayRatio-1)>.02)return null;
  return observation;
}
