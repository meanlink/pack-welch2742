import {datasets} from '../api/entities.js';
import {workspace} from '../stores/workspace.js';
import {session} from '../stores/session.js';
import {heading} from '../components/common/shell.js';
import {table} from '../components/common/table.js';
import {esc,notify,date} from '../utils/dom.js';
import {submit} from '../hooks/forms.js';
import {parseCSV} from '../utils/csv.js';

const isAdmin=()=>session.user.role==='admin';
function previewColumns(meta,selected){
 const cols=[...meta.columns,{key:'excluded',label:'隔离状态'}];
 return cols;
}
function previewRows(selected){
 return (selected?.records||[]).slice(0,30).map(r=>({...r,excluded:r.excluded?'已隔离':'正常'}));
}
function exclusionPanel(selected){
 const active=(selected?.exclusions||[]).filter(e=>e.active);
 const history=(selected?.exclusions||[]).filter(e=>!e.active);
 return '<section class="panel"><div class="section-title"><h2>故障片段隔离</h2><span>隔离后分析按实际使用片段追溯影响</span></div>'
  +(isAdmin()?'<form id="exclusion-form"><label>片段编号（run，多个用逗号分隔；也可在下方预览表点选）<input name="runs" required placeholder="例如：YC-A003, YC-B011"></label><label>隔离原因（必填，随审计与失效标记留痕）<textarea name="reason" rows="3" required minlength="2" placeholder="例如：秒表停走 12 秒，该段节拍失真"></textarea></label><div class="row-actions"><button type="button" class="button" id="impact-btn">预览受影响分析</button><button type="submit" class="primary">确认隔离片段</button></div><p class="hint">隔离立即生效：受影响的旧分析标记失效、关联简报暂停分发；已发文件保留并标明失效。未使用这些片段的分析照常运行。</p></form>':'<p class="hint">仅业务负责人可隔离或恢复片段；你可以查看隔离记录与原因。</p>')
  +'<div id="impact-box"></div>'
  +'<div class="section-title" style="margin-top:24px"><h2>生效中的隔离</h2><span>'+active.length+' 个片段</span></div>'
  +(active.length?'<div class="exclusion-list">'+active.map(e=>'<article class="exclusion-item"><div><strong>'+esc(e.run)+'</strong><p>'+esc(e.reason)+'</p><small>'+date(e.created_at)+'</small></div>'+(isAdmin()?'<button class="button small" data-restore="'+e.id+'">恢复片段</button>':'')+'</article>').join('')+'</div>':'<p class="empty">当前没有隔离片段。</p>')
  +(history.length?'<div class="section-title" style="margin-top:20px"><h2>恢复历史</h2><span>'+history.length+' 条</span></div><div class="exclusion-list muted-list">'+history.map(e=>'<article class="exclusion-item"><div><strong>'+esc(e.run)+'</strong><p>'+esc(e.reason)+'</p><small>已于 '+(e.restored_at?date(e.restored_at):'—')+' 恢复</small></div></article>').join('')+'</div>':'')
  +'</section>';
}
export async function dataPage(datasetId){
 workspace.datasets=await datasets.list();
 const wanted=datasetId?Number(datasetId):(workspace.selectedDataset||workspace.datasets[0]?.id);
 let selected=wanted&&workspace.datasets.some(d=>d.id===wanted)?await datasets.get(wanted):(workspace.datasets[0]?await datasets.get(workspace.datasets[0].id):null);
 if(selected)workspace.selectedDataset=selected.id;
 let m=workspace.meta;
 return heading('02 / DATA INTAKE','数据接入、片段隔离与批次追溯','保留原始业务字段、来源和内容指纹。秒表故障片段可登记原因并隔离；影响范围按每个分析实际用到的片段追溯。')
  +'<div class="dataset-grid"><section class="panel"><div class="section-title"><h2>业务批次</h2><span>'+workspace.datasets.length+' 批</span></div><div class="batch-list">'+workspace.datasets.map(d=>'<button class="batch-item'+(selected&&d.id===selected.id?' selected':'')+'" data-dataset="'+d.id+'"><strong>'+esc(d.name)+'</strong><span>'+d.rows+' 条 · '+esc(d.source)+'</span><small>SHA256 '+esc(d.checksum.slice(0,18))+'…</small></button>').join('')+'</div><div class="section-title"><h2>接入新数据</h2></div><form id="dataset-form"><label>批次名称<input name="name" required minlength="2" placeholder="例如：11 月复测批次"></label><label>上传 CSV 或 JSON<input type="file" id="file-input" accept=".json,.csv"></label><label>记录 JSON<textarea name="records" rows="6" placeholder="粘贴 JSON 数组，或先选择上方文件" required></textarea></label><p class="hint">字段：'+m.columns.map(c=>esc(c.key)+' / '+esc(c.label)).join('，')+'。5–5,000 条记录。</p><button type="submit" class="primary" '+(session.user.role==='viewer'?'disabled':'')+'>校验并接入批次</button></form></section>'
  +'<section class="panel"><div class="section-title"><h2 id="preview-name">'+esc(selected?.name||'尚无批次')+'</h2><span>预览前 30 条 · 隔离片段有标记</span></div><div id="data-preview">'+table(previewColumns(m,selected),previewRows(selected))+'</div>'+(selected&&isAdmin()?'<p class="hint">点击表格中正常片段的行可填入隔离框。</p>':'')+'</section>'
  +(selected?exclusionPanel(selected):'')+'</div>';
}
export function bindData(refresh){
 let source='manual.json';
 document.querySelector('#file-input')?.addEventListener('change',async e=>{try{const file=e.target.files[0];if(!file)return;source=file.name;const text=await file.text(),records=file.name.endsWith('.csv')?parseCSV(text):JSON.parse(text);document.querySelector('[name=records]').value=JSON.stringify(records,null,2);}catch(error){notify(error.message,true);}});
 document.querySelectorAll('[data-dataset]').forEach(button=>button.onclick=async()=>{workspace.selectedDataset=Number(button.dataset.dataset);location.hash='#/datasets/'+button.dataset.dataset;});
 const form=document.querySelector('#dataset-form');
 if(form)submit(form,async f=>{await datasets.create({name:f.get('name'),source,records:JSON.parse(f.get('records'))});notify('数据已接入，可前往工作台执行分析');await refresh();});
 // 点选表格行填入待隔离片段（已隔离行不可重复选）
 document.querySelectorAll('#data-preview tbody tr').forEach(tr=>{tr.onclick=()=>{const input=document.querySelector('[name=runs]');if(!input)return;const cells=tr.querySelectorAll('td');const run=cells[0]?.textContent.trim();const state=cells[cells.length-1]?.textContent.trim();if(state==='已隔离'){notify('该片段已处于隔离状态，可在下方恢复',true);return;}const current=new Set(input.value.split(',').map(s=>s.trim()).filter(Boolean));if(run&&!current.has(run)){current.add(run);input.value=[...current].join(', ');}};});
 const impactBtn=document.querySelector('#impact-btn');
 if(impactBtn)impactBtn.onclick=async()=>{
  const input=document.querySelector('[name=runs]');const runs=input.value.split(',').map(s=>s.trim()).filter(Boolean);
  if(!runs.length){notify('请先填写要隔离的片段编号',true);return;}
  const selectedBtn=document.querySelector('.batch-item.selected');const id=selectedBtn?.dataset.dataset;
  try{
   const r=await datasets.impact(Number(id),runs);
   const box=document.querySelector('#impact-box');
   if(!r.affected_jobs.length){box.innerHTML='<p class="hint">这些片段当前没有被任何分析实际使用，隔离不会影响现有分析与简报。</p>';return;}
   box.innerHTML='<div class="impact-box"><p class="eyebrow">IMPACT TRACE · 按实际使用片段追溯</p><ul>'+r.affected_jobs.map(j=>'<li class="'+(j.invalid?'already-invalid':'')+'"><strong>'+esc(j.name)+'</strong><span>状态 '+esc(j.status)+' · 班次 '+esc(j.shift)+(j.approved?' · 已批准':'')+(j.invalid?' · 已失效':' · 隔离后将失效')+'</span></li>').join('')+'</ul><p class="hint">共 '+r.affected_jobs.length+' 个分析受影响；其关联定时简报将暂停分发，已发文件标明失效。</p></div>';
  }catch(e){notify(e.message,true);}
 };
 const exForm=document.querySelector('#exclusion-form');
 if(exForm)submit(exForm,async f=>{
  const runs=f.get('runs').split(',').map(s=>s.trim()).filter(Boolean);
  const reason=f.get('reason');
  const selectedBtn=document.querySelector('.batch-item.selected');const id=Number(selectedBtn?.dataset.dataset);
  if(!runs.length){notify('请填写片段编号',true);return;}
  await datasets.quarantineBatch(id,{runs,reason});
  notify('片段已隔离，受影响分析已标记失效、简报已暂停');
  await refresh();
 });
 document.querySelectorAll('[data-restore]').forEach(b=>b.onclick=async()=>{
  try{await datasets.restore(Number(b.dataset.restore));notify('片段已恢复；样本重新匹配的分析已恢复有效');await refresh();}
  catch(e){notify(e.message,true);}
 });
}
