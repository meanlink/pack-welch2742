import {datasets,jobs} from '../api/entities.js';
import {workspace} from '../stores/workspace.js';
import {session} from '../stores/session.js';
import {heading} from '../components/common/shell.js';
import {table} from '../components/common/table.js';
import {esc,notify,date} from '../utils/dom.js';
import {submit} from '../hooks/forms.js';
import {parseCSV} from '../utils/csv.js';
import {RecalcStatus,QuarantineStatus} from '../constants/enums.js';
const canMaintain=()=>session.user.role==='admin'||session.user.role==='analyst';
function quarantinePanel(d,qlist){
 const active=new Set(d.excluded_runs||[]);
 return '<section class="panel"><div class="section-title"><h2>故障片段隔离 / 恢复</h2><span>'+active.size+' 段隔离中</span></div>'
 +'<p class="hint">隔离不会删除原始记录：批次原始数据与校验指纹保持不变，仅在后续计算中剔除该片段，并按实际用到该片段的分析追溯影响面。恢复须填写复核原因。</p>'
 +(canMaintain()?'<form id="quarantine-form"><div class="parameter-grid"><label>片段号（run）<input name="run" required minlength="1" placeholder="例如 YC-A017"></label><label>隔离原因（必填，留痕）<input name="reason" required minlength="2" placeholder="例如 秒表故障，该段读数异常"></label></div><button type="submit" class="primary">隔离片段并追溯影响 ↗</button></form>':'<p class="hint">观察员只读，不能隔离或恢复片段。</p>')
 +'<div class="quarantine-list">'+(qlist.length?qlist.map(q=>'<article class="quarantine-item '+esc(q.status)+'"><div><strong>'+esc(q.run)+'</strong><p>'+esc(q.reason)+'</p><small>'+(q.status==='active'?'隔离中 · '+date(q.created_at):'已恢复 · '+date(q.restored_at)+' · 恢复原因：'+esc(q.restore_reason||''))+'</small></div>'+(q.status==='active'&&canMaintain()?'<button class="button small" data-restore="'+q.id+'" data-run="'+esc(q.run)+'">恢复</button>':'<span class="tag">'+esc(QuarantineStatus[q.status]||q.status)+'</span>')+'</article>').join(''):'<p class="empty">暂无隔离记录。</p>')+'</div></section>';
}
function impactPanel(preview){
 if(!preview)return '<section class="panel"><div class="section-title"><h2>影响面预览</h2></div><p class="empty">输入片段号后先预览：仅追溯实际用到该片段的分析与简报，未使用该片段的不受影响。</p></section>';
 return '<section class="panel"><div class="section-title"><h2>影响面预览</h2><span>按实际使用片段追溯</span></div>'
 +'<p class="hint">片段 '+esc(preview.runs.join('、'))+' 实际影响以下对象：</p>'
 +'<ul class="impact-list"><li>受影响分析 '+preview.jobs.length+' 个'+(preview.jobs.length?'：'+preview.jobs.map(j=>'#'+j.job_id+' '+esc(j.name)).join('；'):'')+'</li><li>暂停分发计划 '+preview.report_ids.length+' 个</li><li>已发归档标记失效 '+preview.delivery_ids.length+' 份（文件保留可查）</li></ul></section>';
}
function groupBadge(g){return '<span class="tag recalc-'+esc(g.status)+'">'+esc(RecalcStatus[g.status]||g.status)+'</span>';}
function recalcPanel(groups){
 if(!groups.length)return '<section class="panel"><div class="section-title"><h2>受影响分析统一重算</h2></div><p class="empty">隔离片段后，受影响分析会自动进入重算组：每个旧分析只生成一个重算任务，不重复建分析、不漏计划。</p></section>';
 return '<section class="panel"><div class="section-title"><h2>受影响分析统一重算</h2><span>'+groups.length+' 个重算组</span></div>'
 +groups.map(g=>{const failed=g.jobs.filter(j=>j.status==='failed').length,approved=g.jobs.filter(j=>j.status==='completed'&&j.approved).length;
  return '<article class="recalc-card"><div class="recalc-head"><div><strong>重算组 #'+g.id+'</strong> '+groupBadge(g)+'</div><small>'+date(g.created_at)+'</small></div>'
  +'<p class="hint">触发原因：'+esc(g.reason)+'</p><ol class="recalc-jobs">'+g.jobs.map(j=>'<li class="jobline '+esc(j.status)+'"><span>#'+j.id+' '+esc(j.name)+'</span><em>'+esc(j.status)+(j.approved?' · 已批准':'')+'</em>'+(j.status==='failed'?'<small>'+esc(j.error||'计算失败')+'</small>':'')+'</li>').join('')+'</ol>'
  +'<div class="recalc-actions"><small>进度 '+approved+'/'+g.jobs.length+' 已批准'+(failed?' · '+failed+' 个失败，重试将接着完成':'')+'</small>'
  +(failed&&canMaintain()?'<button class="button small" data-retry="'+g.id+'">重试失败任务</button>':'')
  +(g.status==='waiting_approval'?'<button class="primary small" data-switch="'+g.id+'" '+(session.user.role!=='admin'?'disabled':'')+'>全部已批准 · 切换简报到新结果</button>':'')
  +(g.status==='switched'?'<small class="ok">简报已切换到新结果并恢复分发</small>':'')
  +(g.status==='cancelled'?'<small>已被后续样本事件取代，旧结论仍可查阅</small>':'')+'</div></article>';}).join('')+'</section>';
}
export async function dataPage(datasetId){
 workspace.datasets=await datasets.list();
 const requested=datasetId?workspace.datasets.find(d=>d.id===Number(datasetId)):null;
 const first=requested||workspace.datasets.find(d=>d.id===workspace.selectedDataset)||workspace.datasets[0];
 const selected=first?await datasets.get(first.id):null;
 if(selected)workspace.selectedDataset=selected.id;
 const qlist=selected?await datasets.quarantines(selected.id):[];
 const groups=selected?await jobs.recalcGroups(selected.id):[];
 const m=workspace.meta;
 window.__selectedDatasetId=selected?selected.id:null;
 window.__excludedRuns=new Set(selected?.excluded_runs||[]);
 return heading('02 / DATA INTAKE','数据接入与批次追溯','保留原始业务字段、来源和内容指纹。分析任务始终绑定一个数据批次；故障片段可隔离、可恢复并全程留痕。')
 +'<div class="dataset-grid"><section class="panel"><div class="section-title"><h2>业务批次</h2><span>'+workspace.datasets.length+' 批</span></div><div class="batch-list">'
 +workspace.datasets.map(d=>'<button class="batch-item" data-dataset="'+d.id+'"><strong>'+esc(d.name)+'</strong><span>'+d.active_records+' / '+d.rows+' 条有效 · '+esc(d.source)+(d.quarantine_count?' · '+d.quarantine_count+' 段隔离':'')+'</span><small>SHA256 '+esc(d.checksum.slice(0,18))+'…</small></button>').join('')
 +'</div><div class="section-title"><h2>接入新数据</h2></div><form id="dataset-form"><label>批次名称<input name="name" required minlength="2" placeholder="例如：11 月复测批次"></label><label>上传 CSV 或 JSON<input type="file" id="file-input" accept=".json,.csv"></label><label>记录 JSON<textarea name="records" rows="6" placeholder="粘贴 JSON 数组，或先选择上方文件" required></textarea></label><p class="hint">字段：'+m.columns.map(c=>esc(c.key)+' / '+esc(c.label)).join('，')+'。5–5,000 条记录。</p><button type="submit" class="primary" '+(session.user.role==='viewer'?'disabled':'')+'>校验并接入批次</button></form></section>'
 +'<section class="panel"><div class="section-title"><h2 id="preview-name">'+esc(selected?.name||'尚无批次')+'</h2><span>预览前 30 条 · 隔离片段高亮</span></div><div id="data-preview">'+(selected?table(m.columns,selected.records.slice(0,30)):'')+'</div>'
 +(selected?'<div class="impact-tools"><input id="impact-run" placeholder="输入片段号预览影响面，例如 YC-A017"><button class="button small" id="impact-btn">影响面预览</button></div>':'')+'<div id="impact-slot">'+impactPanel(null)+'</div></section></div>'
 +(selected?'<div class="quarantine-grid">'+quarantinePanel(selected,qlist)+recalcPanel(groups)+'</div>':'');
}
export function bindData(refresh){
 let source='manual.json';
 document.querySelector('#file-input')?.addEventListener('change',async e=>{try{const file=e.target.files[0];if(!file)return;source=file.name;const text=await file.text(),records=file.name.endsWith('.csv')?parseCSV(text):JSON.parse(text);document.querySelector('[name=records]').value=JSON.stringify(records,null,2);}catch(error){notify(error.message,true);}});
 document.querySelectorAll('[data-dataset]').forEach(button=>button.onclick=()=>{location.hash='#/datasets/'+button.dataset.dataset;});
 const qform=document.querySelector('#quarantine-form');
 if(qform)submit(qform,async f=>{const out=await datasets.isolate(window.__selectedDatasetId,{run:f.get('run').trim(),reason:f.get('reason').trim()});notify('片段已隔离：'+out.replacement_job_ids.length+' 个受影响分析已进入统一重算，相关简报暂停分发');await refresh();});
 document.querySelectorAll('[data-restore]').forEach(b=>b.onclick=async()=>{const reason=prompt('恢复片段 '+b.dataset.run+'，请填写复核原因（必填）');if(!reason||reason.trim().length<2){notify('恢复原因至少两个字符',true);return;}try{const out=await datasets.restore(b.dataset.restore,reason.trim());notify('片段已恢复，受影响分析已按新样本重新计算');await refresh();}catch(e){notify(e.message,true);}});
 document.querySelector('#impact-btn')?.addEventListener('click',async()=>{const run=document.querySelector('#impact-run').value.trim();if(!run)return notify('请先输入片段号',true);try{document.querySelector('#impact-slot').innerHTML=impactPanel(await datasets.impact(window.__selectedDatasetId,run));}catch(e){notify(e.message,true);}});
 document.querySelectorAll('[data-retry]').forEach(b=>b.onclick=async()=>{try{const r=await jobs.retryRecalc(b.dataset.retry);notify(r.retried_job_ids.length?('已重新提交 '+r.retried_job_ids.length+' 个失败任务，接着完成重算'):'当前没有失败任务');await refresh();}catch(e){notify(e.message,true);}});
 document.querySelectorAll('[data-switch]').forEach(b=>b.onclick=async()=>{try{await jobs.switchRecalc(b.dataset.switch);notify('全部重算结果已批准，简报切换到新结果并恢复分发');await refresh();}catch(e){notify(e.message,true);}});
 const form=document.querySelector('#dataset-form');
 if(form)submit(form,async f=>{await datasets.create({name:f.get('name'),source,records:JSON.parse(f.get('records'))});notify('数据已接入，可前往工作台执行分析');await refresh();});
 document.querySelectorAll('#data-preview tbody tr').forEach(tr=>{
   const run=tr.firstElementChild?.textContent?.trim();
   if(run&&window.__excludedRuns?.has(run))tr.classList.add('row-quarantined');
 });
}
