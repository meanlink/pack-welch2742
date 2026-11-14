import {api} from '../api/client.js';
import {workspace} from '../stores/workspace.js';
import {heading} from '../components/common/shell.js';
import {chart} from '../components/common/chart.js';
import {esc,date} from '../utils/dom.js';
export async function overview(){
 const [o,jobs,audits]=await Promise.all([api('/overview'),api('/jobs'),api('/audits')]),m=workspace.meta,baseline=jobs.find(j=>j.status==='completed'&&j.approved);
 return heading('01 / DAILY BRIEF',m.name,m.workflow,'<a class="button primary" href="#/workbench">'+esc(m.action_label||'发起分析')+' ↗</a>')
 +'<section class="overview-hero"><div class="narrative"><p class="eyebrow">当前业务判断</p><h2>'+esc(baseline?.result?.summary||'先导入一批真实业务记录，形成可复核的分析结论。')+'</h2><p>'+esc(m.upstream)+' → '+esc(m.downstream)+'</p><a href="#/results" class="text-link">查看计算依据与业务解释 ↗</a></div><div class="numbers">'+[['有效业务记录',o.records],['数据批次',o.datasets],['分析任务',o.jobs],['已批准结果',o.approved]].map(([k,v])=>'<div><span>'+k+'</span><strong>'+v+'</strong></div>').join('')+'</div></section>'
 +((o.invalid_jobs||o.active_quarantines||o.held_reports)?'<section class="panel alert-strip"><div class="section-title"><h2>样本隔离动态</h2><a class="text-link" href="#/datasets">前往隔离与统一重算 ↗</a></div><div class="numbers">'+[['隔离中片段',o.active_quarantines||0],['失效分析',o.invalid_jobs||0],['暂停简报',o.held_reports||0]].map(([k,v])=>'<div><span>'+k+'</span><strong>'+v+'</strong></div>').join('')+'</div><p class="hint">受影响分析完成重算并全部批准后，简报才会切换到新结果；未使用故障片段的分析与简报照常运行。</p></section>':'')
 +'<section class="panel"><div class="section-title"><h2>基线切片</h2><span>来自 Python 计算 · '+esc(m.method)+'</span></div>'+chart(baseline?.result?.chart)+'</section><div class="two-columns"><section class="panel"><div class="section-title"><h2>今天需要回答</h2></div><ol class="questions">'+m.pains.map(v=>'<li>'+esc(v)+'</li>').join('')+'</ol></section><section class="panel"><div class="section-title"><h2>最近动作</h2><span>可追溯记录</span></div><ul class="timeline">'+audits.slice(0,4).map(a=>'<li><strong>'+esc(a.action)+'</strong><span>'+esc(a.actor)+' · '+date(a.at)+'</span></li>').join('')+'</ul></section></div>';
}
