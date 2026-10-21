'use strict';
// Match supplied LED video-controller limits. A 4K media output alone is not
// evidence of LED loading capacity, so multimedia players are not auto-selected.
function recommendVideoController(controllers, width, height){
 if(!Number.isSafeInteger(width)||!Number.isSafeInteger(height)||width<=0||height<=0)return null;
 const total=width*height;
 return controllers.filter(c=>c.kind==='LED Wall Controller'&&Number.isFinite(c.max_pixels)&&c.max_pixels>total&&Number.isFinite(c.max_width)&&c.max_width>=width&&Number.isFinite(c.max_height)&&c.max_height>=height)
  .sort((a,b)=>a.max_pixels-b.max_pixels||a.name.localeCompare(b.name))[0]||null;
}
if(typeof module!=='undefined')module.exports={recommendVideoController};
