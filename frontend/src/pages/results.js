import {jobs} from '../api/entities.js';
import {workspace} from '../stores/workspace.js';
import {session} from '../stores/session.js';
import {heading} from '../components/common/shell.js';
import {chart} from '../components/common/chart.js';
import {table} from '../components/common/table.js';
import {status} from '../components/common/status.js';
import {esc,fmt,date,notify} from '../utils/dom.js';
import {RecalcStatus} from '../constants/enums.js';
function invalidBanner(j){
 if(j.status!=='invalid')return '';
 return '<section class="panel invalid-banner"><div class="section-title"><h2>该分析结论已失效（旧结论仍可查阅）</h2></div><p>'+esc(j.invalidated_reason||'依据片段被隔离，结论不再可用')+'</p><p class="hint">失效结果不能批准、不能进入分发；请在「数据接入」页查看统一重算进展。替代链：任务 #'+j.id+' → 重算任务沿用相同参数重新计算。</p></section>';
}
function traceBlock(j){
 const runs=j.input_runs||[];
 return '<div class="trace-block"><p class="eyebrow">SAMPLE TRACE / 实际使用片段</p><p class="hint">本任务实际参与计算的片段共 '+runs.length+' 段（计算时快照）：</p><div class="run-chips">'+runs.slice(0,40).map(r=>'<span class="run-chip">'+esc(r)+'</span>').join('')+(runs.length>40?'<span class="run-chip">…+'+(runs.length-40)+'</span>':'')+'</div></div>';
}
function recalcBadge(j,groups){
 if(j.recalc_group_id==null)return '';
 const g=groups.find(x=>x.id===j.recalc_group_id);
 if(!g)return '';
 return '<span class="tag recalc-'+esc(g.status)+'">重算组 #'+g.id+' · '+esc(RecalcStatus[g.status]||g.status)+'</span>';
}
export async function results(id){
 const [list,groups]=await Promise.all([jobs.list(),jobs.recalcGroups()]);
 workspace.jobs=list;
 const j=id?await jobs.get(id):(workspace.jobs.find(x=>x.id===workspace.selectedJob)||workspace.jobs[0]);
 if(j&&!workspace.jobs.some(x=>x.id===j.id))workspace.jobs.push(j);
 if(!j)return heading('04 / REVIEW','结果复核','尚无分析结果。')+'<div class="empty">先到分析工作台，选择批次并提交一次计算。<a href="#/workbench">前往工作台 ↗</a></div>';
 workspace.selectedJob=j.id;const r=j.result||{};
 const replacements=workspace.jobs.filter(x=>x.supersedes_job_id===j.id);
 return heading('04 / REVIEW','结果复核与业务解释',j.name,'<button class="button" id="refresh-results">刷新结果 ↻</button>')
 +'<div class="result-selector"><label>分析记录<select id="select-job">'+workspace.jobs.map(x=>'<option value="'+x.id+'" '+(x.id===j.id?'selected':'')+'>'+esc(x.name)+' · '+esc(x.status)+(x.approved?' · 已批准':'')+'</option>').join('')+'</select></label>'+status(j.status)+recalcBadge(j,groups)+'<span>'+date(j.created_at)+'</span><span class="approval">'+(j.status==='invalid'?'结论已失效':(j.approved?'已获业务批准':'待负责人复核'))+'</span></div>'
 +invalidBanner(j)
 +(j.status==='completed'?'<section class="result-lead"><p class="eyebrow">COMPUTED FINDING</p><h2>'+esc(r.summary)+'</h2><div class="metrics">'+(r.metrics||[]).map(m=>'<div><span>'+esc(m.label)+'</span><strong>'+esc(fmt(m.value))+'<small>'+esc(m.unit||'')+'</small></strong></div>').join('')+'</div></section><section class="panel">'+chart(r.chart)+'</section><div class="two-columns"><section class="panel"><div class="section-title"><h2>业务解释</h2><span>由计算结果生成</span></div><ol class="questions">'+(r.findings||[]).map(v=>'<li>'+esc(v)+'</li>').join('')+'</ol>'+(r.warnings||[]).map(v=>'<p class="warning">'+esc(v)+'</p>').join('')+'</section><section class="method-sheet compact"><p class="eyebrow">REPRODUCIBILITY</p><h3>计算口径与参数</h3><p>'+esc(r.method)+'</p><pre>'+esc(JSON.stringify(j.params,null,2))+'</pre>'+traceBlock(j)+(j.supersedes_job_id?'<p class="hint">本结果为重算任务，替代失效的旧分析 #'+j.supersedes_job_id+'（参数保持一致）。</p>':'')+(replacements.length?'<p class="hint">本分析已被重算任务替代：'+replacements.map(x=>'<a href="#/results/'+x.id+'">#'+x.id+' '+esc(x.name)+' ↗</a>').join('；')+'</p>':'')+(session.user.role==='admin'&&!j.approved?'<button class="primary" id="approve-job">批准此业务结论</button>':'')+'<p class="hint">仅批准结果可进入定时分发档案；失效结果不可批准。</p></section></div><section class="panel"><div class="section-title"><h2>结果明细</h2><span>'+(r.table?.rows?.length||0)+' 行</span></div>'+table(r.table?.columns||[],r.table?.rows||[])+'</section>'
 :'<section class="panel empty">'+(j.status==='invalid'?'该结论已失效，原始参数与结果仍保留可查阅；请前往数据接入页查看统一重算。<a href="#/datasets">前往数据接入 ↗</a>':(j.status==='failed'?'计算失败：'+esc(j.error)+'。若属于重算任务，可在数据接入页重试，接着完成剩余计算。':'后台正在执行计算。点击刷新结果查看最新进展。'))+'<a href="#/workbench">返回工作台 ↗</a></section>');
}
export function bindResults(refresh){document.querySelector('#refresh-results')?.addEventListener('click',refresh);document.querySelector('#select-job')?.addEventListener('change',e=>{workspace.selectedJob=Number(e.target.value);location.hash='#/results/'+e.target.value;});document.querySelector('#approve-job')?.addEventListener('click',async()=>{try{await jobs.approve(workspace.selectedJob);notify('已批准。若该结果属于重算组，全部重算批准后即可在数据接入页切换简报');await refresh();}catch(e){notify(e.message,true);}});}
