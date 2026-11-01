function radarMarkup(dimensions) {
  const names = ['探询需求','清晰互动','异议处理','医学准确','证据与风险','合规边界'];
  const point = (i, value, radius = 118) => { const a = -Math.PI/2 + i*Math.PI/3; return [210+Math.cos(a)*radius*value/2, 178+Math.sin(a)*radius*value/2]; };
  const xy = p => p.map(x=>x.toFixed(2)).join(',');
  const known = d => typeof d.rating === 'number' && Number.isFinite(d.rating) && d.rating >= 0 && d.rating <= 2;
  let svg = '<svg viewBox="0 0 420 350" role="img" aria-label="六维评分雷达图，0到2分；填色连接已评分点，虚线跨过NA，不代表该维度得分"><title>六维评分：填色连接已评分点，NA不补分</title>';
  for (const level of [1,2]) svg += `<polygon points="${dimensions.map((_,i)=>xy(point(i,level))).join(' ')}" fill="none" stroke="#d5e4dd"/><text x="215" y="${178-level*59+12}" fill="#80928b" font-size="11">${level}</text>`;
  dimensions.forEach((d,i)=> {
    const p=point(i,2),label=point(i,2,154);
    svg+=`<line x1="210" y1="178" x2="${p[0]}" y2="${p[1]}" stroke="#d5e4dd" ${known(d)?'':'stroke-dasharray="4 4"'}/><text x="${label[0]}" y="${label[1]}" text-anchor="middle" font-size="12" fill="${known(d)?'#234f47':'#86938d'}">${names[i]}<tspan x="${label[0]}" dy="18">${known(d)?d.rating+' / 2':'NA · 未评分'}</tspan></text>`;
  });
  const scored=dimensions.map((d,i)=>({d,i})).filter(({d})=>known(d));
  if(scored.length>=3) svg+=`<polygon data-score-area="true" points="${scored.map(({d,i})=>xy(point(i,d.rating))).join(' ')}" fill="#0a7264" fill-opacity="0.18" stroke="none"/>`;
  if(scored.length>=2) scored.forEach(({d,i},n)=>{
    if(scored.length===2&&n===1)return;
    const next=scored[(n+1)%scored.length],a=point(i,d.rating),b=point(next.i,next.d.rating);
    const gap=(next.i-i+dimensions.length)%dimensions.length!==1;
    svg+=`<line data-score-edge="${gap?'gap':'rated'}" x1="${a[0]}" y1="${a[1]}" x2="${b[0]}" y2="${b[1]}" stroke="#0a7264" stroke-width="2.5" stroke-linejoin="round" ${gap?'stroke-dasharray="5 4"':''}/>`;
  });
  dimensions.forEach((d,i)=> {
    if(known(d)){const p=point(i,d.rating);svg+=`<circle data-dimension="${d.id}" cx="${p[0]}" cy="${p[1]}" r="5" fill="#0a7264" stroke="white" stroke-width="2"><title>${names[i]}：${d.rating} / 2</title></circle>`;}
  });
  return svg+'</svg>';
}
if(typeof module!=='undefined') module.exports={radarMarkup};
