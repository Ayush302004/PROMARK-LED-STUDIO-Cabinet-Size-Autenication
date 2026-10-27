'use strict';
function updateStudioSummary(){
 const target=$('studio-cost-lines');if(!target)return;
 const amount=v=>Number(v).toLocaleString('en-IN',{style:'currency',currency:'INR',maximumFractionDigits:2});
 const controller=controllers.find(c=>c.id===$('controller').value);
 const lines=[['LED model',product?.name||'Select model'],['Controller',controller?.name||'Not selected']];
 let total=0,pending=!result;
 if(result){
  const area=quotationAreaSqft();
  for(const [label,id,factor] of [['LED wall','q_wall_rate',area]]){
   const raw=$(id).value;if(raw===''){pending=true;lines.push([label,'Rate required']);}else{const cost=Number(raw)*factor;total+=cost;lines.push([label,amount(cost)]);}
  }
 }
 if(controller?.rate_inr!=null){
  const cost=controller.rate_inr*Number($('q_controller_qty').value||1);total+=cost;lines.push(['Controller cost',amount(cost)]);
 }else{pending=true;lines.push(['Controller cost','Select a controller']);}
 for(const label of ['Mounting Structure','Installation','UPS','Cabling'])lines.push([label,'Company actual price']);
 pending=true;
 target.innerHTML=lines.map(([label,value])=>`<div><dt>${esc(label)}</dt><dd>${esc(value)}</dd></div>`).join('');
 $('studio-total').textContent=pending?'Rates pending':amount(total*(1+Number($('q_gst').value||0)/100));
 $('studio-rate-status').textContent=pending?'Controller rate is included where selected. Enter company actual prices for mounting structure, installation, UPS and cabling in the Excel quotation.':'Includes '+$('q_gst').value+'% GST. Final rounding is applied in Excel.';
 $('studio-catalogue-count').textContent=catalogue.length+' display models · '+controllers.length+' controllers';
}
const originalFullPrices=updateFullPrices;
updateFullPrices=function(){originalFullPrices();updateStudioSummary();};
$('studio-download').onclick=()=>$('download-quotation').click();
$('studio-quote-details').onclick=()=>{showTab('results');window.scrollTo({top:0,behavior:'smooth'});};
updateStudioSummary();
