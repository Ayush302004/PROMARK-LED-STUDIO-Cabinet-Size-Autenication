'use strict';
function updateStudioSummary(){
 const target=$('studio-cost-lines');if(!target)return;
 const amount=v=>Number(v).toLocaleString('en-IN',{style:'currency',currency:'INR',maximumFractionDigits:2});
 const controller=controllers.find(c=>c.id===$('controller').value);
 const lines=[['LED model',product?.name||'Select model']];
 const gst=Number($('q_gst').value||0)/100;
 let total=0,hasPricedRate=false;
 if(result){
  const area=quotationAreaSqft();
  const raw=$('q_wall_rate').value;
  if(raw!==''&&Number.isFinite(Number(raw))){const cost=Number(raw)*area;total+=cost*(1+gst);hasPricedRate=true;lines.push(['LED wall, incl. GST',amount(cost*(1+gst))]);}
 }
 if(controller?.rate_inr!=null){
  const quantity=Math.max(0,Number($('q_controller_qty').value||1));
  const cost=controller.rate_inr*quantity;total+=cost*(1+gst);hasPricedRate=true;
  lines.push(['LED Wall Controller, incl. GST',amount(cost*(1+gst))]);
 }
 for(const [label,id,quantityId] of [['UniPole','q_mount_rate','q_mount_qty'],['Installation','q_installation_rate',null]]){
  const raw=$(id).value;
  if(raw!==''&&Number.isFinite(Number(raw))){
   const cost=Number(raw)*(quantityId?Number($(quantityId).value||1):1);
   total+=cost*(1+gst);hasPricedRate=true;lines.push([label+', incl. GST',amount(cost*(1+gst))]);
  }else lines.push([label,'Company actual price']);
 }
 target.innerHTML=lines.map(([label,value])=>`<div><dt>${esc(label)}</dt><dd>${esc(value)}</dd></div>`).join('');
 $('studio-total').textContent=hasPricedRate?amount(total):amount(0);
 $('studio-rate-status').textContent='Live total includes every available priced row and updates when quantities or GST change.';
 $('studio-catalogue-count').textContent=catalogue.length+' display models · '+controllers.length+' controllers';
}
const originalFullPrices=updateFullPrices;
updateFullPrices=function(){originalFullPrices();updateStudioSummary();};
$('studio-download').onclick=()=>$('download-quotation').click();
$('studio-quote-details').onclick=()=>{showTab('results');window.scrollTo({top:0,behavior:'smooth'});};
updateStudioSummary();
