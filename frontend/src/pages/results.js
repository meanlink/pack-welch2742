import {jobs} from '../api/entities.js';
import {workspace} from '../stores/workspace.js';
import {session} from '../stores/session.js';
import {heading} from '../components/common/shell.js';
import {chart} from '../components/common/chart.js';
import {table} from '../components/common/table.js';
import {status,invalidBadge} from '../components/common/status.js';
import {esc,fmt,date,notify} from '../utils/dom.js';
export async function results(id){
 workspace.jobs=await jobs.list();const j=id?await jobs.get(id):(workspace.jobs.find(j=>j.id===workspace.selectedJob)||workspace.jobs[0]);
 if(j&&!workspace.jobs.some(x=>x.id===j.id))workspace.jobs.push(j);
 if(!j)return heading('04 / REVIEW','结果复核','尚无分析结果。')+'<div class="empty">先到分析工作台，选择批次并提交一次计算。<a href="#/workbench">前往工作台 ↗</a></div>';
 workspace.selectedJob=j.id;const r=j.result||{};
 const recomputeHint=j.recompute_key?'<p class="warning">该任务属于隔离后统一重算批次（'+esc(j.recompute_key)+'）。同批次全部完成并获批准后，关联简报才会切换到新结果。</p>':'';
 const invalidBanner=j.invalid?'<section class="invalid-banner"><strong>该分析依据的片段已隔离，结论已失效。</strong><p>'+esc(j.invalid_reason||'')+'</p><p class="hint">旧结论仍保留可查阅，但不能批准或用于分发；请在数据接入页发起统一重算。</p>'+(session.user.role!=='viewer'?'<a class="button small" href="#/datasets/'+j.dataset_id+'">前往隔离与重算 ↗</a>':'')+'</section>':'';
 return heading('04 / REVIEW','结果复核与业务解释',j.name,'<button class="button" id="refresh-results">刷新结果 ↻</button>')
  +'<div class="result-selector"><label>分析记录<select id="select-job">'+workspace.jobs.map(x=>'<option value="'+x.id+'" '+(x.id===j.id?'selected':'')+'>'+esc(x.name)+' · '+esc(x.status)+(x.invalid?' · 已失效':'')+'</option>').join('')+'</select></label>'+status(j.status)+invalidBadge(j)+'<span>'+date(j.created_at)+'</span><span class="approval">'+(j.approved?'已获业务批准':'待负责人复核')+'</span>'+(j.source_job_id?'<span class="recompute-tag">重算自 #'+j.source_job_id+'</span>':'')+'</div>'
  +invalidBanner+recomputeHint
  +(j.status==='completed'?'<section class="result-lead"><p class="eyebrow">COMPUTED FINDING</p><h2>'+esc(r.summary)+'</h2><div class="metrics">'+(r.metrics||[]).map(m=>'<div><span>'+esc(m.label)+'</span><strong>'+esc(fmt(m.value))+'<small>'+esc(m.unit||'')+'</small></strong></div>').join('')+'</div></section><section class="panel">'+chart(r.chart)+'</section><div class="two-columns"><section class="panel"><div class="section-title"><h2>业务解释</h2><span>由计算结果生成</span></div><ol class="questions">'+(r.findings||[]).map(v=>'<li>'+esc(v)+'</li>').join('')+'</ol>'+(r.warnings||[]).map(v=>'<p class="warning">'+esc(v)+'</p>').join('')+'</section><section class="method-sheet compact"><p class="eyebrow">REPRODUCIBILITY</p><h3>计算口径与参数</h3><p>'+esc(r.method)+'</p><pre>'+esc(JSON.stringify(j.params,null,2))+'</pre>'+(session.user.role==='admin'&&!j.approved&&!j.invalid?'<button class="primary" id="approve-job">批准此业务结论</button>':'')+(j.invalid?'<p class="warning">失效结果不能批准；重算并完成后才能进入分发。</p>':'')+'<p class="hint">仅批准且有效的结果可进入定时分发档案。</p></section></div><section class="panel"><div class="section-title"><h2>结果明细</h2><span>'+(r.table?.rows?.length||0)+' 行</span></div>'+table(r.table?.columns||[],r.table?.rows||[])+'</section>':'<section class="panel empty">'+(j.status==='failed'?'计算失败：'+esc(j.error)+'。'+(j.invalid?'该任务因输入片段隔离而失效，旧样本结果不会恢复为可用。':'请返回工作台调整参数或数据。'):'后台正在执行计算。点击刷新结果查看最新进展。')+'<a href="#/workbench">返回工作台 ↗</a></section>');
}
export function bindResults(refresh){document.querySelector('#refresh-results')?.addEventListener('click',refresh);document.querySelector('#select-job')?.addEventListener('change',e=>{workspace.selectedJob=Number(e.target.value);location.hash='#/results/'+e.target.value;});document.querySelector('#approve-job')?.addEventListener('click',async()=>{try{await jobs.approve(workspace.selectedJob);notify('已批准；若为重算批次，全部批准后简报将自动切换');await refresh();}catch(e){notify(e.message,true);}});}
